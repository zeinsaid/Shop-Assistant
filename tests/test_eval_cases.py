"""Sanity checks on eval/questions.jsonl: every case is well-formed and consistent with the schema and KB.

Only the committed synthetic file is read. eval/real/ is never touched.
"""

import json
import re
from pathlib import Path

import pytest

from brain.schema import Action, Attachment

ROOT = Path(__file__).resolve().parent.parent


def load_cases() -> list[dict]:
    lines = (ROOT / "eval" / "questions.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def load_kb_ids() -> set[str]:
    kb = (ROOT / "kb" / "the-plug.md").read_text(encoding="utf-8")
    return set(re.findall(r"^### (\S+)\s*$", kb, re.M))


CASES = load_cases()
KB_IDS = load_kb_ids()


def test_case_ids_are_unique():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case_is_well_formed(case):
    assert case["source"] == "synthetic", "only synthetic cases may be committed"
    assert Action(case["expected_action"])
    for attachment in case["attachments"]:
        Attachment(**attachment)  # metadata only (D-010)

    entries = case["expected_entries"]
    assert set(entries) <= KB_IDS, f"unknown KB entries: {set(entries) - KB_IDS}"
    if case["expected_action"] == "answer":
        assert entries, "an answer case must expect at least one citation"
    else:
        assert not entries, "only answer cases expect citations"

    if "expected_language" in case:
        languages = case["expected_language"]
        assert languages and all(isinstance(x, str) and x for x in languages)
    if "must_not_contain" in case:
        phrases = case["must_not_contain"]
        assert phrases and all(isinstance(x, str) and x for x in phrases)
