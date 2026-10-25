"""
Recognition preview for schema extraction runs.

Reports, per schema candidate, whether a matching schema entity already exists in
the target concept scheme — computed at request time with zero writes.

Two kinds of match are reported:

- ``exact``: the same rule apply uses to deduplicate (class title within the concept
  scheme, ignoring case, spaces, hyphens and underscores; property identifier;
  source+target+property relationship).
  These candidates are reused, not created, when the run is applied
  (``will_match_existing`` is True).
- ``vector`` (classes only, advisory): the proposed label is semantically close to
  the title of an existing class in the concept scheme. Apply still creates a new
  class, so ``will_match_existing`` is False; the reviewer decides whether the
  proposal duplicates the existing class. Mirrors individual recognition's
  conservative defaults: a high threshold, and no hint at all when a second class
  scores within the ambiguity margin of the best one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from domain.pipelines.candidate_ids import (
    enumerate_schema_candidates,
    enumerate_schema_connections,
)
from domain.pipelines.exceptions import PipelineInputError
from domain.pipelines.schema_extraction.apply_service import class_title_key, slugify

if TYPE_CHECKING:
    from domain.ontology.ports import EmbeddingService, OntologyRepository, SchemaVectorIndex

SchemaCandidateType = Literal["schema_class", "schema_property", "schema_connection"]
SchemaMatchMethod = Literal["exact", "vector"]

DEFAULT_VECTOR_THRESHOLD = 0.90
DEFAULT_AMBIGUITY_MARGIN = 0.05
_VECTOR_TOP_K = 5


@dataclass(frozen=True)
class SchemaRecognitionHit:
    """
    Whether one schema candidate matches an existing schema entity.

    Attributes:
        candidate_id: The candidate's stable id (``class-{i}``, ``property-{i}``,
            ``connection-{i}``)
        candidate_type: Which kind of schema candidate this is
        label: The candidate's label (``subject → predicate → object`` for connections)
        will_match_existing: True when apply reuses the existing entity instead of
            creating one (exact matches only)
        existing_entity_id: ID of the matched class, property definition or
            relationship, or None if no match
        existing_entity_title: Title of the matched entity, or None if no match
        match_method: ``exact``, ``vector`` or None
        match_score: Similarity of the match (1.0 for exact), or None if no match

    Raises:
        ValueError: If the match fields are inconsistent with each other
    """

    candidate_id: str
    candidate_type: SchemaCandidateType
    label: str
    will_match_existing: bool = False
    existing_entity_id: str | None = None
    existing_entity_title: str | None = None
    match_method: SchemaMatchMethod | None = None
    match_score: float | None = None

    def __post_init__(self) -> None:
        """Validate schema recognition hit invariants."""
        if self.match_score is not None and not 0.0 <= self.match_score <= 1.0:
            raise ValueError(f"match_score must be 0.0–1.0 or None, got {self.match_score}")
        if (self.match_method is None) != (self.existing_entity_id is None):
            raise ValueError("match_method and existing_entity_id must be set together")
        if self.will_match_existing and self.match_method != "exact":
            raise ValueError("will_match_existing requires an exact match")


class SchemaRecognitionPreviewService:
    """
    Previews which schema extraction candidates already exist in a concept scheme.

    Reads only, through the OntologyRepository port. The optional SchemaVectorIndex
    and EmbeddingService enable advisory vector hints for proposed classes; without
    them only exact matches are reported.
    """

    def __init__(
        self,
        ontology_repo: "OntologyRepository",
        schema_index: "SchemaVectorIndex | None" = None,
        embedding_service: "EmbeddingService | None" = None,
        vector_threshold: float = DEFAULT_VECTOR_THRESHOLD,
        ambiguity_margin: float = DEFAULT_AMBIGUITY_MARGIN,
    ) -> None:
        """
        Args:
            ontology_repo: Read access to classes, property definitions and relationships.
            schema_index: Optional vector index over schema entities.
            embedding_service: Embeds proposed class labels for vector search;
                required for vector hints alongside schema_index.
            vector_threshold: Minimum title similarity (0.0–1.0) for a vector hint.
            ambiguity_margin: A vector hint is withheld when another class scores
                within this many points of the best match.

        Raises:
            ValueError: If vector_threshold or ambiguity_margin is not 0.0–1.0
        """
        if not 0.0 <= vector_threshold <= 1.0:
            raise ValueError(f"vector_threshold must be 0.0–1.0, got {vector_threshold}")
        if not 0.0 <= ambiguity_margin <= 1.0:
            raise ValueError(f"ambiguity_margin must be 0.0–1.0, got {ambiguity_margin}")
        self._repo = ontology_repo
        self._schema_index = schema_index
        self._embedding = embedding_service
        self._vector_threshold = vector_threshold
        self._ambiguity_margin = ambiguity_margin

    def preview(
        self, output_summary: dict[str, Any] | None, concept_scheme_id: str
    ) -> list[SchemaRecognitionHit]:
        """
        Report one hit per class, property and connection candidate of a run.

        Args:
            output_summary: The schema extraction run's output_summary.
            concept_scheme_id: Concept scheme the run would be applied to.

        Returns:
            Hits in candidate order: classes and properties, then connections.

        Raises:
            PipelineInputError: If concept_scheme_id is empty or does not exist
        """
        if not concept_scheme_id:
            raise PipelineInputError("concept_scheme_id is required for schema recognition")
        scheme = self._repo.get_concept_scheme(concept_scheme_id)
        if scheme is None:
            raise PipelineInputError(f"Concept scheme {concept_scheme_id} not found")

        classes = self._repo.list_classes(concept_scheme_id=concept_scheme_id, limit=None)
        class_by_title = {class_title_key(c.title): c for c in classes}
        class_by_id = {c.id: c for c in classes}

        hits: list[SchemaRecognitionHit] = []
        for candidate_id, candidate in enumerate_schema_candidates(output_summary):
            label = (candidate.get("label") or "").strip()
            if candidate.get("kind") == "class":
                hits.append(
                    self._class_hit(
                        candidate_id, label, class_by_title, class_by_id, scheme.taxonomy_id
                    )
                )
            else:
                hits.append(self._property_hit(candidate_id, label))

        for candidate_id, connection in enumerate_schema_connections(output_summary):
            hits.append(self._connection_hit(candidate_id, connection, class_by_title))
        return hits

    def _class_hit(
        self,
        candidate_id: str,
        label: str,
        class_by_title: dict,
        class_by_id: dict,
        taxonomy_id: str,
    ) -> SchemaRecognitionHit:
        existing = class_by_title.get(class_title_key(label)) if label else None
        if existing is not None:
            return SchemaRecognitionHit(
                candidate_id=candidate_id,
                candidate_type="schema_class",
                label=label,
                will_match_existing=True,
                existing_entity_id=existing.id,
                existing_entity_title=existing.title,
                match_method="exact",
                match_score=1.0,
            )
        similar = self._similar_class(label, class_by_id, taxonomy_id) if label else None
        if similar is not None:
            cls, score = similar
            return SchemaRecognitionHit(
                candidate_id=candidate_id,
                candidate_type="schema_class",
                label=label,
                existing_entity_id=cls.id,
                existing_entity_title=cls.title,
                match_method="vector",
                match_score=score,
            )
        return SchemaRecognitionHit(
            candidate_id=candidate_id, candidate_type="schema_class", label=label
        )

    def _similar_class(self, label: str, class_by_id: dict, taxonomy_id: str):
        """Return (class, score) for a single clear title match in the scheme, else None."""
        if self._schema_index is None or self._embedding is None or not class_by_id:
            return None
        matches = self._schema_index.search(
            self._embedding.embed(label),
            kinds=["class"],
            top_k=_VECTOR_TOP_K,
            threshold=0.0,
            taxonomy_id=taxonomy_id,
        )
        # Only titles in the target scheme: a proposed class is compared to class
        # names, not to definitions that merely mention the same words.
        in_scheme = sorted(
            (m for m in matches if m.entity_id in class_by_id and m.matched_field == "title"),
            key=lambda m: m.score,
            reverse=True,
        )
        if not in_scheme or in_scheme[0].score < self._vector_threshold:
            return None
        best = in_scheme[0]
        if len(in_scheme) > 1 and best.score - in_scheme[1].score < self._ambiguity_margin:
            return None
        return class_by_id[best.entity_id], best.score

    def _property_hit(self, candidate_id: str, label: str) -> SchemaRecognitionHit:
        identifier = slugify(label)
        existing = (
            self._repo.get_property_definition_by_identifier(identifier) if identifier else None
        )
        if existing is None:
            return SchemaRecognitionHit(
                candidate_id=candidate_id, candidate_type="schema_property", label=label
            )
        return SchemaRecognitionHit(
            candidate_id=candidate_id,
            candidate_type="schema_property",
            label=label,
            will_match_existing=True,
            existing_entity_id=existing.id,
            existing_entity_title=existing.title,
            match_method="exact",
            match_score=1.0,
        )

    def _connection_hit(
        self, candidate_id: str, connection: dict, class_by_title: dict
    ) -> SchemaRecognitionHit:
        subject_ref = (connection.get("subject_ref") or "").strip()
        predicate = (connection.get("predicate") or "").strip()
        object_ref = (connection.get("object_ref") or "").strip()
        label = f"{subject_ref} → {predicate} → {object_ref}"
        no_match = SchemaRecognitionHit(
            candidate_id=candidate_id, candidate_type="schema_connection", label=label
        )

        source = class_by_title.get(class_title_key(subject_ref))
        target = class_by_title.get(class_title_key(object_ref))
        identifier = slugify(predicate)
        if source is None or target is None or not identifier:
            return no_match
        prop = self._repo.get_property_definition_by_identifier(identifier)
        if prop is None:
            return no_match
        existing = self._repo.list_relationships(
            source_id=source.id, target_id=target.id, property_id=prop.id, limit=1
        )
        if not existing:
            return no_match
        return SchemaRecognitionHit(
            candidate_id=candidate_id,
            candidate_type="schema_connection",
            label=label,
            will_match_existing=True,
            existing_entity_id=existing[0].id,
            existing_entity_title=f"{source.title} → {prop.title} → {target.title}",
            match_method="exact",
            match_score=1.0,
        )
