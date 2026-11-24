"""
Pure functions over extracted triples and classes, shared by the extraction
service and the pipelines that run it (a module of its own, so another
context imports them without the service module; #1633).
"""

from __future__ import annotations

from typing import Any, Mapping

_TYPE_PREDICATE_LABELS = frozenset(
    {"is a", "is_a", "isa", "type", "rdf type", "instance of", "subclass of"}
)


def class_reference_aliases(cls) -> list[str]:
    """
    Every identifying string by which a typing triple may legitimately name a class.

    A class can be referenced by any of its external reference identifiers (a DR
    spec node id like "technology.node", a wikidata/dbpedia id, ...), by its own
    machine identifier ("crdt"), or by its human title ("Conflict-free Replicated
    Data Type"). Different source ontologies — and their graded ground truth —
    use different ones of these forms (the DR spec types by dotted node id; the
    canon slice's models emit the class title), so verification must recognize a
    class by any of them rather than a single canonical pick.
    """
    aliases: list[str] = []
    for reference in getattr(cls, "external_references", None) or []:
        identifier = getattr(reference, "identifier", None)
        if identifier:
            aliases.append(identifier)
    identifier = getattr(cls, "identifier", "") or ""
    if identifier:
        aliases.append(identifier)
    title = getattr(cls, "title", "") or ""
    if title:
        aliases.append(title)
    return aliases


def _normalize_predicate_label(label: str) -> str:
    """Lowercase a predicate label and fold underscores/hyphens to spaces for matching."""
    return label.strip().lower().replace("_", " ").replace("-", " ")


def is_below_confidence(triple: Mapping[str, Any], threshold: float) -> bool:
    """
    Whether a triple's confidence is under a threshold. A triple that gives no
    confidence (``None``, or none at all) is never under it: the threshold
    compares a score, and the extraction gave none, which is not a score of 0.
    The single call that finds and types individuals (single_call) rates none
    of them, so a threshold leaves its individuals in rather than dropping
    every one.
    """
    confidence = triple.get("confidence")
    if confidence is None:
        return False
    return float(confidence) < threshold


def is_typing_triple(triple: Mapping[str, Any]) -> bool:
    """
    Whether a triple is an ``is_a``/rdf:type assertion: its predicate label
    normalizes to a typing predicate ("is_a", "type", "instance of", ...) or its
    object is a class. Whatever ``property_definition_id`` the model put on it
    (the prompt's example shows one, so models send "is_a") doesn't matter.
    """
    predicate = triple.get("predicate") or {}
    obj = triple.get("object") or {}
    predicate_label = _normalize_predicate_label(str(predicate.get("label") or ""))
    return predicate_label in _TYPE_PREDICATE_LABELS or obj.get("kind") == "class"
