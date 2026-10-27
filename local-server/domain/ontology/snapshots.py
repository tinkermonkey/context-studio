"""
JSON-safe snapshots of ontology entities.

A deleted entity's change event stores its snapshot, and reverting the delete
rebuilds the entity from it with the same id and fields. The derived `embedding`
is left out: it is recomputed when the restored entity is re-indexed.
"""

from __future__ import annotations

from dataclasses import asdict, fields
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from domain.ontology.entities import (
    AttributeDefinition,
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.ontology.value_objects import (
    DataPropertyValue,
    DataType,
    ExternalReference,
    LexicalSense,
    OntologyMapping,
    Status,
)

_ENTITY_TYPES: dict[str, type] = {
    "taxonomy": Taxonomy,
    "concept_scheme": ConceptScheme,
    "class": Class,
    "individual": Individual,
    "relationship": Relationship,
    "property_definition": PropertyDefinition,
    "attribute_definition": AttributeDefinition,
}

_EXCLUDED_FIELDS = {"embedding"}


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


_DECODERS: dict[str, Callable[[Any], Any]] = {
    "status": Status,
    "datatype": DataType,
    "created_at": _parse_datetime,
    "last_modified": _parse_datetime,
    "external_references": lambda refs: [ExternalReference.from_dict(r) for r in refs],
    "lexical_senses": lambda senses: [LexicalSense(**s) for s in senses],
    "data_properties": lambda values: [DataPropertyValue(**v) for v in values],
    "ontology_mapping": lambda mapping: OntologyMapping(**mapping),
}


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ExternalReference):
        return value.to_dict()
    if isinstance(value, (LexicalSense, DataPropertyValue, OntologyMapping)):
        return asdict(value)
    if isinstance(value, list):
        return [_encode(item) for item in value]
    return value


def entity_snapshot(entity: Any) -> dict[str, Any]:
    """Return every field of an ontology entity as a JSON-safe dict."""
    return {
        f.name: _encode(getattr(entity, f.name))
        for f in fields(entity)
        if f.name not in _EXCLUDED_FIELDS
    }


def entity_field_names(entity_type: str) -> frozenset[str]:
    """
    The field names of an entity type ("class", "concept_scheme", ...).

    Raises:
        ValueError: If the entity type is unknown
    """
    entity_cls = _ENTITY_TYPES.get(entity_type)
    if entity_cls is None:
        raise ValueError(f"Unknown entity type: {entity_type}")
    return frozenset(f.name for f in fields(entity_cls))


def entity_from_snapshot(entity_type: str, snapshot: dict[str, Any], entity_id: str) -> Any:
    """
    Rebuild an ontology entity from its snapshot.

    Keys that are not fields of the entity are ignored, so an older, minimal
    snapshot restores whatever it carries; if it lacks a required field a
    ValueError says so.

    Raises:
        ValueError: If the entity type is unknown or a required field is missing
    """
    entity_cls = _ENTITY_TYPES.get(entity_type)
    if entity_cls is None:
        raise ValueError(f"Unknown entity type for snapshot: {entity_type}")
    kwargs: dict[str, Any] = {"id": entity_id}
    for f in fields(entity_cls):
        if f.name in _EXCLUDED_FIELDS or f.name not in snapshot:
            continue
        value = snapshot[f.name]
        decoder = _DECODERS.get(f.name)
        kwargs[f.name] = decoder(value) if decoder is not None and value is not None else value
    try:
        return entity_cls(**kwargs)
    except TypeError as exc:
        raise ValueError(
            f"Cannot restore {entity_type} {entity_id}: snapshot is incomplete ({exc})"
        ) from exc
