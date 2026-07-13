"""
Domain-to-ORM mapping utilities for the Ontology Management bounded context.

Provides bidirectional conversion between domain entities (dataclasses) and
SQLAlchemy ORM models. Handles:
- Discriminator-based entity type routing
- JSON serialization/deserialization of nested value objects
- Timestamp conversion (UTC)
- Embedding vector handling
"""

import struct
from datetime import datetime
from typing import Any, Union, cast

from adapters.persistence.sqlite.models import (
    OntologyEntity,
)
from adapters.persistence.sqlite.models import (
    PropertyDefinition as PropertyDefinitionORM,
)
from adapters.persistence.sqlite.models import (
    Relationship as RelationshipORM,
)
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.ontology.value_objects import (
    DataPropertyValue,
    ExternalReference,
    LexicalSense,
    NodeType,
    OntologyMapping,
    Status,
)


def serialize_external_references(
    refs: list[ExternalReference],
) -> list[dict[str, Any]]:
    """
    Serialize ExternalReference value objects to JSON-compatible dicts.

    Args:
        refs: List of ExternalReference objects

    Returns:
        List of dicts with keys: source, identifier, uri, metadata
    """
    return [
        {
            "source": ref.source,
            "identifier": ref.identifier,
            "uri": ref.uri,
            "metadata": dict(ref.metadata) if ref.metadata else None,
        }
        for ref in refs
    ]


def deserialize_external_references(
    data: list[dict[str, Any]],
) -> list[ExternalReference]:
    """
    Deserialize JSON data to ExternalReference value objects.

    Args:
        data: List of dicts with keys: source, identifier, uri, metadata

    Returns:
        List of ExternalReference objects
    """
    if not data:
        return []

    result = []
    for item in data:
        ref = ExternalReference(
            source=item["source"],
            identifier=item["identifier"],
            uri=item.get("uri"),
            metadata=item.get("metadata"),
        )
        result.append(ref)
    return result


def serialize_lexical_senses(senses: list[LexicalSense]) -> list[dict[str, str]]:
    """
    Serialize LexicalSense value objects to JSON-compatible dicts.

    Args:
        senses: List of LexicalSense objects

    Returns:
        List of dicts with keys: label, language_code, sense_type
    """
    return [
        {
            "label": sense.label,
            "language_code": sense.language_code,
            "sense_type": sense.sense_type,
        }
        for sense in senses
    ]


def deserialize_lexical_senses(data: list[dict[str, str]]) -> list[LexicalSense]:
    """
    Deserialize JSON data to LexicalSense value objects.

    Args:
        data: List of dicts with keys: label, language_code, sense_type

    Returns:
        List of LexicalSense objects
    """
    if not data:
        return []

    return [
        LexicalSense(
            label=item["label"],
            language_code=item["language_code"],
            sense_type=item["sense_type"],
        )
        for item in data
    ]


def serialize_data_properties(props: list[DataPropertyValue]) -> list[dict[str, Any]]:
    """
    Serialize DataPropertyValue value objects to JSON-compatible dicts.

    Args:
        props: List of DataPropertyValue objects

    Returns:
        List of dicts with keys: property_identifier, value, datatype
    """
    return [
        {
            "property_identifier": prop.property_identifier,
            "value": prop.value,
            "datatype": prop.datatype,
        }
        for prop in props
    ]


def deserialize_data_properties(data: list[dict[str, Any]]) -> list[DataPropertyValue]:
    """
    Deserialize JSON data to DataPropertyValue value objects.

    Args:
        data: List of dicts with keys: property_identifier, value, datatype

    Returns:
        List of DataPropertyValue objects
    """
    if not data:
        return []

    return [
        DataPropertyValue(
            property_identifier=item["property_identifier"],
            value=item["value"],
            datatype=item.get("datatype"),
        )
        for item in data
    ]


def serialize_ontology_mapping(
    mapping: OntologyMapping | None,
) -> dict[str, str] | None:
    """
    Serialize OntologyMapping value object to JSON-compatible dict.

    Args:
        mapping: OntologyMapping object or None

    Returns:
        Dict with keys: source_id, target_id, mapping_type, or None
    """
    if mapping is None:
        return None

    return {
        "source_id": mapping.source_id,
        "target_id": mapping.target_id,
        "mapping_type": mapping.mapping_type,
    }


def deserialize_ontology_mapping(data: dict[str, str] | None) -> OntologyMapping | None:
    """
    Deserialize JSON data to OntologyMapping value object.

    Args:
        data: Dict with keys: source_id, target_id, mapping_type, or None

    Returns:
        OntologyMapping object or None
    """
    if data is None:
        return None

    return OntologyMapping(
        source_id=data["source_id"],
        target_id=data["target_id"],
        mapping_type=data["mapping_type"],
    )


def map_orm_to_domain(
    orm_entity: OntologyEntity,
) -> Union[Taxonomy, ConceptScheme, Class, PropertyDefinition]:
    """
    Convert an OntologyEntity ORM model to the appropriate domain entity type.

    Routes based on the node_type discriminator column.

    Args:
        orm_entity: SQLAlchemy ORM model instance

    Returns:
        Domain entity (Taxonomy, ConceptScheme, Class, or PropertyDefinition)

    Raises:
        NotImplementedError: If node_type is 'individual' — use _build_individual_from_orm() instead
        ValueError: If node_type is not recognized
    """
    entity_id = cast(str, orm_entity.id)
    entity_title = cast(str, orm_entity.title)
    entity_description = cast(str | None, orm_entity.description)
    entity_created_at = cast(datetime | None, orm_entity.created_at)
    entity_last_modified = cast(datetime | None, orm_entity.last_modified)
    entity_version = cast(int, orm_entity.version)

    entity_identifier = cast(str | None, orm_entity.identifier)
    entity_color = cast(str | None, orm_entity.color)
    fallback_id_slug = "x_" + entity_id.replace("-", "")[:8]

    if orm_entity.node_type == NodeType.TAXONOMY:
        return Taxonomy(
            id=entity_id,
            identifier=entity_identifier or fallback_id_slug,
            title=entity_title,
            description=entity_description,
            color=entity_color,
            created_at=entity_created_at,
            last_modified=entity_last_modified,
            version=entity_version,
            status=Status(cast(str, orm_entity.status)),
        )

    elif orm_entity.node_type == NodeType.CONCEPT_SCHEME:
        return ConceptScheme(
            id=entity_id,
            identifier=entity_identifier or fallback_id_slug,
            title=entity_title,
            description=entity_description,
            color=entity_color,
            created_at=entity_created_at,
            last_modified=entity_last_modified,
            version=entity_version,
            taxonomy_id=cast(str, orm_entity.taxonomy_id),
            status=Status(cast(str, orm_entity.status)),
        )

    elif orm_entity.node_type == NodeType.CLASS:
        return Class(
            id=entity_id,
            identifier=entity_identifier or fallback_id_slug,
            title=entity_title,
            description=entity_description,
            color=entity_color,
            created_at=entity_created_at,
            last_modified=entity_last_modified,
            version=entity_version,
            concept_scheme_id=cast(str, orm_entity.concept_scheme_id),
            taxonomy_id=cast(str, orm_entity.taxonomy_id),
            parent_class_id=cast(str | None, orm_entity.parent_class_id),
            structural_property_id=cast(str | None, orm_entity.structural_property_id),
            external_references=deserialize_external_references(
                cast(list[dict[str, Any]], orm_entity.external_references) or []
            ),
            lexical_senses=deserialize_lexical_senses(
                cast(list[dict[str, str]], orm_entity.lexical_senses) or []
            ),
            data_properties=deserialize_data_properties(
                cast(list[dict[str, Any]], orm_entity.data_properties) or []
            ),
            embedding=_deserialize_embedding(cast(bytes | None, orm_entity.embedding)),
            status=Status(cast(str, orm_entity.status)),
            source_run_id=cast(str | None, orm_entity.source_run_id),
        )

    elif orm_entity.node_type == NodeType.INDIVIDUAL:
        raise NotImplementedError(
            "Individual entities must be constructed via _build_individual_from_orm() "
            "in the repository to load class_ids from the IndividualClass join table. "
            "Direct ORM mapping is not supported for Individual entities."
        )

    elif orm_entity.node_type == NodeType.PROPERTY_DEFINITION:
        return PropertyDefinition(
            id=entity_id,
            title=entity_title,
            description=entity_description,
            canonical_predicate=cast(str | None, orm_entity.canonical_predicate),
            created_at=entity_created_at,
            last_modified=entity_last_modified,
            version=entity_version,
            identifier=cast(str, orm_entity.identifier),
            ontology_mapping=deserialize_ontology_mapping(
                cast(dict[str, str] | None, orm_entity.ontology_mapping)
            ),
            domain_class_id=cast(str | None, orm_entity.domain_class_id),
            range_class_id=cast(str | None, orm_entity.range_class_id),
            external_references=deserialize_external_references(
                cast(list[dict[str, Any]], orm_entity.external_references) or []
            ),
            is_relevant=cast(bool | None, orm_entity.is_relevant),
            lexical_senses=deserialize_lexical_senses(
                cast(list[dict[str, str]], orm_entity.lexical_senses) or []
            ),
            status=Status(cast(str, orm_entity.status)),
            source_run_id=cast(str | None, orm_entity.source_run_id),
        )

    else:
        raise ValueError(f"Unknown node_type: {orm_entity.node_type}")


def map_domain_to_orm(
    entity: Union[Taxonomy, ConceptScheme, Class, Individual, PropertyDefinition],
) -> OntologyEntity:
    """
    Convert a domain entity to an OntologyEntity ORM model.

    Args:
        entity: Domain entity (Taxonomy, ConceptScheme, Class, Individual, or PropertyDefinition)

    Returns:
        SQLAlchemy OntologyEntity ORM model

    Raises:
        TypeError: If entity type is not recognized
    """
    common_args = {
        "id": entity.id,
        "title": entity.title,
        "description": entity.description,
        "created_at": entity.created_at,
        "last_modified": entity.last_modified,
        "version": entity.version,
        "status": entity.status.value,
    }

    if isinstance(entity, Taxonomy):
        return OntologyEntity(
            **common_args,
            node_type=NodeType.TAXONOMY,
            identifier=entity.identifier,
            color=entity.color,
        )

    elif isinstance(entity, ConceptScheme):
        return OntologyEntity(
            **common_args,
            node_type=NodeType.CONCEPT_SCHEME,
            taxonomy_id=entity.taxonomy_id,
            identifier=entity.identifier,
            color=entity.color,
        )

    elif isinstance(entity, Class):
        return OntologyEntity(
            **common_args,
            node_type=NodeType.CLASS,
            concept_scheme_id=entity.concept_scheme_id,
            taxonomy_id=entity.taxonomy_id,
            parent_class_id=entity.parent_class_id,
            structural_property_id=entity.structural_property_id,
            external_references=serialize_external_references(entity.external_references),
            lexical_senses=serialize_lexical_senses(entity.lexical_senses),
            data_properties=serialize_data_properties(entity.data_properties),
            embedding=_serialize_embedding(entity.embedding),
            source_run_id=entity.source_run_id,
            identifier=entity.identifier,
            color=entity.color,
        )

    elif isinstance(entity, Individual):
        return OntologyEntity(
            **common_args,
            node_type=NodeType.INDIVIDUAL,
            data_properties=serialize_data_properties(entity.data_properties),
            external_references=serialize_external_references(entity.external_references),
            source_run_id=entity.source_run_id,
        )

    elif isinstance(entity, PropertyDefinition):
        return OntologyEntity(
            **common_args,
            node_type=NodeType.PROPERTY_DEFINITION,
            identifier=entity.identifier,
            canonical_predicate=entity.canonical_predicate,
            ontology_mapping=serialize_ontology_mapping(entity.ontology_mapping),
            domain_class_id=entity.domain_class_id,
            range_class_id=entity.range_class_id,
            external_references=serialize_external_references(entity.external_references),
            is_relevant=entity.is_relevant,
            lexical_senses=serialize_lexical_senses(entity.lexical_senses),
            source_run_id=entity.source_run_id,
        )

    else:
        raise TypeError(f"Unknown entity type: {type(entity).__name__}")


def map_relationship_orm_to_domain(orm_rel: RelationshipORM) -> Relationship:
    """
    Convert a Relationship ORM model to a domain Relationship entity.

    Args:
        orm_rel: SQLAlchemy Relationship ORM model

    Returns:
        Domain Relationship entity
    """
    return Relationship(
        id=cast(str, orm_rel.id),
        source_id=cast(str, orm_rel.source_id),
        target_id=cast(str, orm_rel.target_id),
        property_definition_id=cast(str, orm_rel.property_definition_id),
        created_at=cast(datetime, orm_rel.created_at),
        source_run_id=cast(str | None, orm_rel.source_run_id),
    )


def map_relationship_domain_to_orm(rel: Relationship) -> RelationshipORM:
    """
    Convert a domain Relationship entity to an ORM model.

    Args:
        rel: Domain Relationship entity

    Returns:
        SQLAlchemy Relationship ORM model
    """
    return RelationshipORM(
        id=rel.id,
        source_id=rel.source_id,
        target_id=rel.target_id,
        property_definition_id=rel.property_definition_id,
        created_at=rel.created_at,
        source_run_id=rel.source_run_id,
    )


def map_property_definition_orm_to_domain(
    orm_prop: PropertyDefinitionORM,
) -> PropertyDefinition:
    """
    Convert a PropertyDefinition ORM model from the property_definitions table to domain entity.

    Note: The primary source of truth is the OntologyEntity with node_type='property_definition'.
    This is a convenience mapper for the specialized property_definitions table.

    external_references is not stored on the property_definitions table (only on
    ontology_entities), so it is always empty on the returned entity.

    Args:
        orm_prop: SQLAlchemy PropertyDefinition ORM model

    Returns:
        Domain PropertyDefinition entity
    """
    return PropertyDefinition(
        id=cast(str, orm_prop.id),
        identifier=cast(str, orm_prop.identifier),
        title=cast(str, orm_prop.title),
        description=cast(str | None, orm_prop.description),
        ontology_mapping=deserialize_ontology_mapping(
            cast(dict[str, str] | None, orm_prop.ontology_mapping)
        ),
        domain_class_id=cast(str | None, orm_prop.domain_class_id),
        range_class_id=cast(str | None, orm_prop.range_class_id),
        is_relevant=cast(bool | None, orm_prop.is_relevant),
        created_at=cast(datetime | None, orm_prop.created_at),
        last_modified=cast(datetime | None, orm_prop.last_modified),
        version=cast(int, orm_prop.version),
    )


def map_property_definition_domain_to_orm(
    prop: PropertyDefinition,
) -> PropertyDefinitionORM:
    """
    Convert a domain PropertyDefinition entity to an ORM model for the property_definitions table.

    Note: external_references has no column on the property_definitions table (only on
    ontology_entities), so it is not written by this mapper.

    Args:
        prop: Domain PropertyDefinition entity

    Returns:
        SQLAlchemy PropertyDefinition ORM model
    """
    return PropertyDefinitionORM(
        id=prop.id,
        identifier=prop.identifier,
        title=prop.title,
        description=prop.description,
        ontology_mapping=serialize_ontology_mapping(prop.ontology_mapping),
        domain_class_id=prop.domain_class_id,
        range_class_id=prop.range_class_id,
        is_relevant=prop.is_relevant,
        created_at=prop.created_at,
        last_modified=prop.last_modified,
        version=prop.version,
    )


def _serialize_embedding(embedding: list[float] | None) -> bytes | None:
    """Serialize embedding vector to bytes using struct packing."""
    if not embedding:
        return None
    return struct.pack(f"{len(embedding)}f", *embedding)


def _deserialize_embedding(data: bytes | None) -> list[float] | None:
    """Deserialize embedding vector from bytes using struct unpacking."""
    if not data:
        return None
    size = len(data) // 4
    return list(struct.unpack(f"{size}f", data))
