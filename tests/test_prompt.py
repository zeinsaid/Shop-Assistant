"""Checks on prompts/brain.md that don't need a model: it stays in sync with the schema and generic."""

import re
from pathlib import Path

from brain.schema import Action, BrainDecision

ROOT = Path(__file__).resolve().parent.parent
PROMPT = (ROOT / "prompts" / "brain.md").read_text(encoding="utf-8")


def test_prompt_mentions_every_action():
    for action in Action:
        assert f"`{action}`" in PROMPT, f"prompt never mentions {action}"


def test_prompt_mentions_every_decision_field_it_relies_on():
    for field in ("reasoning", "cited_entries", "question_for_owner"):
        assert field in BrainDecision.model_fields
        assert f"`{field}`" in PROMPT


def test_prompt_names_the_input_tags_brain_py_must_use():
    for tag in ("knowledge_base", "customer_message", "attachments"):
        assert f"<{tag}>" in PROMPT


def test_prompt_is_business_agnostic():
    # D-001: the business's name and details belong in the KB, not the prompt.
    kb = (ROOT / "kb" / "the-plug.md").read_text(encoding="utf-8")
    business = re.search(r"^business:\s*(.+)$", kb, re.M).group(1).strip()
    generic = {"the", "business", "center", "centre", "shop", "store", "company", "ltd"}
    distinctive = [w for w in business.lower().split() if w not in generic]
    assert distinctive, "no distinctive word in the business name to check"
    for word in distinctive:
        assert not re.search(rf"\b{re.escape(word)}\b", PROMPT.lower()), f"business name in prompt: {word}"
