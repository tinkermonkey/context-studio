"""
Domain-to-ORM mapping utilities for the Ontology Management bounded context.

Provides bidirectional conversion between domain entities (dataclasses) and
SQLAlchemy ORM models. Handles:
- Discriminator-based entity type routing
- JSON serialization/deserialization of nested value objects
- Timestamp conversion (UTC)
- Embedding vector handling
"""

from typing import Union, Any
from datetime import datetime, timezone
import struct

from domain.ontology.entities import (
    Taxonomy,
    ConceptScheme,
    Class,
    Individual,
    Relationship,
    PropertyDefinition,
)
from domain.ontology.value_objects import (
    ExternalReference,
    LexicalSense,
    DataPropertyValue,
    OntologyMapping,
    NodeType,
)
from adapters.persistence.sqlite.models import (
    OntologyEntity,
    Relationship as RelationshipORM,
    PropertyDefinition as PropertyDefinitionORM,
)


def serialize_external_references(refs: list[ExternalReference]) -> list[dict[str, Any]]:
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


def deserialize_external_references(data: list[dict[str, Any]]) -> list[ExternalReference]:
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


def serialize_ontology_mapping(mapping: OntologyMapping | None) -> dict[str, str] | None:
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


def map_orm_to_domain(orm_entity: OntologyEntity) -> Union[Taxonomy, ConceptScheme, Class, Individual, PropertyDefinition]:
    """
    Convert an OntologyEntity ORM model to the appropriate domain entity type.

    Routes based on the node_type discriminator column.

    Args:
        orm_entity: SQLAlchemy ORM model instance

    Returns:
        Domain entity (Taxonomy, ConceptScheme, Class, Individual, or PropertyDefinition)

    Raises:
        ValueError: If node_type is not recognized
    """
    common_args = {
        "id": orm_entity.id,
        "title": orm_entity.title,
        "description": orm_entity.description,
        "created_at": orm_entity.created_at,
        "last_modified": orm_entity.last_modified,
        "version": orm_entity.version,
    }

    if orm_entity.node_type == NodeType.TAXONOMY:
        return Taxonomy(**common_args)

    elif orm_entity.node_type == NodeType.CONCEPT_SCHEME:
        return ConceptScheme(
            **common_args,
            taxonomy_id=orm_entity.taxonomy_id,
        )

    elif orm_entity.node_type == NodeType.CLASS:
        return Class(
            **common_args,
            concept_scheme_id=orm_entity.concept_scheme_id,
            taxonomy_id=orm_entity.taxonomy_id,
            parent_class_id=orm_entity.parent_class_id,
            structural_property_id=orm_entity.structural_property_id,
            external_references=deserialize_external_references(orm_entity.external_references or []),
            lexical_senses=deserialize_lexical_senses(orm_entity.lexical_senses or []),
            data_properties=deserialize_data_properties(orm_entity.data_properties or []),
            embedding=_deserialize_embedding(orm_entity.embedding),
        )

    elif orm_entity.node_type == NodeType.INDIVIDUAL:
        return Individual(
            **common_args,
            class_id=orm_entity.class_id,
            data_properties=deserialize_data_properties(orm_entity.data_properties or []),
            external_references=deserialize_external_references(orm_entity.external_references or []),
        )

    elif orm_entity.node_type == NodeType.PROPERTY_DEFINITION:
        return PropertyDefinition(
            **common_args,
            identifier=orm_entity.identifier,
            ontology_mapping=deserialize_ontology_mapping(orm_entity.ontology_mapping),
            is_relevant=orm_entity.is_relevant,
        )

    else:
        raise ValueError(f"Unknown node_type: {orm_entity.node_type}")


def map_domain_to_orm(
    entity: Union[Taxonomy, ConceptScheme, Class, Individual, PropertyDefinition]
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
    }

    if isinstance(entity, Taxonomy):
        return OntologyEntity(
            **common_args,
            node_type=NodeType.TAXONOMY,
        )

    elif isinstance(entity, ConceptScheme):
        return OntologyEntity(
            **common_args,
            node_type=NodeType.CONCEPT_SCHEME,
            taxonomy_id=entity.taxonomy_id,
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
        )

    elif isinstance(entity, Individual):
        return OntologyEntity(
            **common_args,
            node_type=NodeType.INDIVIDUAL,
            class_id=entity.class_id,
            data_properties=serialize_data_properties(entity.data_properties),
            external_references=serialize_external_references(entity.external_references),
        )

    elif isinstance(entity, PropertyDefinition):
        return OntologyEntity(
            **common_args,
            node_type=NodeType.PROPERTY_DEFINITION,
            identifier=entity.identifier,
            ontology_mapping=serialize_ontology_mapping(entity.ontology_mapping),
            is_relevant=entity.is_relevant,
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
        id=orm_rel.id,
        source_id=orm_rel.source_id,
        target_id=orm_rel.target_id,
        property_definition_id=orm_rel.property_definition_id,
        created_at=orm_rel.created_at,
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
    )


def map_property_definition_orm_to_domain(orm_prop: PropertyDefinitionORM) -> PropertyDefinition:
    """
    Convert a PropertyDefinition ORM model from the property_definitions table to domain entity.

    Note: The primary source of truth is the OntologyEntity with node_type='property_definition'.
    This is a convenience mapper for the specialized property_definitions table.

    Args:
        orm_prop: SQLAlchemy PropertyDefinition ORM model

    Returns:
        Domain PropertyDefinition entity
    """
    return PropertyDefinition(
        id=orm_prop.id,
        identifier=orm_prop.identifier,
        title=orm_prop.title,
        description=orm_prop.description,
        ontology_mapping=deserialize_ontology_mapping(orm_prop.ontology_mapping),
        is_relevant=orm_prop.is_relevant,
        created_at=orm_prop.created_at,
        last_modified=orm_prop.last_modified,
        version=orm_prop.version,
    )


def map_property_definition_domain_to_orm(prop: PropertyDefinition) -> PropertyDefinitionORM:
    """
    Convert a domain PropertyDefinition entity to an ORM model for the property_definitions table.

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
        is_relevant=prop.is_relevant,
        created_at=prop.created_at,
        last_modified=prop.last_modified,
        version=prop.version,
    )


def _serialize_embedding(embedding: list[float] | None) -> bytes | None:
    """Serialize embedding vector to bytes using struct packing."""
    if not embedding:
        return None
    return struct.pack(f'{len(embedding)}f', *embedding)


def _deserialize_embedding(data: bytes | None) -> list[float] | None:
    """Deserialize embedding vector from bytes using struct unpacking."""
    if not data:
        return None
    size = len(data) // 4
    return list(struct.unpack(f'{size}f', data))
