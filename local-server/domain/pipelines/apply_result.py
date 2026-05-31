"""Shared result type returned by all pipeline apply services."""

from dataclasses import dataclass, field


@dataclass
class ApplyResult:
    """Counts and IDs of ontology entities created, modified, or skipped during a pipeline apply."""

    classes_created: int = 0
    classes_updated: int = 0
    classes_skipped: int = 0
    properties_created: int = 0
    properties_skipped: int = 0
    relationships_created: int = 0
    relationships_removed: int = 0
    relationships_modified: int = 0
    relationships_skipped: int = 0
    individuals_created: int = 0
    individuals_skipped: int = 0
    external_references_created: int = 0
    external_references_skipped: int = 0
    created_class_ids: list[str] = field(default_factory=list)
    created_individual_ids: list[str] = field(default_factory=list)
    created_relationship_ids: list[str] = field(default_factory=list)
    created_property_definition_ids: list[str] = field(default_factory=list)
    created_external_reference_ids: list[str] = field(default_factory=list)
