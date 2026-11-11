"""
Operations planned from an extraction run's candidates on a source (#1552),
shared by the individual and schema planners: the planned operation, and the
evidence and probability each candidate carries.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from domain.extraction.chunking import page_of
from domain.versioning.proposal_service import OperationDraft
from domain.versioning.provenance import SOURCE_ID


@dataclass
class PlannedOperation:
    """
    One operation planned from a run's candidates.

    Attributes:
        draft: The operation as proposed
        label: What it is, for reporting a refusal ("Whirlpool", "Whirlpool made_by Acme")
        needs: The refs of the creates it points at; refusing one drops it too
    """

    draft: OperationDraft
    label: str
    needs: frozenset[str] = frozenset()


@dataclass
class OperationPlan:
    """
    A run's candidates planned as operations.

    Attributes:
        operations: In seq order
        skipped: Candidates that became no operation, each {"label", "reason"}
    """

    operations: list[PlannedOperation] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)

    def skip(self, label: str, reason: str) -> None:
        self.skipped.append({"label": label, "reason": reason})


def passage_evidence(
    spans: Sequence[Mapping[str, Any]], source_id: str, page_starts: Sequence[int]
) -> list[dict[str, Any]]:
    """
    Evidence items for a candidate's passages in a source.

    A passage placed in the text becomes {source_id, page, start, end, quote},
    its page numbered from 1 (taken from the passage, else from page_starts;
    null without pages). A quote that could not be placed keeps only its
    quote. Duplicates are dropped.

    Args:
        spans: {quote, start, end, page?} passages, offsets into the source's text
        source_id: The source
        page_starts: Offset at which each page starts
    """
    items: list[dict[str, Any]] = []
    for span in spans:
        quote = span.get("quote")
        quote = quote if isinstance(quote, str) and quote.strip() else None
        start, end = span.get("start"), span.get("end")
        if not _is_offset(start) or not _is_offset(end) or end < start:
            item: dict[str, Any] = {"quote": quote} if quote else {}
        else:
            page = span.get("page")
            if not _is_offset(page) and page_starts:
                page = page_of(start, page_starts)
            item = {
                SOURCE_ID: source_id,
                "page": page if _is_offset(page) and page >= 1 else None,
                "start": start,
                "end": end,
            }
            if quote:
                item["quote"] = quote
        if item and item not in items:
            items.append(item)
    return items


def merged_evidence(*groups: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evidence items of several candidates, without duplicates, in order."""
    items: list[dict[str, Any]] = []
    for group in groups:
        items.extend(item for item in group if item not in items)
    return items


def best_probability(*values: Any) -> float | None:
    """The highest confidence among values (non-numbers ignored), clamped to 0..1."""
    numbers = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return max(0.0, min(1.0, max(numbers))) if numbers else None


def _is_offset(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
