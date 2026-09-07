"""
In-memory fake IndividualVectorIndex for domain unit tests (issue #1142).

Deterministic and infra-free: stores individuals with a caller-supplied vector
map (or exact-title fallback) and does plain cosine, so recognition logic
(threshold, ambiguity margin, class scoping) can be unit-tested without a DB or
an embedding model.
"""

from __future__ import annotations

import math
from typing import Sequence

from domain.ontology.ports import IndividualMatch, IndividualVectorIndex


class FakeIndividualVectorIndex(IndividualVectorIndex):
    def __init__(self, vectors: dict[str, list[float]] | None = None, repo=None) -> None:
        # title -> vector, used to embed both stored titles and queries by title.
        self._vectors = vectors or {}
        # individual_id -> (title, class_ids, description)
        self._individuals: dict[str, tuple[str, list[str], str | None]] = {}
        # Optional OntologyRepository: when given, index_individual resolves
        # class_ids from the live entity (mirroring how the real SQLite-backed
        # index joins against persisted class associations at search time)
        # instead of requiring class_ids to be pre-seeded via add().
        self._repo = repo

    # --- test seeding helpers -------------------------------------------------
    def add(
        self,
        individual_id: str,
        title: str,
        class_ids: list[str],
        description: str | None = None,
    ) -> None:
        self._individuals[individual_id] = (title, list(class_ids), description)

    # --- IndividualVectorIndex port ------------------------------------------
    def index_individual(self, individual_id: str, title: str, description: str | None) -> None:
        if self._repo is not None:
            existing_entity = self._repo.get_individual(individual_id)
            class_ids = list(existing_entity.class_ids) if existing_entity else []
        else:
            existing = self._individuals.get(individual_id)
            class_ids = existing[1] if existing else []
        self._individuals[individual_id] = (title, class_ids, description)

    def remove_individual(self, individual_id: str) -> None:
        self._individuals.pop(individual_id, None)

    def reindex_all_individuals(self) -> int:
        return len(self._individuals)

    def search(
        self,
        query_embedding: list[float],
        class_ids: Sequence[str],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> list[IndividualMatch]:
        wanted = set(class_ids)
        matches: list[IndividualMatch] = []
        for ind_id, (title, cids, description) in self._individuals.items():
            if wanted and not (wanted & set(cids)):
                continue
            score = self._cosine(query_embedding, self._vectors.get(title, []))
            if score < threshold:
                continue
            matches.append(
                IndividualMatch(
                    individual_id=ind_id,
                    class_ids=list(cids),
                    title=title,
                    score=score,
                    description=description,
                )
            )
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:top_k]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / (na * nb)
