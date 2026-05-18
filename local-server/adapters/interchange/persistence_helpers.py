"""
Shared entity persistence logic for ontology deserialization adapters.

Provides helper functions for persisting incoming entities during import commits,
supporting all entity types (taxonomy, concept_scheme, class, individual,
property_definition, relationship).
"""

from typing import Any, Dict, List

from domain.interchange.value_objects import ResolutionKind
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.ontology.value_objects import ExternalReference
from utils.logger import get_logger

logger = get_logger(__name__)


def persist_incoming_entities(
    incoming_entities: Dict[str, Dict[str, Any]],
    resolution_map: Dict[str, ResolutionKind],
    ontology_repo,
    warnings: List[str],
) -> List[str]:
    """
    Persist incoming entities from an import, respecting resolution choices.

    For each incoming entity:
    - If it has SKIP resolution, skip it
    - If it has ABORT resolution, raise ValueError
    - Otherwise, persist the entity to the database

    Args:
        incoming_entities: Dict mapping entity_id to entity_dict with type and fields
        resolution_map: Dict mapping entity_id to ResolutionKind
        ontology_repo: Repository for persisting entities
        warnings: List to accumulate warning messages

    Returns:
        List of entity IDs that were successfully persisted

    Raises:
        ValueError: If an entity has ABORT resolution
    """
    affected_entity_ids = []

    for entity_id, entity_dict in incoming_entities.items():
        # Check if this entity should be skipped
        if entity_id in resolution_map:
            resolution = resolution_map[entity_id]
            if resolution == ResolutionKind.SKIP:
                continue
            if resolution == ResolutionKind.ABORT:
                raise ValueError(f"Import aborted per user resolution for entity {entity_id}")

        # Persist the entity based on its type
        entity_type = entity_dict.get("type")
        try:
            if entity_type == "class":
                _persist_class(entity_dict, incoming_entities, ontology_repo)
                affected_entity_ids.append(entity_id)
            elif entity_type == "concept_scheme":
                _persist_concept_scheme(entity_dict, ontology_repo)
                affected_entity_ids.append(entity_id)
            elif entity_type == "taxonomy":
                _persist_taxonomy(entity_dict, ontology_repo)
                affected_entity_ids.append(entity_id)
            elif entity_type == "individual":
                _persist_individual(entity_dict, ontology_repo)
                affected_entity_ids.append(entity_id)
            elif entity_type == "property_definition":
                _persist_property_definition(entity_dict, ontology_repo)
                affected_entity_ids.append(entity_id)
            elif entity_type == "relationship":
                _persist_relationship(entity_dict, ontology_repo)
                affected_entity_ids.append(entity_id)
            else:
                warning_msg = (
                    f"Entity type '{entity_type or 'unknown'}' not yet supported for" " persistence"
                )
                logger.warning(warning_msg)
                warnings.append(warning_msg)
        except Exception as e:
            warning_msg = (
                f"Failed to persist {entity_type or 'unknown'} entity {entity_id}:" f" {str(e)}"
            )
            logger.error(warning_msg)
            warnings.append(warning_msg)

    return affected_entity_ids


def _persist_class(
    entity_dict: Dict[str, Any],
    incoming_entities: Dict[str, Dict[str, Any]],
    ontology_repo,
) -> None:
    """Persist a Class entity."""
    concept_scheme_id = entity_dict.get("concept_scheme_id", "")
    taxonomy_id = ""
    if concept_scheme_id and concept_scheme_id in incoming_entities:
        concept_scheme = incoming_entities[concept_scheme_id]
        taxonomy_id = concept_scheme.get("taxonomy_id", "")

    class_entity = Class(
        id=entity_dict["id"],
        title=entity_dict["title"],
        description=entity_dict.get("description"),
        concept_scheme_id=concept_scheme_id,
        taxonomy_id=taxonomy_id,
        parent_class_id=entity_dict.get("parent_class_id"),
        external_references=[
            ExternalReference(
                source=ref["source"],
                identifier=ref["identifier"],
                uri=ref.get("uri"),
            )
            for ref in entity_dict.get("external_references", [])
        ],
    )
    ontology_repo.save_class(class_entity)


def _persist_concept_scheme(
    entity_dict: Dict[str, Any],
    ontology_repo,
) -> None:
    """Persist a ConceptScheme entity."""
    scheme = ConceptScheme(
        id=entity_dict["id"],
        title=entity_dict["title"],
        description=entity_dict.get("description"),
        taxonomy_id=entity_dict.get("taxonomy_id", ""),
    )
    ontology_repo.save_concept_scheme(scheme)


def _persist_taxonomy(
    entity_dict: Dict[str, Any],
    ontology_repo,
) -> None:
    """Persist a Taxonomy entity."""
    taxonomy = Taxonomy(
        id=entity_dict["id"],
        title=entity_dict["title"],
        description=entity_dict.get("description"),
    )
    ontology_repo.save_taxonomy(taxonomy)


def _persist_individual(
    entity_dict: Dict[str, Any],
    ontology_repo,
) -> None:
    """Persist an Individual entity."""
    class_ids = entity_dict.get("class_ids", [])
    if not class_ids:
        raise ValueError(f"Individual {entity_dict['id']} has no parent classes")

    individual = Individual(
        id=entity_dict["id"],
        title=entity_dict["title"],
        description=entity_dict.get("description"),
        class_ids=class_ids,
        external_references=[
            ExternalReference(
                source=ref["source"],
                identifier=ref["identifier"],
                uri=ref.get("uri"),
            )
            for ref in entity_dict.get("external_references", [])
        ],
    )
    ontology_repo.save_individual(individual)


def _persist_property_definition(
    entity_dict: Dict[str, Any],
    ontology_repo,
) -> None:
    """Persist a PropertyDefinition entity."""
    prop = PropertyDefinition(
        id=entity_dict["id"],
        identifier=entity_dict.get("identifier", ""),
        title=entity_dict["title"],
        description=entity_dict.get("description"),
        is_relevant=entity_dict.get("is_relevant"),
    )
    ontology_repo.save_property_definition(prop)


def _persist_relationship(
    entity_dict: Dict[str, Any],
    ontology_repo,
) -> None:
    """Persist a Relationship entity."""
    relationship = Relationship(
        id=entity_dict["id"],
        source_id=entity_dict["source_id"],
        target_id=entity_dict["target_id"],
        property_definition_id=entity_dict["property_definition_id"],
    )
    ontology_repo.save_relationship(relationship)
