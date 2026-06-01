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
    created_taxonomy_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if (self.classes_created > 0) != bool(self.created_class_ids):
            raise ValueError(
                f"classes_created ({self.classes_created}) and created_class_ids ({len(self.created_class_ids)} items) must be consistent"
            )
        if (self.individuals_created > 0) != bool(self.created_individual_ids):
            raise ValueError(
                f"individuals_created ({self.individuals_created}) and created_individual_ids ({len(self.created_individual_ids)} items) must be consistent"
            )
        if (self.relationships_created > 0) != bool(self.created_relationship_ids):
            raise ValueError(
                f"relationships_created ({self.relationships_created}) and created_relationship_ids ({len(self.created_relationship_ids)} items) must be consistent"
            )
        if (self.properties_created > 0) != bool(self.created_property_definition_ids):
            raise ValueError(
                f"properties_created ({self.properties_created}) and created_property_definition_ids ({len(self.created_property_definition_ids)} items) must be consistent"
            )
        if (self.external_references_created > 0) != bool(
            self.created_external_reference_ids
        ):
            raise ValueError(
                f"external_references_created ({self.external_references_created}) and created_external_reference_ids ({len(self.created_external_reference_ids)} items) must be consistent"
            )
