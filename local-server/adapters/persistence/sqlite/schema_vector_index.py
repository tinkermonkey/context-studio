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

import numpy as np
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.mappers import (
    _deserialize_embedding,
    _serialize_embedding,
)
from adapters.persistence.sqlite.models import OntologyEntity
from adapters.persistence.sqlite.models import Relationship as RelationshipORM
from domain.ontology.ports import EmbeddingService, MatchedField, SchemaKind, SchemaMatch

# SchemaKind values that map directly to ontology_entities.node_type rows.
_ENTITY_KINDS = ("class", "property_definition")


class SqliteSchemaVectorIndex:
    """
    Persistence-layer vector index over schema entities (ClusteringPort sibling).

    Args:
        session_factory: SQLAlchemy sessionmaker for the local.db, shared with the
            ontology repository so vectors and structured data are one store.
        embedding_service: Port used to embed entity text and keep the index in
            sync; the same model produces query embeddings at search time.
    """

    def __init__(self, session_factory: sessionmaker, embedding_service: EmbeddingService) -> None:
        self._session_factory = session_factory
        self._embedding = embedding_service

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
                return
            row.title_embedding = _serialize_embedding(title_vec)
            row.definition_embedding = _serialize_embedding(def_vec)
            session.commit()

    def reindex_all(self) -> int:
        """
        Recompute embeddings for every class and property definition in one pass.

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
            titles = [row.title or "" for row in rows]
            descriptions = [row.description or "" for row in rows]
            title_vecs = self._embedding.embed_batch(titles)
            def_vecs = self._embedding.embed_batch(descriptions)
            for row, title_vec, def_vec, description in zip(
                rows, title_vecs, def_vecs, descriptions
            ):
                row.title_embedding = _serialize_embedding(title_vec)
                row.definition_embedding = _serialize_embedding(
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
                rows = (
                    session.query(
                        OntologyEntity.id,
                        OntologyEntity.node_type,
                        OntologyEntity.title,
                        OntologyEntity.title_embedding,
                        OntologyEntity.definition_embedding,
                    )
                    .filter(
                        OntologyEntity.node_type.in_(entity_kinds),
                        OntologyEntity.is_indexed.is_(True),
                    )
                    .all()
                )
                for entity_id, node_type, title, title_blob, def_blob in rows:
                    match = self._build_match(
                        query, str(entity_id), node_type, title, title_blob, def_blob, threshold
                    )
                    if match is not None:
                        matches.append(match)

            if "relationship" in kinds:
                # A relationship has no text of its own; match it via the
                # embeddings of the property definition that types it.
                rows = (
                    session.query(
                        RelationshipORM.id,
                        OntologyEntity.title,
                        OntologyEntity.title_embedding,
                        OntologyEntity.definition_embedding,
                    )
                    .join(
                        OntologyEntity,
                        RelationshipORM.property_definition_id == OntologyEntity.id,
                    )
                    .filter(OntologyEntity.is_indexed.is_(True))
                    .all()
                )
                for rel_id, title, title_blob, def_blob in rows:
                    match = self._build_match(
                        query, str(rel_id), "relationship", title, title_blob, def_blob, threshold
                    )
                    if match is not None:
                        matches.append(match)

        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:top_k]

    def _build_match(
        self,
        query_norm: np.ndarray,
        entity_id: str,
        kind: SchemaKind,
        title: str | None,
        title_blob: bytes | None,
        def_blob: bytes | None,
        threshold: float,
    ) -> SchemaMatch | None:
        """Score one candidate's best field; None if below threshold or unembedded."""
        scored = self._best_score(query_norm, title_blob, def_blob)
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
        )

    @staticmethod
    def _best_score(
        query_norm: np.ndarray, title_blob: bytes | None, def_blob: bytes | None
    ) -> tuple[float, MatchedField] | None:
        """
        Cosine similarity of the query against the title and definition vectors,
        returning the higher score and which field won. Cosine is clamped to
        [0, 1] (the SchemaMatch invariant; negative cosine means unrelated).

        This is the single point a sqlite-vec / SQL-native backend would replace.
        """
        best: tuple[float, MatchedField] | None = None
        for field, blob in (("title", title_blob), ("definition", def_blob)):
            vec = _deserialize_embedding(blob)
            if not vec:
                continue
            candidate = np.asarray(vec, dtype=np.float32)
            # Skip stale-dimension vectors (e.g. after an embedding-model swap or
            # a truncated blob) rather than letting numpy raise mid-search.
            if candidate.shape != query_norm.shape:
                continue
            candidate_norm = float(np.linalg.norm(candidate))
            if candidate_norm == 0.0:
                continue
            score = float(np.dot(query_norm, candidate / candidate_norm))
            score = max(0.0, min(1.0, score))
            if best is None or score > best[0]:
                best = (score, field)  # type: ignore[assignment]
        return best
