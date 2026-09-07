"""
SQLite-backed SchemaVectorIndex: in-database vector search over schema entities.

Vector search is a first-class part of the persistence layer here: the title and
definition embeddings live as columns ON ontology_entities (kept in sync on
write), and search queries them through the same SQLAlchemy session as the
structured data — no separate vector store, no source-of-truth split.

The similarity compute is plain brute-force cosine in numpy, isolated in
``_best_score`` so a sqlite-vec (or custom SQL function) backend can replace it
later without touching the port, the storage, or callers. Brute force is
sub-millisecond at the current ontology scale, and the on-disk float32 blob
format (struct little-endian) is already byte-compatible with sqlite-vec's
``vec_f32`` — so that swap needs no data migration.
"""

from __future__ import annotations

from typing import Literal, cast

import numpy as np
from sqlalchemy import or_
from sqlalchemy.orm import aliased, sessionmaker

from adapters.persistence.sqlite.mappers import (
    _deserialize_embedding,
    _serialize_embedding,
)
from adapters.persistence.sqlite.models import OntologyEntity
from adapters.persistence.sqlite.models import Relationship as RelationshipORM
from domain.ontology.ports import EmbeddingService, MatchedField, SchemaKind, SchemaMatch
from utils.logger import get_logger

logger = get_logger(__name__)

# SchemaKind values that map directly to ontology_entities.node_type rows.
_ENTITY_KINDS = ("class", "property_definition", "individual")

# How a candidate's title-similarity and definition-similarity combine into its
# single reported score. This is an adapter-level knob only — the domain port is
# indifferent to it.
#   "max"                 — the higher of title/definition similarity wins
#                           (default; preserves prior behavior).
#   "definition_preferred" — the curated definition drives the match: when a
#                           usable definition embedding exists, its similarity is
#                           the score; otherwise fall back to the title.
MatchingMode = Literal["max", "definition_preferred"]

# One-time guard so a fully-stale index (every stored vector a different
# dimension after an embedding-model swap) surfaces a WARNING instead of
# silently returning no matches. Reset only matters for tests.
_dim_mismatch_warned = False


def _first_external_identifier(external_references: list | None) -> str | None:
    """
    The identifier of the entity's first external reference, or None.

    ``external_references`` is the raw JSON column value — a list of
    ``{source, identifier, uri, metadata}`` dicts. DR-imported entities carry
    exactly one (the spec node id, e.g. "motivation.goal"); selecting the first
    is unambiguous for them and a harmless best-effort for anything else.
    """
    if not external_references:
        return None
    first = external_references[0]
    if isinstance(first, dict):
        return first.get("identifier")
    return None


class SqliteSchemaVectorIndex:
    """
    Persistence-layer vector index over schema entities (ClusteringPort sibling).

    Args:
        session_factory: SQLAlchemy sessionmaker for the local.db, shared with the
            ontology repository so vectors and structured data are one store.
        embedding_service: Port used to embed entity text and keep the index in
            sync; the same model produces query embeddings at search time.
        matching_mode: How title- and definition-similarity combine into a
            candidate's score. Defaults to "max" (unchanged prior behavior).
            Pass "definition_preferred" to let the curated definition drive
            matches (see ``MatchingMode``).
    """

    def __init__(
        self,
        session_factory: sessionmaker,
        embedding_service: EmbeddingService,
        matching_mode: MatchingMode = "max",
    ) -> None:
        self._session_factory = session_factory
        self._embedding = embedding_service
        self._matching_mode = matching_mode

    # ---- maintenance -------------------------------------------------------

    def index_entity(self, entity_id: str, title: str, description: str | None) -> None:
        """Embed one entity's title/description and persist the two vectors."""
        title_vec = self._embedding.embed(title) if title and title.strip() else None
        def_vec = (
            self._embedding.embed(description) if description and description.strip() else None
        )
        with self._session_factory() as session:
            row = session.get(OntologyEntity, entity_id)
            if row is None:
                logger.warning(
                    "index_entity requested for entity_id=%s but no such entity was "
                    "found; nothing indexed.",
                    entity_id,
                )
                return
            row.title_embedding = _serialize_embedding(title_vec)
            row.definition_embedding = _serialize_embedding(def_vec)
            session.commit()

    def reindex_all(self) -> int:
        """
        Recompute embeddings for every class, property definition, and
        individual in one pass.

        Returns the number of entities (re)indexed. Used by the backfill script
        and to populate the index after the migration adds the columns.
        """
        with self._session_factory() as session:
            rows = (
                session.query(OntologyEntity)
                .filter(OntologyEntity.node_type.in_(_ENTITY_KINDS))
                .all()
            )
            if not rows:
                return 0
            titles = [cast(str, row.title) or "" for row in rows]
            descriptions = [cast("str | None", row.description) or "" for row in rows]
            title_vecs = self._embedding.embed_batch(titles)
            def_vecs = self._embedding.embed_batch(descriptions)
            for row, title_vec, def_vec, title, description in zip(
                rows, title_vecs, def_vecs, titles, descriptions
            ):
                row.title_embedding = _serialize_embedding(  # type: ignore[assignment]
                    title_vec if title.strip() else None
                )
                row.definition_embedding = _serialize_embedding(  # type: ignore[assignment]
                    def_vec if description.strip() else None
                )
            session.commit()
            return len(rows)

    # ---- search ------------------------------------------------------------

    def search(
        self,
        query_embedding: list[float],
        kinds,
        top_k: int = 20,
        threshold: float = 0.0,
        taxonomy_id: str | None = None,
        matching_mode: MatchingMode | None = None,
    ) -> list[SchemaMatch]:
        """Find schema entities whose title or definition is similar to the query."""
        query = np.asarray(query_embedding, dtype=np.float32)
        norm = float(np.linalg.norm(query))
        if norm == 0.0:
            return []
        query = query / norm

        kinds = list(kinds)
        matches: list[SchemaMatch] = []
        with self._session_factory() as session:
            entity_kinds = [k for k in kinds if k in _ENTITY_KINDS]
            if entity_kinds:
                entity_query = session.query(
                    OntologyEntity.id,
                    OntologyEntity.node_type,
                    OntologyEntity.title,
                    OntologyEntity.title_embedding,
                    OntologyEntity.definition_embedding,
                    OntologyEntity.external_references,
                    OntologyEntity.identifier,
                    OntologyEntity.canonical_predicate,
                ).filter(
                    OntologyEntity.node_type.in_(entity_kinds),
                    OntologyEntity.is_indexed.is_(True),
                )
                entity_query = self._scope_to_taxonomy(entity_query, taxonomy_id)
                for (
                    entity_id,
                    node_type,
                    title,
                    title_blob,
                    def_blob,
                    ext_refs,
                    identifier,
                    canonical_predicate,
                ) in entity_query.all():
                    match = self._build_match(
                        query,
                        str(entity_id),
                        node_type,
                        title,
                        title_blob,
                        def_blob,
                        threshold,
                        ext_refs,
                        identifier,
                        canonical_predicate,
                        matching_mode,
                    )
                    if match is not None:
                        matches.append(match)

            if "relationship" in kinds:
                # A relationship has no text of its own; match it via the
                # embeddings of the property definition that types it.
                relationship_query = (
                    session.query(
                        RelationshipORM.id,
                        OntologyEntity.title,
                        OntologyEntity.title_embedding,
                        OntologyEntity.definition_embedding,
                        OntologyEntity.external_references,
                        OntologyEntity.identifier,
                        OntologyEntity.canonical_predicate,
                    )
                    .join(
                        OntologyEntity,
                        RelationshipORM.property_definition_id == OntologyEntity.id,
                    )
                    .filter(OntologyEntity.is_indexed.is_(True))
                )
                relationship_query = self._scope_to_taxonomy(relationship_query, taxonomy_id)
                for (
                    rel_id,
                    title,
                    title_blob,
                    def_blob,
                    ext_refs,
                    identifier,
                    canonical_predicate,
                ) in relationship_query.all():
                    match = self._build_match(
                        query,
                        str(rel_id),
                        "relationship",
                        title,
                        title_blob,
                        def_blob,
                        threshold,
                        ext_refs,
                        identifier,
                        canonical_predicate,
                        matching_mode,
                    )
                    if match is not None:
                        matches.append(match)

        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:top_k]

    @staticmethod
    def _scope_to_taxonomy(query, taxonomy_id: str | None):
        """
        Restrict `query` (already selecting from/joined on OntologyEntity) to
        rows belonging to `taxonomy_id`, or return it unchanged if None.

        A class carries its own `taxonomy_id`. A property definition does not
        (see domain.ontology.entities.PropertyDefinition) — it is scoped via
        the taxonomy of its domain class instead, joined in here.
        """
        if taxonomy_id is None:
            return query
        domain_class = aliased(OntologyEntity)
        return query.outerjoin(
            domain_class, OntologyEntity.domain_class_id == domain_class.id
        ).filter(
            or_(
                OntologyEntity.taxonomy_id == taxonomy_id,
                domain_class.taxonomy_id == taxonomy_id,
            )
        )

    def _build_match(
        self,
        query_norm: np.ndarray,
        entity_id: str,
        kind: SchemaKind,
        title: str | None,
        title_blob: bytes | None,
        def_blob: bytes | None,
        threshold: float,
        external_references: list | None = None,
        identifier: str | None = None,
        canonical_predicate: str | None = None,
        matching_mode: MatchingMode | None = None,
    ) -> SchemaMatch | None:
        """Score one candidate's best field; None if below threshold or unembedded."""
        mode = matching_mode or self._matching_mode
        scored = self._best_score(query_norm, title_blob, def_blob, mode)
        if scored is None:
            return None
        score, matched_field = scored
        if score < threshold:
            return None
        return SchemaMatch(
            entity_id=entity_id,
            kind=kind,
            label=title or "",
            score=score,
            matched_field=matched_field,
            external_id=_first_external_identifier(external_references),
            identifier=identifier,
            predicate=canonical_predicate,
        )

    @staticmethod
    def _best_score(
        query_norm: np.ndarray,
        title_blob: bytes | None,
        def_blob: bytes | None,
        matching_mode: MatchingMode = "max",
    ) -> tuple[float, MatchedField] | None:
        """
        Cosine similarity of the query against the title and definition vectors,
        returning one score and the field that produced it. Cosine is clamped to
        [0, 1] (the SchemaMatch invariant; negative cosine means unrelated).

        Field selection depends on ``matching_mode``:
          - "max": the higher of the two usable scores wins (default).
          - "definition_preferred": the definition score is used whenever a
            usable definition embedding exists; only if it does not does the
            title score stand in. This lets the curated definition — not the
            title — drive the match, while keeping ``matched_field`` honest
            about which vector actually produced the returned score.

        This is the single point a sqlite-vec / SQL-native backend would replace.
        """
        title_score = SqliteSchemaVectorIndex._field_score(query_norm, title_blob)
        def_score = SqliteSchemaVectorIndex._field_score(query_norm, def_blob)

        if matching_mode == "definition_preferred":
            if def_score is not None:
                return (def_score, "definition")
            if title_score is not None:
                return (title_score, "title")
            return None

        # "max" (default): the higher-scoring field wins.
        best: tuple[float, MatchedField] | None = None
        for field, score in (("title", title_score), ("definition", def_score)):
            if score is None:
                continue
            if best is None or score > best[0]:
                best = (score, field)  # type: ignore[assignment]
        return best

    @staticmethod
    def _field_score(query_norm: np.ndarray, blob: bytes | None) -> float | None:
        """
        Clamped cosine similarity of the query against one stored vector, or None
        when the vector is absent, zero-norm, or of a stale dimension.
        """
        vec = _deserialize_embedding(blob)
        if not vec:
            return None
        candidate = np.asarray(vec, dtype=np.float32)
        # Skip stale-dimension vectors (e.g. after an embedding-model swap or
        # a truncated blob) rather than letting numpy raise mid-search. Warn
        # once so a fully-stale index (which would silently return no matches)
        # is diagnosable.
        if candidate.shape != query_norm.shape:
            global _dim_mismatch_warned
            if not _dim_mismatch_warned:
                logger.warning(
                    "Skipping stored embedding with stale dimension %s "
                    "(query dimension %s); the schema vector index likely needs "
                    "a reindex after an embedding-model change.",
                    candidate.shape,
                    query_norm.shape,
                )
                _dim_mismatch_warned = True
            return None
        candidate_norm = float(np.linalg.norm(candidate))
        if candidate_norm == 0.0:
            return None
        score = float(np.dot(query_norm, candidate / candidate_norm))
        return max(0.0, min(1.0, score))
