"""Shared result type returned by all pipeline apply services."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class MergedMention:
    """
    An extracted mention that apply resolved to an individual that already existed.

    Attributes:
        mention_label: The mention's surface text as extracted
        individual_id: The pre-existing individual it was merged into
        source: Why it merged — ``"decision"`` (reviewer chose merge),
            ``"recognition"`` (the recognizer matched it), or ``"existing_title"``
            (an individual with the same title already exists in the class; title
            uniqueness per class means a ``"separate"`` decision also lands here)
    """

    mention_label: str
    individual_id: str
    source: Literal["decision", "recognition", "existing_title"]


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
    individuals_recognized: int = 0
    external_references_created: int = 0
    external_references_skipped: int = 0
    created_class_ids: list[str] = field(default_factory=list)
    created_individual_ids: list[str] = field(default_factory=list)
    created_relationship_ids: list[str] = field(default_factory=list)
    created_property_definition_ids: list[str] = field(default_factory=list)
    created_external_reference_ids: list[str] = field(default_factory=list)
    created_taxonomy_ids: list[str] = field(default_factory=list)
    recognized_individual_ids: list[str] = field(default_factory=list)
    # Per-candidate outcomes (ids from domain.pipelines.candidate_ids). Applied: the
    # candidate was selected and materialized (created, or already present). Skipped:
    # not selected, below threshold, or could not be materialized.
    applied_candidate_ids: list[str] = field(default_factory=list)
    skipped_candidate_ids: list[str] = field(default_factory=list)
    merged_mentions: list[MergedMention] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate that all counts match their corresponding ID list lengths."""
        if self.classes_created != len(self.created_class_ids):
            raise ValueError(
                f"classes_created ({self.classes_created}) and "
                f"created_class_ids ({len(self.created_class_ids)} items) "
                "must be consistent"
            )
        if self.individuals_created != len(self.created_individual_ids):
            raise ValueError(
                f"individuals_created ({self.individuals_created}) and "
                f"created_individual_ids ({len(self.created_individual_ids)} "
                "items) must be consistent"
            )
        if self.individuals_recognized != len(self.recognized_individual_ids):
            raise ValueError(
                f"individuals_recognized ({self.individuals_recognized}) and "
                f"recognized_individual_ids ({len(self.recognized_individual_ids)} "
                "items) must be consistent"
            )
        if self.relationships_created != len(self.created_relationship_ids):
            raise ValueError(
                f"relationships_created ({self.relationships_created}) and "
                f"created_relationship_ids "
                f"({len(self.created_relationship_ids)} items) must be "
                "consistent"
            )
        if self.properties_created != len(self.created_property_definition_ids):
            raise ValueError(
                f"properties_created ({self.properties_created}) and "
                f"created_property_definition_ids "
                f"({len(self.created_property_definition_ids)} items) must be "
                "consistent"
            )
        both = set(self.applied_candidate_ids) & set(self.skipped_candidate_ids)
        if both:
            raise ValueError(f"candidates cannot be both applied and skipped: {sorted(both)}")
        if self.external_references_created != len(self.created_external_reference_ids):
            raise ValueError(
                f"external_references_created "
                f"({self.external_references_created}) and "
                f"created_external_reference_ids "
                f"({len(self.created_external_reference_ids)} items) must be "
                "consistent"
            )
