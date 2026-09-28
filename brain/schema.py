"""Data shapes for the brain: what goes in (IncomingMessage) and what comes out (BrainDecision).

This module checks *shape* only: types and rules between fields. Anything that needs the
knowledge base (do the cited IDs exist? does an answer cite at least one?) lives in brain.py
(D-019). Keeping it that way keeps this file business-agnostic (D-001).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Action(StrEnum):
    """The one action the brain takes for every incoming message (D-002)."""

    ANSWER = "answer"
    ASK_OWNER = "ask_owner"
    HANDOFF = "handoff"
    NO_REPLY = "no_reply"


class Attachment(BaseModel):
    """Metadata about a file the customer sent. There is deliberately no content field (D-010)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: str = Field(min_length=1, description="File kind, e.g. 'pdf' or 'image'.")
    filename: str = Field(min_length=1)
    pages: int | None = Field(default=None, ge=1, description="Page count, when known.")


class IncomingMessage(BaseModel):
    """One customer message, in the channel-independent shape the brain works with."""

    model_config = ConfigDict(extra="forbid")

    text: str = ""
    attachments: list[Attachment] = Field(default_factory=list)


class BrainDecision(BaseModel):
    """The brain's decision for one incoming customer message.

    Field order matters: the model writes them top to bottom, so `reasoning` comes first (D-019).
    Every field is required: the model always writes all five keys, using null or [] when a field
    doesn't apply (D-020).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reasoning: str = Field(
        min_length=1,
        description=(
            "Your private reasoning, in 1-4 short sentences. Is the customer talking to us, or "
            "sending material for staff to handle (a file or pasted text)? Which knowledge-base "
            "entries are relevant, and is anything missing? Does an internal entry or rule apply? "
            "Then say which action follows and why. Never shown to the customer."
        ),
    )
    action: Action = Field(
        description=(
            "Exactly one action for this message. "
            "'answer': reply using the knowledge base. "
            "'ask_owner': the knowledge base doesn't cover it, but the owner could resolve it with "
            "one reply (information or a decision). "
            "'handoff': a person must take over or physically do something (complaint, refund, "
            "negotiation, checking an order or a lost item). "
            "'no_reply': the message is material submitted for staff to handle (a file or pasted "
            "text), not a message addressed to us."
        ),
    )
    reply: str | None = Field(
        description=(
            "The message to send to the customer, in the customer's language. "
            "Required for 'answer'. "
            "Required for 'ask_owner': a short holding message saying we'll check and get back to "
            "them. "
            "Required for 'handoff': a short message saying a team member will take over. "
            "Must be null for 'no_reply'. "
            "Never reveal or paraphrase knowledge-base entries marked internal."
        ),
    )
    cited_entries: list[str] = Field(
        description=(
            "IDs of the knowledge-base entries your reply relies on, exactly as written in the "
            "knowledge base. An 'answer' must cite at least one. Use [] if nothing supports a reply."
        ),
    )
    question_for_owner: str | None = Field(
        description=(
            "Required for 'ask_owner', null otherwise. A self-contained question for the owner, "
            "always written in English whatever language the customer used: what the customer "
            "asked, plus any details already gathered from the customer, so the owner can settle "
            "it in one reply."
        ),
    )

    @field_validator("reply", "question_for_owner")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        # Models often write "" instead of null. Whitespace is already stripped by the config.
        return value or None

    @model_validator(mode="after")
    def check_action_consistency(self) -> "BrainDecision":
        needs_reply = self.action is not Action.NO_REPLY
        needs_question = self.action is Action.ASK_OWNER

        if needs_reply and self.reply is None:
            raise ValueError(f"action '{self.action}' requires a reply")
        if not needs_reply and self.reply is not None:
            raise ValueError("action 'no_reply' must not include a reply")
        if needs_question and self.question_for_owner is None:
            raise ValueError("action 'ask_owner' requires question_for_owner")
        if not needs_question and self.question_for_owner is not None:
            raise ValueError(
                f"question_for_owner is only allowed with 'ask_owner', not '{self.action}'"
            )
        return self
