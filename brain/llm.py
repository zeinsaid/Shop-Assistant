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
    stop_reason: str | None = None  # "end_turn" when the model finished normally
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
        model: str = "claude-sonnet-5",
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
