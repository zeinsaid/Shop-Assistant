"""The interview loop (D-030): the owner talks, the model asks, the code keeps score.

The transcript is the single source of truth. It's saved after every turn, so an interview can
stop at any point and be resumed later, and the drafting step (next) reads it to write the KB.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from brain.llm import LLMClient, Message
from onboarding.schema import InterviewTurn, Topic

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "interview.md"

# The providers need the conversation to start with a user message, and the owner hasn't said
# anything yet when the interview opens. This stands in for "the owner opened the tool".
OPENING = "(The owner has opened the interview and is waiting for your first question.)"

CORRECTION = (
    "Your previous response was not accepted:\n{problems}\n\n"
    "Reply again with a corrected response for the same point in the interview."
)


class InterviewError(Exception):
    """The model failed to produce a valid turn twice in a row."""


@dataclass
class Interview:
    client: LLMClient
    transcript: list[dict] = field(default_factory=list)  # {"role": "owner" | "interviewer", "text": ...}
    covered: set[Topic] = field(default_factory=set)
    done: bool = False
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    prompt: str = field(default_factory=lambda: PROMPT_PATH.read_text(encoding="utf-8"))

    def start(self) -> str:
        """The interviewer's opening message. On a resumed interview, its last message instead."""
        if self.transcript:
            return next(t["text"] for t in reversed(self.transcript) if t["role"] == "interviewer")
        return self._ask()

    def reply(self, owner_text: str) -> str:
        """Record what the owner said and return the interviewer's next message."""
        if self.done:
            raise InterviewError("the interview is already finished")
        self.transcript.append({"role": "owner", "text": owner_text})
        return self._ask()

    @property
    def remaining(self) -> list[Topic]:
        return [t for t in Topic if t not in self.covered]

    # --- one model turn ------------------------------------------------------------------------

    def _ask(self) -> str:
        messages = self._messages()
        schema = InterviewTurn.model_json_schema()
        problems: list[str] = []
        for _ in range(2):  # one try plus one corrective retry, as in the brain (D-025)
            completion = self.client.complete(self.prompt, messages, schema)
            try:
                turn = InterviewTurn.model_validate_json(completion.text)
                break
            except ValidationError as e:
                problems = [f"{'.'.join(map(str, err['loc'])) or 'response'}: {err['msg']}" for err in e.errors()]
                messages = messages + [
                    {"role": "assistant", "content": completion.text or "(empty response)"},
                    {"role": "user", "content": CORRECTION.format(problems="\n".join(f"- {p}" for p in problems))},
                ]
        else:
            raise InterviewError(f"no valid interviewer turn after a retry: {'; '.join(problems)}")

        # Coverage only grows: if the model forgets a topic it reported earlier, it stays covered.
        self.covered |= set(turn.covered)
        self.done = turn.done
        self.transcript.append({"role": "interviewer", "text": turn.message})
        return turn.message

    def _messages(self) -> list[Message]:
        """The transcript as provider messages: the owner is the user, the interviewer the assistant."""
        messages: list[Message] = [{"role": "user", "content": OPENING}]
        for t in self.transcript:
            role = "user" if t["role"] == "owner" else "assistant"
            if role == "user" and messages[-1]["role"] == "user":  # owner spoke first after OPENING
                messages[-1] = {"role": "user", "content": t["text"]}
            else:
                messages.append({"role": role, "content": t["text"]})
        return messages

    # --- saving and resuming -------------------------------------------------------------------

    def save(self, path: Path) -> None:
        data = {
            "started_at": self.started_at,
            "model": getattr(self.client, "model", None),
            "done": self.done,
            "covered": [t.value for t in Topic if t in self.covered],
            "transcript": self.transcript,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path, client: LLMClient) -> "Interview":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(client=client, transcript=data["transcript"], covered={Topic(t) for t in data["covered"]},
                   done=data["done"], started_at=data["started_at"])
