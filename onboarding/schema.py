"""What the interviewer returns each turn (D-030).

The topic IDs must match the ones listed in prompts/interview.md; a test checks they do.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Topic(StrEnum):
    """The interview checklist. Business-agnostic: every small business has these (D-026)."""

    BASICS = "basics"
    HOURS = "hours"
    SERVICES = "services"
    PRICES = "prices"
    QUOTES = "quotes"
    TURNAROUND = "turnaround"
    ORDERING = "ordering"
    PAYMENT = "payment"
    DISCOUNTS = "discounts"
    LIMITS = "limits"
    ESCALATION = "escalation"
    PRIVATE = "private"
    SCOPE = "scope"
    STYLE = "style"


class InterviewTurn(BaseModel):
    """One interviewer turn: what to say to the owner, plus progress for the code to track."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(
        min_length=1,
        description=(
            "What you say to the owner now, in the owner's language: usually your next question, "
            "or the final summary when every topic is covered."
        ),
    )
    covered: list[Topic] = Field(
        description=(
            "IDs of every topic covered so far in the whole interview, not just this turn. A topic "
            "is covered when you have the owner's answer, or the owner said it doesn't apply."
        ),
    )
    done: bool = Field(
        description=(
            "True only when the owner has confirmed your final summary. False otherwise, "
            "including on the turn where you present the summary."
        ),
    )
