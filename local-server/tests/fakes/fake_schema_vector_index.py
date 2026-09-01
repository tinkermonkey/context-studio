"""
In-memory fake SchemaVectorIndex for domain unit tests.

Tracks index_entity calls by entity_id so service-level sync behavior (which
entities were embedded, with what text) can be asserted without a DB or an
embedding model. Supports configurable search results for testing retrieval logic.
"""

from __future__ import annotations

from typing import Sequence

from domain.ontology.ports import SchemaKind, SchemaMatch


class FakeSchemaVectorIndex:
    def __init__(
        self, search_results: list[SchemaMatch] | None = None
    ) -> None:
        # entity_id -> (title, description)
        self._entities: dict[str, tuple[str, str | None]] = {}
        # Configured search results: list of (match, taxonomy_id) tuples
        # taxonomy_id is optional and used for filtering
        self._search_results: list[tuple[SchemaMatch, str | None]] = []
        if search_results:
            self.set_search_results(search_results)

    def index_entity(self, entity_id: str, title: str, description: str | None) -> None:
        self._entities[entity_id] = (title, description)

    def set_search_results(
        self, results: list[SchemaMatch], taxonomies: dict[str, str | None] | None = None
    ) -> None:
        """
        Configure the results that search() will return.

        Args:
            results: List of SchemaMatch objects to return from search()
            taxonomies: Optional dict mapping entity_id to taxonomy_id for filtering.
                       If not provided, all results are assumed to belong to any taxonomy.
        """
        if taxonomies is None:
            taxonomies = {match.entity_id: None for match in results}
        self._search_results = [(match, taxonomies.get(match.entity_id)) for match in results]

    def search(
        self,
        query_embedding,
        kinds: Sequence[SchemaKind],
        top_k: int = 20,
        threshold: float = 0.0,
        taxonomy_id: str | None = None,
    ) -> list[SchemaMatch]:
        """
        Return configured search results, filtered by taxonomy_id and kinds.

        Args:
            query_embedding: Ignored (not used by the fake)
            kinds: Filter results to only include matches with these kinds
            top_k: Maximum number of results to return
            threshold: Ignored (all configured results pass)
            taxonomy_id: Filter results to only include matches from this taxonomy

        Returns:
            Filtered configured search results, up to top_k matches
        """
        filtered = []
        for match, match_taxonomy_id in self._search_results:
            # Filter by kinds
            if match.kind not in kinds:
                continue
            # Filter by taxonomy_id if specified
            if taxonomy_id is not None and match_taxonomy_id != taxonomy_id:
                continue
            filtered.append(match)

        # Return up to top_k results
        return filtered[:top_k]
