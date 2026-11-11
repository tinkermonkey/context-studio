"""
Provenance: the source passages behind applied entities.

An operation's evidence may locate a passage in a source: {source_id, page,
start, end, quote}, start and end being character offsets into the source's
text (end exclusive), page its page (when it has pages). When the operation
applies, each such passage becomes an EntitySource row for the entity it
created or changed (or the existing individual a near match resolved to), so
provenance outlives the extraction run. Reverting the proposal removes the
rows its operations wrote; removing the source keeps them.

`source_id` is a plain string, not a reference: sources are soft-deleted and
provenance must outlive them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence
from uuid import uuid4

SOURCE_ID = "source_id"
# The integer keys of a source passage: its page and character offsets.
OFFSET_KEYS = ("page", "start", "end")


@dataclass(frozen=True)
class EntitySource:
    """
    One source passage behind one entity, written when an operation applied.

    Attributes:
        entity_id: The individual, relationship or class
        entity_kind: Its kind ("individual", "relationship" or "class")
        source_id: The source the passage is in (kept when the source is removed)
        proposal_id: The proposal whose operation wrote it
        op_seq: That operation's seq
        start, end: Character offsets of the passage in the source's text (end exclusive)
        created_at: When it was written (timezone-aware)
        page: The page the passage is on, if the source has pages
        quote: The passage's text
        id: Unique id
    """

    entity_id: str
    entity_kind: str
    source_id: str
    proposal_id: str
    op_seq: int
    start: int
    end: int
    created_at: datetime
    page: int | None = None
    quote: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.end < self.start:
            raise ValueError("end must not be before start")


def _is_offset(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def evidence_problem(item: Any) -> str | None:
    """
    Why one evidence item is invalid, or None.

    An item is an object of text values ("quote", "url", "entity_id", ...). A
    source passage also has "source_id" (non-empty text) and "start" and "end"
    (non-negative integers, end not before start), and may have "page" (a
    non-negative integer or null); only a source passage has those integers.
    """
    if not isinstance(item, Mapping) or not all(isinstance(k, str) for k in item):
        return f"each evidence item must be an object, not {item!r}"
    passage = SOURCE_ID in item
    for key, value in item.items():
        if key in OFFSET_KEYS:
            if not passage:
                return f'evidence "{key}" needs a "source_id": {item!r}'
            if key == "page" and value is None:
                continue
            if not _is_offset(value):
                return f'evidence "{key}" must be a non-negative integer, not {value!r}'
        elif not isinstance(value, str):
            return (
                'each evidence value must be text ("quote", "url", "entity_id"; a source'
                f" passage's page, start and end are integers), not {key}={value!r}"
            )
    if not passage:
        return None
    if not item[SOURCE_ID].strip():
        return "evidence source_id must not be empty"
    missing = [k for k in ("start", "end") if k not in item]
    if missing:
        return f"a source passage needs {' and '.join(missing)}: {item!r}"
    if item["end"] < item["start"]:
        return f"a source passage's end ({item['end']}) is before its start ({item['start']})"
    return None


def source_passages(evidence: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The evidence items that locate a passage in a source."""
    return [item for item in evidence if isinstance(item, Mapping) and SOURCE_ID in item]


def entity_sources(
    evidence: Sequence[Mapping[str, Any]],
    entity_id: str,
    entity_kind: str,
    proposal_id: str,
    op_seq: int,
    created_at: datetime,
) -> list[EntitySource]:
    """One EntitySource per source passage in an applied operation's evidence."""
    return [
        EntitySource(
            entity_id=entity_id,
            entity_kind=entity_kind,
            source_id=item[SOURCE_ID],
            proposal_id=proposal_id,
            op_seq=op_seq,
            start=item["start"],
            end=item["end"],
            page=item.get("page"),
            quote=item.get("quote"),
            created_at=created_at,
        )
        for item in source_passages(evidence)
    ]
