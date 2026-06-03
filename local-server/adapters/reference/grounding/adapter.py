"""
Grounding adapter that orchestrates queries to external knowledge sources.

Wraps existing reference sources (DBpedia, ConceptNet) to find candidates
matching a schema node label. Handles parallel queries and response normalization.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

from adapters.reference.conceptnet import ConceptNetSource
from adapters.reference.dbpedia import DBpediaSource
from adapters.reference.schema_org import SchemaOrgSource
from adapters.reference.wikidata import WikidataSource
from domain.pipelines.exceptions import PipelineExternalServiceError, PipelineInputError
from domain.pipelines.schema_node_grounding.scoring import GroundingCandidate
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
        wikidata: WikidataSource | None = None,
        schema_org: SchemaOrgSource | None = None,
    ) -> None:
        """
        Initialize the grounding adapter.

        Args:
            dbpedia: DBpedia source adapter (creates default if None)
            conceptnet: ConceptNet source adapter (creates default if None)
            wikidata: Wikidata source adapter (creates default if None)
            schema_org: schema.org source adapter (creates default if None)
        """
        self._dbpedia = dbpedia or DBpediaSource()
        self._conceptnet = conceptnet or ConceptNetSource()
        self._wikidata = wikidata or WikidataSource()
        self._schema_org = schema_org or SchemaOrgSource()
        self._sources = {
            "DBpedia": self._dbpedia,
            "ConceptNet": self._conceptnet,
            "Wikidata": self._wikidata,
            "schema.org": self._schema_org,
        }

    async def query_sources(
        self,
        label: str,
        sources: list[str] | None = None,
    ) -> list[GroundingCandidate]:
        """
        Query active sources for candidates matching the label.

        Dispatches queries to each active source in parallel and normalizes
        responses to GroundingCandidate objects.

        Args:
            label: Schema node label to find candidates for
            sources: List of source names to query (default: all)

        Returns:
            List of GroundingCandidate objects from all sources

        Raises:
            PipelineInputError: If unknown source names are requested
            PipelineExternalServiceError: If all queried sources fail
        """
        if not label or not label.strip():
            return []

        active_sources = sources or list(self._sources.keys())
        queries = []
        source_names = []
        unknown_sources = []

        for source_name in active_sources:
            if source_name not in self._sources:
                unknown_sources.append(source_name)
                continue

            source = self._sources[source_name]
            queries.append(self._query_single_source(label, source_name, source))
            source_names.append(source_name)

        if unknown_sources:
            raise PipelineInputError(
                f"Unknown grounding sources: {', '.join(unknown_sources)}. "
                f"Registered sources: {', '.join(sorted(self._sources.keys()))}"
            )

        if not queries:
            return []

        results = await asyncio.gather(*queries, return_exceptions=True)

        candidates: list[GroundingCandidate] = []
        failures: dict[str, str] = {}

        for source_name, result in zip(source_names, results):
            if isinstance(result, Exception):
                error_msg = str(result)
                logger.warning(f"Source query failed for {source_name}: {error_msg}")
                failures[source_name] = error_msg
                continue
            candidates.extend(cast(list[GroundingCandidate], result))

        if len(failures) == len(source_names):
            error_details = "; ".join(
                [f"{name}: {msg}" for name, msg in failures.items()]
            )
            raise PipelineExternalServiceError(
                f"All grounding sources failed: {error_details}"
            )

        return candidates

    async def _query_single_source(
        self,
        label: str,
        source_name: str,
        source: Any,
    ) -> list[GroundingCandidate]:
        """
        Query a single source for candidates.

        Args:
            label: Search label
            source_name: Name of source
            source: Source adapter instance

        Returns:
            List of normalized GroundingCandidate objects

        Raises:
            Exception: If source query fails, propagates to caller for handling
        """
        if source_name == "DBpedia":
            return await self._query_dbpedia(label, source)
        elif source_name == "ConceptNet":
            return await self._query_conceptnet(label, source)
        elif source_name == "Wikidata":
            return await self._query_wikidata(label, source)
        elif source_name == "schema.org":
            return await self._query_schema_org(label, source)
        else:
            logger.warning(f"No query handler for source: {source_name}")
            return []

    async def _query_dbpedia(
        self, label: str, source: DBpediaSource
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
                    source_score=result.confidence,
                    types=None,
                )
            )

        return candidates

    async def _query_conceptnet(
        self, label: str, source: ConceptNetSource
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
                    source_score=result.confidence,
                    types=None,
                )
            )

        return candidates

    async def _query_wikidata(
        self, label: str, source: WikidataSource
    ) -> list[GroundingCandidate]:
        """Query Wikidata for entities matching label."""
        results = await source.search_async(label, limit=10)
        candidates = []

        for result in results:
            candidates.append(
                GroundingCandidate(
                    uri=result.uri,
                    label=result.label,
                    description=result.description,
                    source="Wikidata",
                    source_score=result.confidence,
                    types=None,
                )
            )

        return candidates

    async def _query_schema_org(
        self, label: str, source: SchemaOrgSource
    ) -> list[GroundingCandidate]:
        """Query schema.org for type definitions matching label."""
        results = await source.search_async(label, limit=10)
        candidates = []

        for result in results:
            candidates.append(
                GroundingCandidate(
                    uri=result.uri,
                    label=result.label,
                    description=result.description,
                    source="schema.org",
                    source_score=result.confidence,
                    types=None,
                )
            )

        return candidates
