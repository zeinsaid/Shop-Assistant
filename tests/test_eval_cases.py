"""Sanity checks on eval/questions.jsonl: every case is well-formed and consistent with the schema and KB.

Only the committed synthetic file is read. eval/real/ is never touched.
"""

import json
from pathlib import Path

import pytest

from brain.kb import load_kb
from brain.schema import Action, Attachment, Role, Turn
from eval.run_eval import ALWAYS_REPLY_FIELDS, for_setting

ROOT = Path(__file__).resolve().parent.parent


def load_cases() -> list[dict]:
    lines = (ROOT / "eval" / "questions.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


CASES = load_cases()
KB = load_kb(ROOT / "kb" / "the-plug.md")
KB_IDS = set(KB.entries)


def test_case_ids_are_unique():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("always_reply", [False, True], ids=["no_reply-allowed", "always-reply"])
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case_is_well_formed(case, always_reply):
    # Every case is checked as it applies on both kinds of channel (D-024).
    overrides = case.get("always_reply", {})
    assert set(overrides) <= ALWAYS_REPLY_FIELDS, f"can't override {set(overrides) - ALWAYS_REPLY_FIELDS}"
    if case["expected_action"] == "no_reply":
        assert overrides.get("expected_action", "no_reply") != "no_reply", (
            "a no_reply case needs an always_reply expectation: website chats reply to everything"
        )
    case = for_setting(case, always_reply)

    assert case["source"] == "synthetic", "only synthetic cases may be committed"
    assert Action(case["expected_action"])
    for attachment in case["attachments"]:
        Attachment(**attachment)  # metadata only (D-010)

    entries = case["expected_entries"]
    ids = {alt for e in entries for alt in e.split("|")}  # "a|b": either entry counts
    assert ids <= KB_IDS, f"unknown KB entries: {ids - KB_IDS}"
    if case["expected_action"] == "answer":
        assert entries, "an answer case must expect at least one citation"
        assert all(KB.is_public(e) for e in ids), "answers may only rely on public entries (D-020)"
    else:
        assert not entries, "only answer cases expect citations"

    if "expected_language" in case:
        languages = case["expected_language"]
        assert languages and all(isinstance(x, str) and x for x in languages)
    if "expected_amounts" in case:
        amounts = case["expected_amounts"]
        assert case["expected_action"] == "answer", "amounts are only checked on answers"
        assert amounts and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in amounts)
    if "must_not_contain" in case:
        phrases = case["must_not_contain"]
        assert phrases and all(isinstance(x, str) and x for x in phrases)
    if "question_must_contain" in case:
        phrases = case["question_must_contain"]
        assert case["expected_action"] == "ask_owner", "the owner question only exists on ask_owner"
        assert phrases and all(isinstance(x, str) and x for x in phrases)
    if "history" in case:
        turns = [Turn(**t) for t in case["history"]]  # same rules as the brain's input (D-023)
        assert turns, "leave history out rather than empty"
        assert any(t.role is Role.CUSTOMER for t in turns), "a conversation starts with the customer"
