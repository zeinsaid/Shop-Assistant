"""Language blocks in the brain prompt follow the KB's `languages:` front matter."""

import pytest

from brain.brain import Brain, render_blocks
from brain.kb import parse_kb
from brain.llm import DryRunClient


def _kb(languages: str | None):
    front = f"languages: {languages}\n" if languages else ""
    return parse_kb(f"---\nbusiness: Test\n{front}---\n\n### hello\n**Visibility:** public · **Status:** confirmed\n\nHi.\n")


def test_language_notes_follow_the_kb_languages():
    greek = Brain(_kb("en, el"), DryRunClient()).system
    arabic = Brain(_kb("en, ar"), DryRunClient()).system
    plain = Brain(_kb(None), DryRunClient()).system
    assert "Greeklish" in greek and "Arabizi" not in greek
    assert "Arabizi" in arabic and "Greeklish" not in arabic
    assert "Greeklish" not in plain and "Arabizi" not in plain
    for system in (greek, arabic, plain):
        assert "<!--" not in system
        assert "reply in the language the customer wrote in" in system


def test_kb_languages_fall_back_to_the_default_language():
    kb = parse_kb("---\nbusiness: Test\ndefault_language: en\n---\n\n### hello\n**Visibility:** public · **Status:** confirmed\n\nHi.\n")
    assert kb.languages == ["en"]
    assert _kb("EN, ar ").languages == ["en", "ar"]


def test_unknown_prompt_blocks_are_a_mistake():
    with pytest.raises(KeyError):
        render_blocks("<!-- if mystery -->\nx\n<!-- end -->\n", {})
