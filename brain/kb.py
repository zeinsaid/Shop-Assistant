"""Load a knowledge base: the markdown the model reads, plus an index of its entries for code checks.

The model gets the file as-is. Code needs structure (which IDs exist, which are public) to enforce
D-003 and D-013, so the file is also parsed here. The format is generic (D-001):

    ### entry-id
    **Visibility:** public · **Status:** confirmed

    Entry text...
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class KBError(ValueError):
    """The knowledge base file doesn't follow the expected format."""


class Visibility(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"


@dataclass(frozen=True)
class KBEntry:
    id: str
    visibility: Visibility
    status: str
    text: str


@dataclass(frozen=True)
class KnowledgeBase:
    text: str  # the full markdown, exactly as given to the model
    metadata: dict[str, str]  # front matter (business name, currency, ...)
    entries: dict[str, KBEntry]  # by ID, in file order

    def is_public(self, entry_id: str) -> bool:
        entry = self.entries.get(entry_id)
        return entry is not None and entry.visibility is Visibility.PUBLIC


HEADING = re.compile(r"^### (\S+)\s*$")
META = re.compile(r"^\*\*Visibility:\*\*\s*(\w+)\s*·\s*\*\*Status:\*\*\s*(\w+)\s*$")


def load_kb(path: str | Path) -> KnowledgeBase:
    return parse_kb(Path(path).read_text(encoding="utf-8"))


def parse_kb(text: str) -> KnowledgeBase:
    lines = text.splitlines()
    metadata, start = _parse_front_matter(lines)
    entries: dict[str, KBEntry] = {}

    i = start
    while i < len(lines):
        heading = HEADING.match(lines[i])
        if not heading:
            i += 1
            continue
        entry_id = heading.group(1)
        if entry_id in entries:
            raise KBError(f"duplicate entry ID: {entry_id}")

        i += 1
        while i < len(lines) and not lines[i].strip():  # blank lines before the meta line
            i += 1
        meta = META.match(lines[i]) if i < len(lines) else None
        if not meta:
            raise KBError(f"entry {entry_id}: expected a '**Visibility:** ... · **Status:** ...' line")
        try:
            visibility = Visibility(meta.group(1))
        except ValueError:
            raise KBError(f"entry {entry_id}: unknown visibility '{meta.group(1)}'") from None

        # The body runs until the next heading of any level or a '---' separator.
        body_start = i = i + 1
        while i < len(lines) and not lines[i].startswith("#") and lines[i].strip() != "---":
            i += 1
        body = "\n".join(lines[body_start:i]).strip()
        entries[entry_id] = KBEntry(entry_id, visibility, meta.group(2), body)

    if not entries:
        raise KBError("no entries found")
    return KnowledgeBase(text=text, metadata=metadata, entries=entries)


def _parse_front_matter(lines: list[str]) -> tuple[dict[str, str], int]:
    """Parse simple 'key: value' front matter between '---' lines. Returns (metadata, next line)."""
    if not lines or lines[0].strip() != "---":
        return {}, 0
    metadata = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return metadata, i + 1
        key, sep, value = line.partition(":")
        if sep:
            metadata[key.strip()] = value.strip()
    raise KBError("front matter is not closed with '---'")
