from pathlib import Path

import pytest

from brain.kb import KBError, Visibility, load_kb, parse_kb

ROOT = Path(__file__).resolve().parent.parent

SAMPLE = """---
business: Example Co
currency: EUR
---

# Example KB

## Basics

### hours
**Visibility:** public · **Status:** confirmed

Open 9 to 5.

Closed on Sundays.

### hours-internal
**Visibility:** internal · **Status:** placeholder

Don't promise holiday hours.

---

## More

### prices
**Visibility:** public · **Status:** confirmed

Everything is €1.
"""


def test_parses_metadata_entries_and_bodies():
    kb = parse_kb(SAMPLE)
    assert kb.metadata == {"business": "Example Co", "currency": "EUR"}
    assert list(kb.entries) == ["hours", "hours-internal", "prices"]
    assert kb.entries["hours"].text == "Open 9 to 5.\n\nClosed on Sundays."
    assert kb.entries["hours-internal"].visibility is Visibility.INTERNAL
    assert kb.entries["hours-internal"].status == "placeholder"
    assert kb.entries["prices"].text == "Everything is €1."  # stops at the '---' and '##' before it
    assert kb.text == SAMPLE  # the model gets the file unchanged


def test_is_public():
    kb = parse_kb(SAMPLE)
    assert kb.is_public("hours")
    assert not kb.is_public("hours-internal")
    assert not kb.is_public("does-not-exist")


@pytest.mark.parametrize(
    "broken, message",
    [
        (SAMPLE.replace("### prices", "### hours"), "duplicate"),
        (SAMPLE.replace("**Visibility:** public · **Status:** confirmed\n\nEverything", "Everything"), "Visibility"),
        (SAMPLE.replace("internal ·", "secret ·"), "unknown visibility"),
        ("# Empty\n\nNo entries here.", "no entries"),
        ("---\nbusiness: X\n\n### a\n", "front matter"),
    ],
)
def test_malformed_kb_fails_loudly(broken, message):
    with pytest.raises(KBError, match=message):
        parse_kb(broken)


def test_the_real_kb_parses():
    kb = load_kb(ROOT / "kb" / "the-plug.md")
    assert len(kb.entries) > 50
    assert any(e.visibility is Visibility.INTERNAL for e in kb.entries.values())
