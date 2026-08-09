"""
In-memory fake SchemaVectorIndex for domain unit tests.

Tracks index_entity calls by entity_id so service-level sync behavior (which
entities were embedded, with what text) can be asserted without a DB or an
embedding model. Search is not exercised by these tests, so it is unimplemented.
"""

from __future__ import annotations


class FakeSchemaVectorIndex:
    def __init__(self) -> None:
        # entity_id -> (title, description)
        self._entities: dict[str, tuple[str, str | None]] = {}

    def index_entity(self, entity_id: str, title: str, description: str | None) -> None:
        self._entities[entity_id] = (title, description)

    def search(self, query_embedding, kinds, top_k=20, threshold=0.0, taxonomy_id=None):
        raise NotImplementedError
