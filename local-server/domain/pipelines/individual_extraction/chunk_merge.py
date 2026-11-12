"""
Merge triples extracted chunk by chunk into one list over the whole source.

Each chunk's triples carry provenance offsets into the chunk. Merging maps
them to the whole text (and to a page), then folds the same triple found in
several chunks into one, keeping every passage as evidence. A typing triple
(individual ``is_a`` class) is an individual candidate, so the same individual
of the same class found in several chunks becomes one candidate.

Individuals are matched by `individual_key` (#1575), so "screws (D)" and
"Screw", or "Moen Inc." and "Moen", are the same individual, shown by its
`preferred_label`.
"""

from __future__ import annotations

import copy
from typing import Any, Sequence

from domain.extraction.chunking import Chunk, page_of
from domain.pipelines.candidate_ids import mention_key
from domain.pipelines.individual_extraction.labels import individual_key, preferred_label


def merge_chunk_triples(
    chunk_triples: Sequence[tuple[Chunk, list[dict[str, Any]]]],
    page_starts: Sequence[int] | None = None,
) -> list[dict[str, Any]]:
    """
    Merge per-chunk triples into whole-text triples with every passage.

    Triples merge when their subject, predicate and object match after
    normalizing labels (individuals by `individual_key`). The merged triple is
    the first one found, with:

    - ``passages``: ``[{quote, start, end, page}]`` from every chunk it was
      found in, in the order found, offsets into the whole text
    - ``provenance``: ``{quote, start, end}`` of the first passage placed in
      the text, else of the first passage (whose offsets are then null)
    - ``confidence``: the highest of the merged triples
    - subject and object ``id``: taken from a later triple when the first had
      none (recognition found the existing node in another chunk)
    - ``near_matches``: the union of the merged triples' recognition near
      misses, best first (only when any had them)

    Every individual without an id, in any triple, takes its key's preferred
    label: a recognized individual's title when one with that key was
    recognized, else `preferred_label` of every label found with that key.

    Merged triples are in order of first appearance, so the positional
    candidate ids (``triple-{i}``) stay stable.

    Args:
        chunk_triples: Each chunk with the triples extracted from it
        page_starts: Offset at which each page starts, to number passage pages

    Returns:
        The merged triples
    """
    starts = list(page_starts or [])
    merged: dict[tuple, dict[str, Any]] = {}
    # Individual key -> (titles of recognized individuals, every label found)
    labels: dict[str, tuple[list[str], list[str]]] = {}
    for chunk, triples in chunk_triples:
        for triple in triples:
            _collect_labels(triple, labels)
            span = _whole_text_span(triple.get("provenance"), chunk)
            key = _triple_key(triple)
            item = merged.get(key)
            if item is None:
                item = copy.deepcopy(triple)
                item["provenance"] = span
                item["passages"] = []
                merged[key] = item
            else:
                item["confidence"] = max(
                    item.get("confidence") or 0.0, triple.get("confidence") or 0.0
                )
                if triple.get("near_matches"):
                    item["near_matches"] = _merge_near_matches(
                        item.get("near_matches") or [], triple["near_matches"]
                    )
                for role in ("subject", "object"):
                    # A chunk where recognition found the existing node supplies its id
                    node, other = item.get(role), triple.get(role)
                    if isinstance(node, dict) and isinstance(other, dict):
                        if not node.get("id") and other.get("id"):
                            node["id"] = other["id"]
            if span["quote"] is not None:
                passage = {**span, "page": _passage_page(span, chunk, starts)}
                if passage not in item["passages"]:
                    item["passages"].append(passage)

    for item in merged.values():
        _relabel(item, labels)
        if item["passages"]:
            placed = [p for p in item["passages"] if p["start"] is not None]
            first = (placed or item["passages"])[0]
            item["provenance"] = {key: first[key] for key in ("quote", "start", "end")}
    return list(merged.values())


def _whole_text_span(provenance: Any, chunk: Chunk) -> dict[str, Any]:
    """A chunk-relative provenance span as ``{quote, start, end}`` in the whole text."""
    provenance = provenance if isinstance(provenance, dict) else {}
    start, end = provenance.get("start"), provenance.get("end")
    return {
        "quote": provenance.get("quote"),
        "start": start + chunk.start if start is not None else None,
        "end": end + chunk.start if end is not None else None,
    }


def _passage_page(span: dict[str, Any], chunk: Chunk, page_starts: list[int]) -> int | None:
    """The page a passage is on; a quote without offsets is on the chunk's page if it has one."""
    if not page_starts:
        return None
    if span["start"] is not None:
        return page_of(span["start"], page_starts)
    return chunk.page_first if chunk.page_first == chunk.page_last else None


def _triple_key(triple: dict[str, Any]) -> tuple:
    """Identity of a triple across chunks: normalized subject, predicate and object."""
    subject = triple.get("subject") or {}
    predicate = triple.get("predicate") or {}
    obj = triple.get("object") or {}
    object_value = obj.get("label") if obj.get("kind") != "literal" else obj.get("value")
    return (
        subject.get("kind"),
        _node_key(subject.get("kind"), subject.get("label")),
        mention_key(str(predicate.get("label") or "")),
        obj.get("kind"),
        _node_key(obj.get("kind"), object_value),
    )


def _node_key(kind: Any, label: Any) -> str:
    """A subject or object label normalized: an individual's by `individual_key`."""
    text = str(label if label is not None else "")
    return individual_key(text) if kind == "individual" else mention_key(text)


def _individual_nodes(triple: dict[str, Any]) -> list[dict[str, Any]]:
    """A triple's subject and object that are individuals with a label."""
    return [
        node
        for node in (triple.get("subject"), triple.get("object"))
        if isinstance(node, dict) and node.get("kind") == "individual" and node.get("label")
    ]


def _collect_labels(triple: dict[str, Any], labels: dict[str, tuple[list[str], list[str]]]) -> None:
    """Note a triple's individual labels under their key, a recognized one's as a title."""
    for node in _individual_nodes(triple):
        label = str(node["label"])
        titles, found = labels.setdefault(individual_key(label), ([], []))
        found.append(label)
        if node.get("id"):
            titles.append(label)


def _relabel(item: dict[str, Any], labels: dict[str, tuple[list[str], list[str]]]) -> None:
    """Give a merged triple's unrecognized individuals their key's preferred label."""
    for node in _individual_nodes(item):
        if node.get("id"):
            continue  # a recognized individual keeps its title
        titles, found = labels[individual_key(str(node["label"]))]
        node["label"] = titles[0] if titles else preferred_label(found)


def _merge_near_matches(first: list[dict], second: list[dict]) -> list[dict]:
    """Union near matches by entity id, keeping each one's best similarity, best first."""
    best: dict[str, dict] = {}
    for match in [*first, *second]:
        current = best.get(match["entity_id"])
        if current is None or match["similarity"] > current["similarity"]:
            best[match["entity_id"]] = dict(match)
    return sorted(best.values(), key=lambda match: match["similarity"], reverse=True)
