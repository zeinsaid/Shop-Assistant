"""The relay + learn call (D-004): after the owner answers a question the brain escalated.

One model call through the same `LLMClient` seam as the brain. It writes the reply that carries the
owner's answer to the customer, and drafts a knowledge-base entry for the owner to approve. Checked
like `brain.decide`: Pydantic for the shape, code for the rules that need the KB, one corrective
retry, then a fallback (the caller sends the owner's answer as-is).

The owner then approves the draft with Save / Edit / Just this once; storing it is the app's job.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from brain.brain import format_history
from brain.kb import KnowledgeBase
from brain.llm import Completion, LLMClient, Message
from brain.schema import Turn

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "learn.md"

MAX_ATTEMPTS = 2  # the first try plus one corrective retry, like the brain
HISTORY_LIMIT = 10  # messages of the conversation the model sees

log = logging.getLogger("brain.learn")


class LearnAction(StrEnum):
    ADD = "add"
    UPDATE = "update"
    NONE = "none"


class ProposedEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(description="Lowercase, hyphenated, unique. For 'update', the existing entry's ID.")
    visibility: Literal["public", "internal"]
    text: str = Field(min_length=1, description="The complete entry text, in English.")


class LearnResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reasoning: str = Field(min_length=1, description="1-3 plain sentences for the owner: general or one-off, and why.")
    reply_to_customer: str | None = Field(description="The message to the customer in their language, or null if the owner's answer isn't for the customer.")
    learn_action: LearnAction
    target_entry_id: str | None = Field(description="Required for 'update', null otherwise.")
    proposed_entry: ProposedEntry | None = Field(description="Required for 'add' and 'update', null for 'none'.")
    owner_summary: str = Field(description="One short line for the owner saying what would be saved, or why nothing is.")


def learn_schema() -> dict:
    """The JSON schema the model must follow. The client makes it portable (`portable_schema`)."""
    return LearnResult.model_json_schema()


CORRECTION = (
    "Your previous response was not accepted:\n{problems}\n\n"
    "Reply again with a corrected result for the same owner answer. Pass on only what the owner said."
)

# Our input tags. Customer or owner text can't be allowed to open or close them.
TAG = re.compile(r"</?\s*(knowledge_base|conversation|question_for_owner|owner_answer)\s*>", re.IGNORECASE)
ENTRY_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass
class LearnOutcome:
    result: LearnResult | None  # None when the model failed twice (fallback)
    attempts: list[Completion | None] = field(default_factory=list)  # None: the call itself raised
    problems: list[str] = field(default_factory=list)  # from the last failed attempt

    @property
    def fallback_used(self) -> bool:
        return self.result is None


class Learner:
    """Runs the relay + learn call for one knowledge base."""

    def __init__(self, kb: KnowledgeBase, client: LLMClient, prompt: str | None = None):
        self.kb = kb
        self.client = client
        self.system = prompt if prompt is not None else PROMPT_PATH.read_text(encoding="utf-8")
        self.schema = learn_schema()

    def run(self, history: list[Turn], question: str, owner_answer: str) -> LearnOutcome:
        messages: list[Message] = [
            {"role": "user", "content": format_input(self.kb, history, question, owner_answer)}
        ]
        outcome = LearnOutcome(result=None)

        for _ in range(MAX_ATTEMPTS):
            try:
                completion = self.client.complete(self.system, messages, self.schema)
            except Exception:
                # A provider error never reaches the owner as a failure: retry once, then fall back.
                log.exception("learn call failed")
                outcome.attempts.append(None)
                outcome.problems = ["the model call failed"]
                continue
            outcome.attempts.append(completion)
            result, problems = self.check(completion)
            if result is not None and not problems:
                outcome.result = result
                outcome.problems = []
                return outcome
            outcome.problems = problems
            messages += [
                {"role": "assistant", "content": completion.text or "(empty response)"},
                {"role": "user", "content": CORRECTION.format(problems="\n".join(f"- {p}" for p in problems))},
            ]
        return outcome

    def check(self, completion: Completion) -> tuple[LearnResult | None, list[str]]:
        """Return the parsed result (normalised where the fix is obvious) and every rule it breaks."""
        if completion.stop_reason not in (None, "end_turn"):
            return None, [f"the response didn't finish normally (stop reason: {completion.stop_reason})"]
        try:
            result = LearnResult.model_validate_json(completion.text)
        except ValidationError as e:
            return None, [_describe(error) for error in e.errors()]

        problems: list[str] = []
        if result.reply_to_customer is not None and not result.reply_to_customer:
            problems.append("reply_to_customer is empty: write the message, or use null if nothing goes to the customer")

        action = result.learn_action
        entry = result.proposed_entry
        if action is LearnAction.NONE:
            # Nothing to save, so a stray draft or target is simply dropped.
            return result.model_copy(update={"proposed_entry": None, "target_entry_id": None}), problems

        if entry is None:
            problems.append(f"'{action}' needs a proposed_entry")
            return result, problems
        problems += _text_problems(entry.text)

        if action is LearnAction.ADD:
            if not ENTRY_ID.match(entry.id):
                problems.append(f"proposed_entry.id '{entry.id}' must be lowercase words joined by hyphens")
                return result, problems
            new_id = self._free_id(entry.id)
            return result.model_copy(update={
                "target_entry_id": None,
                "proposed_entry": entry.model_copy(update={"id": new_id}),
            }), problems

        # update: it must change an existing public entry, keeping its ID.
        target = result.target_entry_id or entry.id
        existing = self.kb.entries.get(target)
        if existing is None:
            problems.append(f"target_entry_id '{target}' doesn't exist in the knowledge base")
        elif not self.kb.is_public(target):
            problems.append(f"'{target}' is an internal entry; internal entries are never updated")
        return result.model_copy(update={
            "target_entry_id": target,
            "proposed_entry": entry.model_copy(update={"id": target}),
        }), problems

    def _free_id(self, entry_id: str) -> str:
        """An `add` needs a new ID: if it's taken, append -2 (then -3, ...)."""
        if entry_id not in self.kb.entries:
            return entry_id
        n = 2
        while f"{entry_id}-{n}" in self.kb.entries:
            n += 1
        return f"{entry_id}-{n}"


def _text_problems(text: str) -> list[str]:
    problems = []
    lines = text.splitlines()
    if any(line.lstrip().startswith("#") for line in lines):
        problems.append("proposed_entry.text must not contain a line starting with '#'")
    if any(line.strip() == "---" for line in lines):
        problems.append("proposed_entry.text must not contain a line that is only '---'")
    return problems


def format_input(kb: KnowledgeBase, history: list[Turn], question: str, owner_answer: str) -> str:
    """The user message: each part in the tags `brain/prompts/learn.md` describes."""
    conversation = format_history(history, limit=HISTORY_LIMIT) if history else "(no messages)"
    return (
        f"<knowledge_base>\n{kb.text.strip()}\n</knowledge_base>\n"
        f"<conversation>\n{_neutralise(conversation)}\n</conversation>\n"
        f"<question_for_owner>\n{_neutralise(question)}\n</question_for_owner>\n"
        f"<owner_answer>\n{_neutralise(owner_answer)}\n</owner_answer>"
    )


def _neutralise(text: str) -> str:
    return TAG.sub(lambda m: m.group(0).replace("<", "&lt;").replace(">", "&gt;"), text)


def _describe(error: dict) -> str:
    location = ".".join(str(part) for part in error["loc"]) or "response"
    return f"{location}: {error['msg']}"
