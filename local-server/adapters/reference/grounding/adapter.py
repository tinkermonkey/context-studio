"""
Grounding adapter that orchestrates queries to external knowledge sources.

Wraps existing reference sources (DBpedia, ConceptNet) to find candidates
matching a schema node label. Handles parallel queries and response normalization.
"""

from __future__ import annotations

import asyncio
from typing import Any

from adapters.reference.conceptnet import ConceptNetSource
from adapters.reference.dbpedia import DBpediaSource
from domain.pipelines.schema_node_grounding.scoring import GroundingCandidate, NodeType
from utils.logger import get_logger

logger = get_logger(__name__)


class GroundingAdapter:
    """
    Adapter for querying external sources for grounding candidates.

    Wraps DBpedia and ConceptNet sources to find entity candidates
    matching a schema node's label. Normalizes responses to common
    GroundingCandidate shape.
    """

    def __init__(
        self,
        dbpedia: DBpediaSource | None = None,
        conceptnet: ConceptNetSource | None = None,
    ) -> None:
        """
        Initialize the grounding adapter.

        Args:
            dbpedia: DBpedia source adapter (creates default if None)
            conceptnet: ConceptNet source adapter (creates default if None)
        """
        self._dbpedia = dbpedia or DBpediaSource()
        self._conceptnet = conceptnet or ConceptNetSource()
        self._sources = {
            "DBpedia": self._dbpedia,
            "ConceptNet": self._conceptnet,
        }

    async def query_sources(
        self,
        label: str,
        node_type: NodeType | None = None,
        sources: list[str] | None = None,
    ) -> list[GroundingCandidate]:
        """
        Query active sources for candidates matching the label.

        Dispatches queries to each active source in parallel and normalizes
        responses to GroundingCandidate objects.

        Args:
            label: Schema node label to find candidates for
            node_type: Type of node (Class or PropertyDefinition)
            sources: List of source names to query (default: all)

        Returns:
            List of GroundingCandidate objects from all sources
        """
        if not label or not label.strip():
            return []

        active_sources = sources or list(self._sources.keys())
        queries = []

        for source_name in active_sources:
            if source_name not in self._sources:
                logger.warning(f"Unknown source: {source_name}")
                continue

            source = self._sources[source_name]
            queries.append(self._query_single_source(label, source_name, source, node_type))

        if not queries:
            return []

        results = await asyncio.gather(*queries, return_exceptions=True)

        candidates = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Source query failed: {result}")
                continue
            candidates.extend(result)

        return candidates

    async def _query_single_source(
        self,
        label: str,
        source_name: str,
        source: Any,
        node_type: NodeType | None = None,
    ) -> list[GroundingCandidate]:
        """
        Query a single source for candidates.

        Args:
            label: Search label
            source_name: Name of source
            source: Source adapter instance
            node_type: Type of node

        Returns:
            List of normalized GroundingCandidate objects
        """
        try:
            if source_name == "DBpedia":
                return await self._query_dbpedia(label, source, node_type)
            elif source_name == "ConceptNet":
                return await self._query_conceptnet(label, source, node_type)
            else:
                logger.warning(f"No query handler for source: {source_name}")
                return []
        except Exception as e:
            logger.warning(f"Error querying {source_name}: {e}")
            return []

    async def _query_dbpedia(
        self, label: str, source: DBpediaSource, node_type: NodeType | None = None
    ) -> list[GroundingCandidate]:
        """Query DBpedia for entities matching label."""
        results = await source.search_async(label, limit=10)
        candidates = []

        for result in results:
            candidates.append(
                GroundingCandidate(
                    uri=result.uri,
                    label=result.label,
                    description=result.description,
                    source="DBpedia",
                    source_score=0.8,
                    types=None,
                )
            )

        return candidates

    async def _query_conceptnet(
        self, label: str, source: ConceptNetSource, node_type: NodeType | None = None
    ) -> list[GroundingCandidate]:
        """Query ConceptNet for concepts matching label."""
        results = await source.search_async(label, limit=10)
        candidates = []

        for result in results:
            candidates.append(
                GroundingCandidate(
                    uri=result.uri,
                    label=result.label,
                    description=result.description,
                    source="ConceptNet",
                    source_score=0.7,
                    types=None,
                )
            )

        return candidates
