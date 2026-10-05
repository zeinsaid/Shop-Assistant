"""Turn a finished interview into a draft knowledge base (D-030), and optionally a translated copy.

    uv run --env-file .env python -m onboarding.draft --session my-shop --model claude-sonnet-5-5
    uv run --env-file .env python -m onboarding.draft --session my-shop --model claude-sonnet-5-5 --review-language el

The draft goes to onboarding/drafts/<session>.md (gitignored) for the owner to review and edit.
Nothing here touches a live KB: copying a reviewed draft into kb/ is a deliberate, separate step.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from brain.kb import KBError, parse_kb
from brain.llm import LLMClient, make_client
from onboarding.interview import Interview

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
SESSIONS = Path(__file__).resolve().parent / "sessions"
DRAFTS = Path(__file__).resolve().parent / "drafts"

# A whole KB is long. Anthropic's SDK refuses non-streaming requests that could run past about
# ten minutes (roughly max_tokens above 21,000), so stay under that.
DRAFT_MAX_TOKENS = 20000

REQUIRED_SETTINGS = ("business", "fallback_reply", "default_language")

CORRECTION = (
    "Your knowledge base was not accepted:\n{problems}\n\n"
    "Write the whole knowledge base again with these problems fixed."
)

# Transcript text can't be allowed to close the tag that wraps it.
TAG = re.compile(r"</?\s*interview_transcript\s*>", re.IGNORECASE)


class KBDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kb_markdown: str = Field(min_length=1, description="The complete knowledge base file, in the required format.")
    open_questions: list[str] = Field(
        description="Everything the owner should still settle, in English. Empty if there's nothing."
    )


class Translation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, description="The whole knowledge base, translated.")


class DraftError(Exception):
    """The model failed to write a valid knowledge base twice in a row."""


@dataclass
class DraftResult:
    kb_markdown: str
    open_questions: list[str]
    attempts: int


def check_kb(text: str) -> list[str]:
    """Everything that stops a draft from being usable by the brain. Empty when it's fine."""
    try:
        kb = parse_kb(text)
    except KBError as e:
        return [str(e)]
    problems = [f"front matter is missing '{key}'" for key in REQUIRED_SETTINGS if not kb.metadata.get(key)]
    if not any(kb.is_public(entry_id) for entry_id in kb.entries):
        problems.append("there are no public entries, so the receptionist could never answer")
    return problems


def format_transcript(interview: Interview) -> str:
    lines = [f"[{t['role']}] {TAG.sub('', t['text'])}" for t in interview.transcript]
    return "<interview_transcript>\n" + "\n\n".join(lines) + "\n</interview_transcript>"


def draft_kb(interview: Interview, client: LLMClient, today: date | None = None) -> DraftResult:
    """Ask the model for a KB, check it with the brain's own parser, and allow one corrective retry."""
    system = (PROMPTS / "draft.md").read_text(encoding="utf-8")
    today = today or date.today()
    messages = [{"role": "user", "content": f"Today's date: {today.isoformat()}\n\n{format_transcript(interview)}"}]
    schema = KBDraft.model_json_schema()

    problems: list[str] = []
    for attempt in (1, 2):
        completion = client.complete(system, messages, schema)
        try:
            draft = KBDraft.model_validate_json(completion.text)
            problems = check_kb(draft.kb_markdown)
        except ValidationError as e:
            problems = [f"response: {err['msg']}" for err in e.errors()]
        if not problems:
            return DraftResult(draft.kb_markdown, draft.open_questions, attempt)
        messages = messages + [
            {"role": "assistant", "content": completion.text or "(empty response)"},
            {"role": "user", "content": CORRECTION.format(problems="\n".join(f"- {p}" for p in problems))},
        ]
    raise DraftError("; ".join(problems))


def translate_kb(kb_markdown: str, language: str, client: LLMClient) -> str:
    """A translated copy for the owner to read. The English KB stays the one the receptionist uses."""
    system = (PROMPTS / "translate_kb.md").read_text(encoding="utf-8")
    messages = [{"role": "user", "content": f"Translate into: {language}\n\n{kb_markdown}"}]
    completion = client.complete(system, messages, Translation.model_json_schema())
    return Translation.model_validate_json(completion.text).text


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m onboarding.draft", description=__doc__.split("\n")[0])
    parser.add_argument("--session", required=True)
    parser.add_argument("--model", default="claude-sonnet-5-5")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--review-language", help="also write a translated copy for review, e.g. el")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    session = SESSIONS / f"{args.session}.json"
    if not session.exists():
        raise SystemExit(f"no interview found at {session}")
    client = make_client(args.model, args.effort, max_tokens=DRAFT_MAX_TOKENS)
    interview = Interview.load(session, client)
    if not interview.done:
        print("Note: this interview isn't finished; the draft will list what's missing as open questions.")

    result = draft_kb(interview, client)
    DRAFTS.mkdir(parents=True, exist_ok=True)
    path = DRAFTS / f"{args.session}.md"
    path.write_text(result.kb_markdown, encoding="utf-8")
    print(f"Draft written to {path} ({len(parse_kb(result.kb_markdown).entries)} entries)")
    if result.open_questions:
        print("\nOpen questions for the owner:")
        for q in result.open_questions:
            print(f"- {q}")

    if args.review_language:
        translated = translate_kb(result.kb_markdown, args.review_language, client)
        review = DRAFTS / f"{args.session}.{args.review_language}.md"
        note = ("<!-- Translation for review only. The receptionist uses the English file; "
                "send corrections to be made there. -->\n\n")
        review.write_text(note + translated, encoding="utf-8")
        print(f"\nTranslated copy for review: {review}")


if __name__ == "__main__":
    main()
