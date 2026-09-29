"""The brain: one incoming message in, one checked decision out.

Flow for each message (D-003, D-019, D-020):
1. Send the system prompt (instructions + KB) and the formatted message to the model.
2. Validate the response: JSON shape (schema.py), then KB rules that need the KB (here).
3. If it fails, tell the model what was wrong and let it try once more.
4. If it fails again, fall back to a fixed ask_owner so the customer is never left with a bad reply.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from brain.kb import KnowledgeBase
from brain.llm import Completion, LLMClient, Message
from brain.schema import Action, BrainDecision, IncomingMessage

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "brain.md"

MAX_ATTEMPTS = 2  # the first try plus one corrective retry

# Used when the model fails twice (D-020). A business can set its own, for example in several
# languages, with a `fallback_reply:` line in its knowledge base's front matter.
FALLBACK_REPLY = "Let me check with the team and get back to you."

CORRECTION = (
    "Your previous response was not accepted:\n{problems}\n\n"
    "Reply again with a corrected decision for the same customer message. If you can't support an "
    "answer with a public knowledge-base entry, don't answer: choose another action."
)

# Our input tags. Customer text can't be allowed to open or close them (see format_message).
TAG = re.compile(r"</?\s*(customer_message|attachments|knowledge_base)\s*>", re.IGNORECASE)


@dataclass
class Attempt:
    completion: Completion
    problems: list[str]  # empty when the attempt was accepted


@dataclass
class BrainResult:
    decision: BrainDecision
    fallback_used: bool
    attempts: list[Attempt]
    dropped_citations: list[str] = field(default_factory=list)  # unknown IDs removed from a non-answer

    @property
    def input_tokens(self) -> int:
        return sum(a.completion.input_tokens for a in self.attempts)

    @property
    def output_tokens(self) -> int:
        return sum(a.completion.output_tokens for a in self.attempts)


class Brain:
    def __init__(self, kb: KnowledgeBase, client: LLMClient, prompt: str | None = None):
        self.kb = kb
        self.client = client
        self.fallback_reply = kb.metadata.get("fallback_reply") or FALLBACK_REPLY
        instructions = prompt if prompt is not None else PROMPT_PATH.read_text(encoding="utf-8")
        self.system = build_system_prompt(instructions, kb)
        self.schema = BrainDecision.model_json_schema()

    def decide(self, message: IncomingMessage) -> BrainResult:
        messages: list[Message] = [{"role": "user", "content": format_message(message)}]
        attempts: list[Attempt] = []

        for _ in range(MAX_ATTEMPTS):
            completion = self.client.complete(self.system, messages, self.schema)
            decision, problems = self._check(completion)
            attempts.append(Attempt(completion, problems))
            if decision is not None and not problems:
                decision, dropped = self._drop_unknown_citations(decision)
                return BrainResult(decision, False, attempts, dropped)
            # Show the model its own answer and what was wrong with it, then ask again.
            messages += [
                {"role": "assistant", "content": completion.text or "(empty response)"},
                {"role": "user", "content": CORRECTION.format(problems="\n".join(f"- {p}" for p in problems))},
            ]

        return BrainResult(self._fallback(message, attempts[-1].problems), True, attempts)

    def _check(self, completion: Completion) -> tuple[BrainDecision | None, list[str]]:
        """Return the parsed decision (if it parsed) and every rule it breaks."""
        if completion.stop_reason in ("max_tokens", "refusal"):
            return None, [f"the response was cut off (stop reason: {completion.stop_reason})"]
        try:
            decision = BrainDecision.model_validate_json(completion.text)
        except ValidationError as e:
            return None, [_describe(error) for error in e.errors()]

        problems = []
        if decision.action is Action.ANSWER:
            unknown = [c for c in decision.cited_entries if c not in self.kb.entries]
            if unknown:
                problems.append(f"cited IDs that don't exist in the knowledge base: {', '.join(unknown)}")
            if not any(self.kb.is_public(c) for c in decision.cited_entries):
                problems.append("an 'answer' must cite at least one public knowledge-base entry that supports it")
        return decision, problems

    def _drop_unknown_citations(self, decision: BrainDecision) -> tuple[BrainDecision, list[str]]:
        """Non-answers may cite loosely (D-020), but unknown IDs are never passed on."""
        dropped = [c for c in decision.cited_entries if c not in self.kb.entries]
        if not dropped:
            return decision, []
        kept = [c for c in decision.cited_entries if c in self.kb.entries]
        return decision.model_copy(update={"cited_entries": kept}), dropped

    def _fallback(self, message: IncomingMessage, problems: list[str]) -> BrainDecision:
        return BrainDecision(
            reasoning=f"Fallback after {MAX_ATTEMPTS} invalid attempts. Last problems: {'; '.join(problems)}",
            action=Action.ASK_OWNER,
            reply=self.fallback_reply,
            cited_entries=[],
            question_for_owner=(
                "The assistant couldn't produce a valid answer to this customer message. "
                f"Message: {message.text or '(no text)'}. Attachments: {_describe_attachments(message)}."
            ),
        )


def build_system_prompt(instructions: str, kb: KnowledgeBase) -> str:
    """Instructions first, then the KB. Both are identical on every call, so the whole thing caches."""
    return f"{instructions.rstrip()}\n\n<knowledge_base>\n{kb.text.strip()}\n</knowledge_base>\n"


def format_message(message: IncomingMessage) -> str:
    """Wrap the customer's message in the tags the prompt describes."""
    return (
        f"<customer_message>\n{_neutralise(message.text)}\n</customer_message>\n"
        f"<attachments>\n{_neutralise(_describe_attachments(message, bullet=True))}\n</attachments>"
    )


def _neutralise(text: str) -> str:
    # Stops a customer (or filename) from closing our tags and posing as instructions or KB.
    return TAG.sub(lambda m: m.group(0).replace("<", "&lt;").replace(">", "&gt;"), text)


def _describe_attachments(message: IncomingMessage, bullet: bool = False) -> str:
    if not message.attachments:
        return "none"
    parts = []
    for a in message.attachments:
        pages = f" ({a.pages} pages)" if a.pages else ""
        parts.append(f"{a.type}: {a.filename}{pages}")
    return "\n".join(f"- {p}" for p in parts) if bullet else ", ".join(parts)


def _describe(error: dict) -> str:
    location = ".".join(str(part) for part in error["loc"]) or "response"
    return f"{location}: {error['msg']}"
