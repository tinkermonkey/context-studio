"""
Stable candidate identity for pipeline run output.

Candidates are identified positionally within a run's ``output_summary``:

- ``triple-{i}``: index into ``output_summary["triples"]`` (individual extraction)
- ``class-{i}`` / ``property-{i}``: index within the ``kind``-filtered
  ``output_summary["candidates"]`` list (schema extraction)
- ``connection-{i}``: index into ``output_summary["connections"]`` (schema extraction)
- ``grounding-{i}`` / ``refinement-{i}``: index into the grounding / refinement list

Positions are numbered over the raw lists before any threshold filtering, so a
candidate keeps its id whether or not it is applied. Ids are stable because a
run's ``output_summary`` is written once when the run completes and is never
rewritten afterwards; the candidates GET endpoints and the apply services both
build ids here so they cannot drift apart.
"""

from __future__ import annotations

from typing import Any

SCHEMA_CANDIDATE_PREFIXES = {"class": "class", "property_definition": "property"}


def enumerate_items(items: list[dict] | None, prefix: str) -> list[tuple[str, dict]]:
    """Return ``(f"{prefix}-{i}", item)`` pairs for a raw candidate list."""
    return [(f"{prefix}-{i}", item) for i, item in enumerate(items or [])]


def enumerate_triples(output_summary: dict[str, Any] | None) -> list[tuple[str, dict]]:
    """Return ``(candidate_id, triple)`` pairs for an individual extraction run."""
    return enumerate_items((output_summary or {}).get("triples"), "triple")


def enumerate_schema_candidates(
    output_summary: dict[str, Any] | None,
) -> list[tuple[str, dict]]:
    """
    Return ``(candidate_id, candidate)`` pairs for schema class and property candidates.

    Candidates with an unrecognized ``kind`` get no id and are omitted.
    """
    candidates = (output_summary or {}).get("candidates") or []
    counters = {prefix: 0 for prefix in SCHEMA_CANDIDATE_PREFIXES.values()}
    result: list[tuple[str, dict]] = []
    for candidate in candidates:
        prefix = SCHEMA_CANDIDATE_PREFIXES.get(candidate.get("kind"))
        if prefix is None:
            continue
        result.append((f"{prefix}-{counters[prefix]}", candidate))
        counters[prefix] += 1
    return result


def enumerate_schema_connections(
    output_summary: dict[str, Any] | None,
) -> list[tuple[str, dict]]:
    """Return ``(candidate_id, connection)`` pairs for a schema extraction run."""
    return enumerate_items((output_summary or {}).get("connections"), "connection")


def mention_key(label: str | None) -> str:
    """
    Normalize an extracted mention label into its review/dedup key.

    Shared by recognition preview and apply so a reviewer's per-mention
    decision addresses exactly the mention the preview reported.
    """
    return (label or "").strip().lower()
