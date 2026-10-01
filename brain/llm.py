"""The seam between the brain and a model provider (D-022).

The brain only needs one operation: send a system prompt and a conversation, get back JSON text
that should match a schema. Each provider implements that as a small class; the brain validates
the text itself, so every provider is checked by the same rules.
"""

import json
from dataclasses import dataclass
from typing import Protocol

import anthropic


@dataclass(frozen=True)
class Completion:
    text: str  # the model's raw output, expected to be JSON
    # Normalised across providers: "end_turn" when the model finished normally, "max_tokens" when
    # it was cut off, "refusal" when it declined. Anything else also counts as unfinished.
    stop_reason: str | None = None
    input_tokens: int = 0  # uncached input
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


# One conversation turn: {"role": "user" | "assistant", "content": "..."}
Message = dict[str, str]


class LLMClient(Protocol):
    model: str

    def complete(self, system: str, messages: list[Message], schema: dict) -> Completion: ...


# --- Anthropic ---------------------------------------------------------------------------------

# JSON Schema keywords the structured-outputs feature doesn't accept. Our Pydantic validation
# still enforces them after the response comes back.
UNSUPPORTED_SCHEMA_KEYS = {
    "minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "multipleOf", "minItems", "maxItems",
}


def strip_unsupported(schema):
    """Return a copy of a JSON schema without keywords the API rejects."""
    if isinstance(schema, dict):
        return {k: strip_unsupported(v) for k, v in schema.items() if k not in UNSUPPORTED_SCHEMA_KEYS}
    if isinstance(schema, list):
        return [strip_unsupported(v) for v in schema]
    return schema


class AnthropicClient:
    """Calls Claude with structured outputs, caching the system prompt (instructions + KB)."""

    def __init__(
        self,
        model: str = "claude-sonnet-5-5",
        max_tokens: int = 16000,
        effort: str | None = "low",  # "low" ... "max"; None uses the model's default
        client: anthropic.Anthropic | None = None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort
        self._client = client or anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

    def complete(self, system: str, messages: list[Message], schema: dict) -> Completion:
        output_config: dict = {"format": {"type": "json_schema", "schema": strip_unsupported(schema)}}
        if self.effort:
            output_config["effort"] = self.effort

        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            # The system prompt is identical on every call, so it's cached: later calls read it
            # at a tenth of the input price.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            output_config=output_config,
        )
        usage = response.usage
        return Completion(
            text="".join(block.text for block in response.content if block.type == "text"),
            stop_reason=response.stop_reason,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_input_tokens or 0,
            cache_write_tokens=usage.cache_creation_input_tokens or 0,
        )


# --- Schema for OpenAI and Gemini --------------------------------------------------------------


def portable_schema(schema: dict) -> dict:
    """Rewrite a Pydantic JSON schema into the plain subset every provider accepts.

    - `$ref`/`$defs` are inlined (the `Action` enum becomes a plain enum on the field),
    - `anyOf: [X, null]` becomes `type: [X, "null"]`,
    - keywords the APIs reject (`minLength`, ...) are dropped; Pydantic still checks them.
    """
    defs = schema.get("$defs", {})

    def convert(node):
        if isinstance(node, list):
            return [convert(item) for item in node]
        if not isinstance(node, dict):
            return node
        node = dict(node)
        if "$ref" in node:  # {"$ref": "#/$defs/Action", "description": ...}
            target = defs[node.pop("$ref").rsplit("/", 1)[-1]]
            node = {**target, **node}
        options = node.get("anyOf")
        if options and len(options) == 2 and {"type": "null"} in options:
            other = next(o for o in options if o != {"type": "null"})
            if set(other) == {"type"} and isinstance(other["type"], str):
                del node["anyOf"]
                node["type"] = [other["type"], "null"]
        return {k: convert(v) for k, v in node.items() if k != "$defs" and k not in UNSUPPORTED_SCHEMA_KEYS}

    return convert(schema)


# --- OpenAI ------------------------------------------------------------------------------------


class OpenAIClient:
    """Calls a GPT model through the Responses API with a strict JSON schema.

    OpenAI caches long repeated prefixes automatically; the instructions and KB come first.
    """

    def __init__(self, model: str = "gpt-6.1-sol", max_tokens: int = 16000, effort: str | None = "low", client=None):
        import openai  # imported here so the brain doesn't load every provider's SDK

        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort
        self._client = client or openai.OpenAI()  # reads OPENAI_API_KEY from the environment

    def complete(self, system: str, messages: list[Message], schema: dict) -> Completion:
        extra = {"reasoning": {"effort": self.effort}} if self.effort else {}
        response = self._client.responses.create(
            model=self.model,
            instructions=system,
            input=[{"role": m["role"], "content": m["content"]} for m in messages],
            text={"format": {"type": "json_schema", "name": "brain_decision", "strict": True,
                             "schema": portable_schema(schema)}},
            max_output_tokens=self.max_tokens,
            store=False,  # don't keep customer messages on OpenAI's side
            **extra,
        )

        stop_reason = "end_turn"
        if response.status == "incomplete":
            reason = getattr(response.incomplete_details, "reason", None)
            stop_reason = "max_tokens" if reason == "max_output_tokens" else "refusal"
        elif response.status != "completed":
            stop_reason = str(response.status)
        if any(c.type == "refusal" for item in response.output if item.type == "message" for c in item.content):
            stop_reason = "refusal"

        usage = response.usage
        cached = usage.input_tokens_details.cached_tokens or 0
        written = getattr(usage.input_tokens_details, "cache_write_tokens", 0) or 0
        return Completion(
            text=response.output_text,
            stop_reason=stop_reason,
            input_tokens=usage.input_tokens - cached - written,  # OpenAI's input count includes cached tokens
            output_tokens=usage.output_tokens,  # includes reasoning tokens, which are billed as output
            cache_read_tokens=cached,
            cache_write_tokens=written,
        )


# --- Google Gemini -----------------------------------------------------------------------------


class GeminiClient:
    """Calls a Gemini model through the Interactions API with a JSON schema.

    Gemini caches repeated prefixes implicitly; the instructions and KB come first.
    """

    def __init__(self, model: str = "gemini-3.5-flash-lite", max_tokens: int = 16000, effort: str | None = "low",
                 client=None):
        from google import genai  # imported here so the brain doesn't load every provider's SDK

        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort  # sent as thinking_level: "minimal", "low", "medium" or "high"
        self._client = client or genai.Client()  # reads GEMINI_API_KEY (or GOOGLE_API_KEY)

    def complete(self, system: str, messages: list[Message], schema: dict) -> Completion:
        config: dict = {"max_output_tokens": self.max_tokens}
        if self.effort:
            config["thinking_level"] = self.effort
        interaction = self._client.interactions.create(
            model=self.model,
            system_instruction=system,
            # Our turns become Gemini "steps": the customer side is user_input, ours model_output.
            input=[
                {"type": "user_input" if m["role"] == "user" else "model_output",
                 "content": [{"type": "text", "text": m["content"]}]}
                for m in messages
            ],
            response_format={"type": "text", "mime_type": "application/json", "schema": portable_schema(schema)},
            generation_config=config,
            store=False,  # don't keep customer messages on Google's side
        )

        status = str(interaction.status)
        stop_reason = {"completed": "end_turn", "incomplete": "max_tokens"}.get(status, status)
        usage = interaction.usage
        cached = (usage.total_cached_tokens or 0) if usage else 0
        return Completion(
            text=interaction.output_text or "",
            stop_reason=stop_reason,
            input_tokens=((usage.total_input_tokens or 0) - cached) if usage else 0,  # input includes cached
            # Thinking tokens are billed as output. This assumes total_output_tokens excludes them,
            # as Gemini's older API did; check it against the first live run's bill.
            output_tokens=((usage.total_output_tokens or 0) + (usage.total_thought_tokens or 0)) if usage else 0,
            cache_read_tokens=cached,
        )


# --- No-cost clients ---------------------------------------------------------------------------


class DryRunClient:
    """Calls no model. Always escalates, so the whole pipeline can run for free (no API key)."""

    model = "dry-run"

    def complete(self, system: str, messages: list[Message], schema: dict) -> Completion:
        decision = {
            "reasoning": "Dry run: no model was called.",
            "action": "ask_owner",
            "reply": "(dry run) Let me check with the team and get back to you.",
            "cited_entries": [],
            "question_for_owner": "(dry run) No model was called for this message.",
        }
        return Completion(text=json.dumps(decision), stop_reason="end_turn")


class ScriptedClient:
    """Returns prepared responses in order and records every call. For tests."""

    model = "scripted"

    def __init__(self, responses: list[str | Completion]):
        self._responses = list(responses)
        self.calls: list[tuple[str, list[Message], dict]] = []

    def complete(self, system: str, messages: list[Message], schema: dict) -> Completion:
        self.calls.append((system, [dict(m) for m in messages], schema))
        if not self._responses:
            raise AssertionError("ScriptedClient ran out of responses")
        response = self._responses.pop(0)
        return response if isinstance(response, Completion) else Completion(response, "end_turn")


# --- Choosing a client -------------------------------------------------------------------------


def make_client(model: str, effort: str | None = "low") -> LLMClient:
    """Pick the client for a model name. New providers are added here (D-022)."""
    if model == "dry-run":
        return DryRunClient()
    if model.startswith("claude-"):
        return AnthropicClient(model=model, effort=effort)
    if model.startswith("gpt-"):
        return OpenAIClient(model=model, effort=effort)
    if model.startswith("gemini-"):
        return GeminiClient(model=model, effort=effort)
    raise ValueError(f"no client for model '{model}' (supported: dry-run, claude-*, gpt-*, gemini-*)")
