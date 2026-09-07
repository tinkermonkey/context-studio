"""
SQLite-backed IndividualVectorIndex: vector search over graph individuals.

The recognition counterpart to SqliteSchemaVectorIndex. An individual's title
embedding lives as a column ON ontology_entities (node_type='individual',
`title_embedding`), searched through the same SQLAlchemy session — no separate
vector store. Similarity is brute-force cosine in numpy, isolated in `_cosine`
so a sqlite-vec backend can replace it later. Individuals are embedded on their
TITLE only: a freshly-extracted instance is identified by its name, not a curated
definition (the definition-driven idea applies to schema, not instances).

Unlike schema search — which matches a specific instance to a generic class and
is deliberately generous — recognition matches a specific mention to a specific
existing individual, scoped to candidate classes, and is used with a high
threshold + ambiguity margin by the caller to avoid false merges.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from adapters.persistence.sqlite.mappers import (
    _deserialize_embedding,
    _serialize_embedding,
)
from adapters.persistence.sqlite.models import IndividualClass, OntologyEntity
from domain.ontology.ports import EmbeddingService, IndividualMatch, IndividualVectorIndex
from utils.logger import get_logger

logger = get_logger(__name__)

_INDIVIDUAL = "individual"


class SqliteIndividualVectorIndex(IndividualVectorIndex):
    """SQLite adapter implementing the IndividualVectorIndex port."""

    def __init__(self, session_factory, embedding_service: EmbeddingService) -> None:
        self._session_factory = session_factory
        self._embedding = embedding_service

    def index_individual(self, individual_id: str, title: str, description: str | None) -> None:
        """Embed one individual's title and persist the vector (idempotent)."""
        vec = self._embedding.embed(title) if title and title.strip() else None
        with self._session_factory() as session:
            row = session.get(OntologyEntity, individual_id)
            if row is None or row.node_type != _INDIVIDUAL:
                logger.warning(
                    "index_individual requested for id=%s but no such individual "
                    "was found; nothing indexed.",
                    individual_id,
                )
                return
            row.title_embedding = _serialize_embedding(vec)
            row.is_indexed = vec is not None
            session.commit()

    def remove_individual(self, individual_id: str) -> None:
        """Drop an individual from the recognition index."""
        with self._session_factory() as session:
            row = session.get(OntologyEntity, individual_id)
            if row is not None:
                row.is_indexed = False
                row.title_embedding = None
                session.commit()

    def reindex_all_individuals(self) -> int:
        """Backfill: (re)embed and index every individual; returns the count indexed."""
        count = 0
        with self._session_factory() as session:
            rows = (
                session.query(OntologyEntity)
                .filter(OntologyEntity.node_type == _INDIVIDUAL)
                .all()
            )
            for row in rows:
                vec = self._embedding.embed(row.title) if row.title and row.title.strip() else None
                row.title_embedding = _serialize_embedding(vec)
                row.is_indexed = vec is not None
                if vec is not None:
                    count += 1
            session.commit()
        return count

    def search(
        self,
        query_embedding: list[float],
        class_ids: Sequence[str],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> list[IndividualMatch]:
        """Find indexed individuals similar to the query, scoped to candidate classes."""
        query = np.asarray(query_embedding, dtype=np.float32)
        norm = float(np.linalg.norm(query))
        if norm == 0.0:
            return []
        query = query / norm

        class_ids = list(class_ids)
        matches: list[IndividualMatch] = []
        with self._session_factory() as session:
            entity_query = session.query(
                OntologyEntity.id,
                OntologyEntity.title,
                OntologyEntity.description,
                OntologyEntity.title_embedding,
            ).filter(
                OntologyEntity.node_type == _INDIVIDUAL,
                OntologyEntity.is_indexed.is_(True),
            )
            if class_ids:
                entity_query = (
                    entity_query.join(
                        IndividualClass, IndividualClass.individual_id == OntologyEntity.id
                    )
                    .filter(IndividualClass.class_id.in_(class_ids))
                    .distinct()
                )
            for entity_id, title, description, title_blob in entity_query.all():
                score = self._cosine(query, title_blob)
                if score is None or score < threshold:
                    continue
                matches.append(
                    IndividualMatch(
                        individual_id=str(entity_id),
                        class_ids=self._class_ids_of(session, str(entity_id)),
                        title=title or "",
                        score=score,
                        description=description,
                    )
                )
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:top_k]

    @staticmethod
    def _cosine(query_norm: np.ndarray, blob: bytes | None) -> float | None:
        """Cosine similarity of the query (already unit-normed) against a stored title vector."""
        values = _deserialize_embedding(blob)
        if not values:
            return None
        vec = np.asarray(values, dtype=np.float32)
        if vec.shape != query_norm.shape:
            return None
        vec_norm = float(np.linalg.norm(vec))
        if vec_norm == 0.0:
            return None
        return float(np.dot(query_norm, vec / vec_norm))

    @staticmethod
    def _class_ids_of(session, individual_id: str) -> list[str]:
        """The class ids the individual instantiates, in position order."""
        rows = (
            session.query(IndividualClass.class_id)
            .filter(IndividualClass.individual_id == individual_id)
            .order_by(IndividualClass.position)
            .all()
        )
        return [str(row[0]) for row in rows]
