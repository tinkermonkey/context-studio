# mypy: ignore-errors
"""Core reference service coordinating all reference API sources"""

from typing import Dict, Any, Optional, List, Tuple
import asyncio
from datetime import datetime, UTC
import time

from config import get_config_manager, ConfigurationManager
from .exceptions import ReferenceError
from .models import (
    SourceType,
    DBpediaResourceRequest,
    DBpediaSearchRequest,
    DBpediaSparqlRequest,
    ConceptNetQueryRequest,
    WikidataSparqlRequest,
    WikidataEntityRequest,
    WikidataSearchRequest,
    SchemaOrgEntityRequest,
    SchemaOrgPropertyRequest,
    SchemaOrgSearchRequest,
    MultiSourceSearchRequest,
    MultiSourceSearchResponse,
    SearchNode,
    SearchLink,
    DBpediaResourceResponse,
    DBpediaSearchResponse,
    DBpediaSparqlResponse,
    ConceptNetQueryResponse,
    ConceptNetConceptResponse,
    ConceptNetRelatedResponse,
    WikidataSparqlResponse,
    WikidataEntityResponse,
    WikidataSearchResponse,
    SchemaOrgEntityResponse,
    SchemaOrgPropertyResponse,
    SchemaOrgSearchResponse,
)
from .sources import DBpediaSource, ConceptNetSource, WikidataSource, SchemaOrgSource
from .normalizers import ResultNormalizer
from .aggregators import ResultAggregator
from .response_builders import ResponseBuilder
from utils.logger import get_logger

logger = get_logger(__name__)


class ReferenceService:
    """Core reference service coordinating all reference API sources"""

    def __init__(self, config_manager: ConfigurationManager = None):
        self.config_manager = config_manager or get_config_manager()
        self.settings = self.config_manager.settings
        self._sources = {}  # Cache for source instances

        # Initialize new architecture components
        self.normalizer = ResultNormalizer(self.settings)
        self.aggregator = ResultAggregator()
        self.response_builder = ResponseBuilder()

    def _get_source(self, source_type: SourceType):
        """Get or create source instance"""
        if source_type not in self._sources:
            source_config = self.settings.get_source_config(source_type.value)

            if source_type == SourceType.DBPEDIA:
                self._sources[source_type] = DBpediaSource(source_type, source_config)
            elif source_type == SourceType.CONCEPTNET:
                self._sources[source_type] = ConceptNetSource(
                    source_type, source_config
                )
            elif source_type == SourceType.WIKIDATA:
                self._sources[source_type] = WikidataSource(source_type, source_config)
            elif source_type == SourceType.SCHEMA_ORG:
                self._sources[source_type] = SchemaOrgSource(source_type, source_config)
            else:
                raise ReferenceError(f"Unknown source type: {source_type}")

        return self._sources[source_type]

    # DBpedia methods - now return MultiSourceSearchResponse
    async def dbpedia_get_resource(
        self, request: DBpediaResourceRequest
    ) -> MultiSourceSearchResponse:
        """Get DBpedia resource data"""
        start_time = time.time()
        try:
            source = self._get_source(SourceType.DBPEDIA)
            async with source:
                response = await source.get_resource_data(
                    request.resource_url, request.format.value
                )
                nodes, links = self.normalizer.normalize_dbpedia_resource_response(
                    response, request.resource_url
                )
                search_time_ms = (time.time() - start_time) * 1000
                return self.response_builder.build_single_source_response(
                    SourceType.DBPEDIA,
                    request.resource_url,
                    nodes,
                    links,
                    limit=1,
                    offset=0,
                    search_time_ms=search_time_ms,
                )
        except Exception as e:
            search_time_ms = (time.time() - start_time) * 1000
            logger.error(f"DBpedia resource request failed: {e}")
            return self.response_builder.build_error_response(
                request.resource_url, str(e), SourceType.DBPEDIA
            )

    async def dbpedia_search(
        self, request: DBpediaSearchRequest
    ) -> MultiSourceSearchResponse:
        """Search DBpedia"""
        start_time = time.time()
        try:
            source = self._get_source(SourceType.DBPEDIA)
            async with source:
                response = await source.search(
                    request.query, request.limit, request.offset, request.format.value
                )
                nodes, links = self.normalizer.normalize_dbpedia_search_response(
                    response, request.query
                )
                search_time_ms = (time.time() - start_time) * 1000
                return self.response_builder.build_single_source_response(
                    SourceType.DBPEDIA,
                    request.query,
                    nodes,
                    links,
                    limit=request.limit,
                    offset=request.offset,
                    search_time_ms=search_time_ms,
                )
        except Exception as e:
            search_time_ms = (time.time() - start_time) * 1000
            logger.error(f"DBpedia search failed: {e}")
            return self.response_builder.build_error_response(
                request.query, str(e), SourceType.DBPEDIA, request.limit, request.offset
            )

    async def dbpedia_sparql(
        self, request: DBpediaSparqlRequest
    ) -> MultiSourceSearchResponse:
        """Execute DBpedia SPARQL query"""
        start_time = time.time()
        try:
            source = self._get_source(SourceType.DBPEDIA)
            async with source:
                response = await source.sparql_query(
                    request.query, request.format.value
                )
                nodes, links = self.normalizer.normalize_dbpedia_sparql_response(
                    response, request.query
                )
                search_time_ms = (time.time() - start_time) * 1000
                return self.response_builder.build_single_source_response(
                    SourceType.DBPEDIA,
                    request.query,
                    nodes,
                    links,
                    limit=20,
                    offset=0,
                    search_time_ms=search_time_ms,
                )
        except Exception as e:
            search_time_ms = (time.time() - start_time) * 1000
            logger.error(f"DBpedia SPARQL query failed: {e}")
            return self.response_builder.build_error_response(
                request.query, str(e), SourceType.DBPEDIA
            )

    # ConceptNet methods - now return MultiSourceSearchResponse
    async def conceptnet_query(
        self, request: ConceptNetQueryRequest
    ) -> MultiSourceSearchResponse:
        """Query ConceptNet"""
        start_time = time.time()
        try:
            source = self._get_source(SourceType.CONCEPTNET)
            async with source:
                response = await source.query(
                    start=request.start,
                    end=request.end,
                    node=request.node,
                    rel=request.rel,
                    limit=request.limit,
                    offset=request.offset,
                )
                query_str = request.node or request.start or request.end or "query"
                nodes, links = self.normalizer.normalize_conceptnet_query_response(
                    response, query_str
                )
                search_time_ms = (time.time() - start_time) * 1000
                return self.response_builder.build_single_source_response(
                    SourceType.CONCEPTNET,
                    query_str,
                    nodes,
                    links,
                    limit=request.limit,
                    offset=request.offset,
                    search_time_ms=search_time_ms,
                )
        except Exception as e:
            search_time_ms = (time.time() - start_time) * 1000
            query_str = request.node or request.start or request.end or "query"
            logger.error(f"ConceptNet query failed: {e}")
            return self.response_builder.build_error_response(
                query_str, str(e), SourceType.CONCEPTNET, request.limit, request.offset
            )

    async def conceptnet_get_concept(
        self, concept_path: str
    ) -> MultiSourceSearchResponse:
        """Get ConceptNet concept"""
        start_time = time.time()
        try:
            source = self._get_source(SourceType.CONCEPTNET)
            async with source:
                response = await source.get_concept(concept_path)
                nodes, links = self.normalizer.normalize_conceptnet_concept_response(
                    response, concept_path
                )
                search_time_ms = (time.time() - start_time) * 1000
                return self.response_builder.build_single_source_response(
                    SourceType.CONCEPTNET,
                    concept_path,
                    nodes,
                    links,
                    limit=1,
                    offset=0,
                    search_time_ms=search_time_ms,
                )
        except Exception as e:
            search_time_ms = (time.time() - start_time) * 1000
            logger.error(f"ConceptNet get concept failed: {e}")
            return self.response_builder.build_error_response(
                concept_path, str(e), SourceType.CONCEPTNET
            )

    async def conceptnet_get_related(
        self, concept_path: str, filter: Optional[str] = None, limit: int = 20
    ) -> MultiSourceSearchResponse:
        """Get ConceptNet related concepts"""
        start_time = time.time()
        try:
            source = self._get_source(SourceType.CONCEPTNET)
            async with source:
                response = await source.get_related(concept_path, filter, limit)
                nodes, links = self.normalizer.normalize_conceptnet_related_response(
                    response, concept_path
                )
                search_time_ms = (time.time() - start_time) * 1000
                return self.response_builder.build_single_source_response(
                    SourceType.CONCEPTNET,
                    concept_path,
                    nodes,
                    links,
                    limit=limit,
                    offset=0,
                    search_time_ms=search_time_ms,
                )
        except Exception as e:
            search_time_ms = (time.time() - start_time) * 1000
            logger.error(f"ConceptNet get related failed: {e}")
            return self.response_builder.build_error_response(
                concept_path, str(e), SourceType.CONCEPTNET, limit
            )

    # Wikidata methods - now return MultiSourceSearchResponse
    async def wikidata_sparql(
        self, request: WikidataSparqlRequest
    ) -> MultiSourceSearchResponse:
        """Execute Wikidata SPARQL query"""
        start_time = time.time()
        try:
            source = self._get_source(SourceType.WIKIDATA)
            async with source:
                response = await source.sparql_query(
                    request.query, request.format.value
                )
                nodes, links = self.normalizer.normalize_wikidata_sparql_response(
                    response, request.query
                )
                search_time_ms = (time.time() - start_time) * 1000
                return self.response_builder.build_single_source_response(
                    SourceType.WIKIDATA,
                    request.query,
                    nodes,
                    links,
                    limit=20,
                    offset=0,
                    search_time_ms=search_time_ms,
                )
        except Exception as e:
            search_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Wikidata SPARQL query failed: {e}")
            return self.response_builder.build_error_response(
                request.query, str(e), SourceType.WIKIDATA
            )

    async def wikidata_get_entity(
        self, request: WikidataEntityRequest
    ) -> MultiSourceSearchResponse:
        """Get Wikidata entity data"""
        start_time = time.time()
        try:
            source = self._get_source(SourceType.WIKIDATA)
            async with source:
                response = await source.get_entity_data(
                    request.entity_url, request.properties, request.format.value
                )
                nodes, links = self.normalizer.normalize_wikidata_entity_response(
                    response, request.entity_url
                )
                search_time_ms = (time.time() - start_time) * 1000
                return self.response_builder.build_single_source_response(
                    SourceType.WIKIDATA,
                    request.entity_url,
                    nodes,
                    links,
                    limit=1,
                    offset=0,
                    search_time_ms=search_time_ms,
                )
        except Exception as e:
            logger.error(f"Wikidata entity request failed: {e}")
            return self.response_builder.build_error_response(
                request.entity_url, str(e), SourceType.WIKIDATA
            )

    async def wikidata_search(
        self, request: WikidataSearchRequest
    ) -> MultiSourceSearchResponse:
        """Search Wikidata entities"""
        try:
            # For backwards compatibility, we need to implement this method to use SPARQL
            # since the existing logic in _search_single_source uses SPARQL for search
            escaped_query = (
                request.query.replace('"', '\\"').replace("\n", " ").replace("\r", " ")
            )
            default_language = self.settings.reference_sources.default_language

            sparql_query = f"""
            SELECT ?item ?itemLabel ?itemDescription WHERE {{
              ?item rdfs:label "{escaped_query}"@{default_language} .
              SERVICE wikibase:label {{
                bd:serviceParam wikibase:language "{default_language}" .
                ?item rdfs:label ?itemLabel .
                ?item schema:description ?itemDescription .
              }}
              FILTER(lang(?itemLabel) = "{default_language}" || lang(?itemLabel) = "")
            }}
            LIMIT {request.limit}
            OFFSET {request.offset}
            """

            sparql_request = WikidataSparqlRequest(query=sparql_query)
            return await self.wikidata_sparql(sparql_request)
        except Exception as e:
            logger.error(f"Wikidata search failed: {e}")
            return self.response_builder.build_error_response(
                request.query,
                str(e),
                SourceType.WIKIDATA,
                request.limit,
                request.offset,
            )

    # Schema.org methods - now return MultiSourceSearchResponse
    async def schema_org_get_entity(
        self, request: SchemaOrgEntityRequest
    ) -> MultiSourceSearchResponse:
        """Get Schema.org entity"""
        start_time = time.time()
        try:
            source = self._get_source(SourceType.SCHEMA_ORG)
            async with source:
                response = await source.get_entity(
                    request.identifier,
                    request.include_inherited,
                    request.include_children,
                )
                nodes, links = self.normalizer.normalize_schema_org_entity_response(
                    response, request.identifier
                )
                search_time_ms = (time.time() - start_time) * 1000
                return self.response_builder.build_single_source_response(
                    SourceType.SCHEMA_ORG,
                    request.identifier,
                    nodes,
                    links,
                    limit=1,
                    offset=0,
                    search_time_ms=search_time_ms,
                )
        except Exception as e:
            search_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Schema.org entity request failed: {e}")
            return self.response_builder.build_error_response(
                request.identifier, str(e), SourceType.SCHEMA_ORG
            )

    async def schema_org_get_property(
        self, request: SchemaOrgPropertyRequest
    ) -> MultiSourceSearchResponse:
        """Get Schema.org property"""
        start_time = time.time()
        try:
            source = self._get_source(SourceType.SCHEMA_ORG)
            async with source:
                response = await source.get_property(
                    request.identifier, request.include_usage
                )
                nodes, links = self.normalizer.normalize_schema_org_property_response(
                    response, request.identifier
                )
                search_time_ms = (time.time() - start_time) * 1000
                return self.response_builder.build_single_source_response(
                    SourceType.SCHEMA_ORG,
                    request.identifier,
                    nodes,
                    links,
                    limit=1,
                    offset=0,
                    search_time_ms=search_time_ms,
                )
        except Exception as e:
            search_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Schema.org property request failed: {e}")
            return self.response_builder.build_error_response(
                request.identifier, str(e), SourceType.SCHEMA_ORG
            )

    async def schema_org_search(
        self, request: SchemaOrgSearchRequest
    ) -> MultiSourceSearchResponse:
        """Search Schema.org entities and properties"""
        start_time = time.time()
        try:
            source = self._get_source(SourceType.SCHEMA_ORG)
            async with source:
                response = await source.search(
                    query=request.query,
                    search_type=request.search_type,
                    limit=request.limit,
                    offset=request.offset,
                    similarity_threshold=request.similarity_threshold,
                )
                nodes, links = self.normalizer.normalize_schema_org_search_response(
                    response, request.query
                )
                search_time_ms = (time.time() - start_time) * 1000
                return self.response_builder.build_single_source_response(
                    SourceType.SCHEMA_ORG,
                    request.query,
                    nodes,
                    links,
                    limit=request.limit,
                    offset=request.offset,
                    search_time_ms=search_time_ms,
                )
        except Exception as e:
            search_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Schema.org search failed: {e}")
            return self.response_builder.build_error_response(
                request.query,
                str(e),
                SourceType.SCHEMA_ORG,
                request.limit,
                request.offset,
            )

    # Multi-source search method - simplified using new architecture
    async def search(
        self, request: MultiSourceSearchRequest
    ) -> MultiSourceSearchResponse:
        """
        Search across multiple reference sources

        Args:
            request: Multi-source search request

        Returns:
            Aggregated search results from all requested sources
        """
        start_time = time.time()
        logger.info(f"Starting multi-source search for query: '{request.query}'")

        # Determine which sources to query
        sources_to_query = request.sources or [
            SourceType.DBPEDIA,
            SourceType.CONCEPTNET,
            SourceType.WIKIDATA,
            SourceType.SCHEMA_ORG,
        ]

        # Filter to only enabled sources
        enabled_sources = []
        for source_type in sources_to_query:
            try:
                # Check if source is enabled in configuration
                source_config = self.settings.get_source_config(source_type.value)
                if source_config.enabled:
                    enabled_sources.append(source_type)
                else:
                    logger.debug(f"Skipping disabled source: {source_type.value}")
            except Exception as e:
                logger.warning(f"Error checking source {source_type.value}: {e}")

        search_timeout = self.settings.reference_sources.search_timeout
        logger.info(
            f"Querying {len(enabled_sources)} enabled sources: {[s.value for s in enabled_sources]} (timeout: {search_timeout}s)"
        )

        # Search each source in parallel
        search_tasks = []
        for source_type in enabled_sources:
            task = self._search_single_source_normalized(
                source_type, request.query, request.limit, request.offset
            )
            search_tasks.append((source_type, task))

        # Execute all searches in parallel
        results = await self._gather_search_results_normalized(
            search_tasks, search_timeout
        )

        # Use aggregator to combine results
        search_time_ms = (time.time() - start_time) * 1000
        response = self.aggregator.aggregate_source_results(
            results, request.query, request.limit, request.offset, search_time_ms, {}
        )

        logger.info(
            f"Multi-source search completed: '{request.query}' returned {response.total_results} nodes, {response.total_links} links in {search_time_ms:.2f}ms"
        )
        return response

    async def _search_single_source_normalized(
        self, source_type: SourceType, query: str, limit: int, offset: int
    ) -> Tuple[List[SearchNode], List[SearchLink]]:
        """Search a single source using new normalized architecture"""
        try:
            logger.debug(f"Searching {source_type.value} for '{query}'")

            if source_type == SourceType.DBPEDIA:
                # Note: DBpedia Lookup API currently only supports English
                default_language = self.settings.reference_sources.default_language
                if default_language != "en":
                    logger.warning(
                        f"DBpedia Lookup API only supports English, but configured language is '{default_language}'"
                    )

                request = DBpediaSearchRequest(query=query, limit=limit, offset=offset)
                response = await self.dbpedia_search(request)
                return response.results, response.links

            elif source_type == SourceType.CONCEPTNET:
                # Use higher limit to capture ExternalURL relations in single request
                extended_limit = min(
                    max(limit * 3, 50), 100
                )  # Increase limit but respect ConceptNet's max of 100
                default_language = self.settings.reference_sources.default_language
                request = ConceptNetQueryRequest(
                    node=f"/c/{default_language}/{query.lower().replace(' ', '_')}",
                    limit=extended_limit,
                    offset=offset,
                )
                response = await self.conceptnet_query(request)
                return response.results, response.links

            elif source_type == SourceType.WIKIDATA:
                request = WikidataSearchRequest(query=query, limit=limit, offset=offset)
                response = await self.wikidata_search(request)
                return response.results, response.links

            elif source_type == SourceType.SCHEMA_ORG:
                request = SchemaOrgSearchRequest(
                    query=query, limit=limit, offset=offset
                )
                response = await self.schema_org_search(request)
                return response.results, response.links

            else:
                logger.warning(f"Unknown source type: {source_type}")
                return [], []

        except Exception as e:
            logger.error(f"Error searching {source_type.value}: {e}")
            raise e

    async def _gather_search_results_normalized(
        self, search_tasks: List[tuple], search_timeout: int
    ) -> List[Tuple[SourceType, Tuple[List[SearchNode], List[SearchLink]]]]:
        """Execute search tasks in parallel and gather normalized results"""
        results = []

        # Extract tasks for parallel execution
        task_coroutines = [task for _, task in search_tasks]
        sources = [source for source, _ in search_tasks]

        try:
            # Run all tasks in parallel with configurable timeout
            completed_results = await asyncio.wait_for(
                asyncio.gather(*task_coroutines, return_exceptions=True),
                timeout=search_timeout,
            )

            # Pair results back with sources
            for source, result in zip(sources, completed_results):
                if isinstance(result, Exception):
                    logger.warning(f"Search failed for {source.value}: {result}")
                    results.append((source, ([], [])))
                else:
                    results.append((source, result))

        except asyncio.TimeoutError:
            # Handle timeout - some sources may not have responded
            logger.warning("Some sources timed out during search")
            for source in sources:
                results.append((source, ([], [])))
        except Exception as e:
            logger.error(f"Error in parallel search execution: {e}")
            for source in sources:
                results.append((source, ([], [])))

        return results

    async def _gather_search_results(
        self, search_tasks: List[tuple], search_timeout: int
    ) -> List[tuple]:
        """Execute search tasks in parallel and gather results"""
        results = []

        # Extract tasks for parallel execution
        task_coroutines = [task for _, task in search_tasks]
        sources = [source for source, _ in search_tasks]

        try:
            # Run all tasks in parallel with configurable timeout
            completed_results = await asyncio.wait_for(
                asyncio.gather(*task_coroutines, return_exceptions=True),
                timeout=search_timeout,
            )

            # Pair results back with sources
            for source, result in zip(sources, completed_results):
                results.append((source, result))

        except asyncio.TimeoutError:
            # Handle timeout - some sources may not have responded
            logger.warning("Some sources timed out during search")
            for source in sources:
                results.append((source, TimeoutError("Search timeout")))
        except Exception as e:
            logger.error(f"Error in parallel search execution: {e}")
            for source in sources:
                results.append((source, e))

        return results

    def _discover_cross_references(self, nodes: List[SearchNode]) -> List[SearchLink]:
        """
        Discover cross-references between nodes from different sources based on title matching.
        Creates 'sameAs' links when nodes from different sources likely refer to the same concept.
        """
        cross_links = []

        # Group nodes by normalized title for matching
        title_groups = {}
        for node in nodes:
            # Normalize title for matching (lowercase, remove common variations)
            normalized_title = self._normalize_title(node.title)
            if normalized_title not in title_groups:
                title_groups[normalized_title] = []
            title_groups[normalized_title].append(node)

        # Find groups with nodes from multiple sources
        for normalized_title, matching_nodes in title_groups.items():
            if len(matching_nodes) < 2:
                continue

            # Group by source
            sources_present = {}
            for node in matching_nodes:
                if node.source not in sources_present:
                    sources_present[node.source] = []
                sources_present[node.source].append(node)

            # Only create cross-references between different sources
            if len(sources_present) < 2:
                continue

            # Create cross-reference links between nodes from different sources
            source_pairs = []
            sources = list(sources_present.keys())
            for i in range(len(sources)):
                for j in range(i + 1, len(sources)):
                    source_pairs.append((sources[i], sources[j]))

            for source1, source2 in source_pairs:
                nodes1 = sources_present[source1]
                nodes2 = sources_present[source2]

                # Create links between the best matching nodes from each source
                for node1 in nodes1[:1]:  # Take best match from each source
                    for node2 in nodes2[:1]:
                        # Calculate confidence based on title similarity
                        confidence = self._calculate_title_similarity(
                            node1.title, node2.title
                        )

                        if (
                            confidence >= 0.8
                        ):  # High confidence threshold for cross-references
                            cross_links.append(
                                SearchLink(
                                    id=f"cross_ref:{node1.source.value}:{node2.source.value}:{hash(node1.id + node2.id)}",
                                    source=SourceType.CONCEPTNET,  # Use ConceptNet as the source for cross-references
                                    subject=node1.id,
                                    predicate="sameAs",
                                    object=node2.id,
                                    weight=confidence,
                                    attributes={
                                        "link_type": "cross_reference",
                                        "confidence": confidence,
                                        "matching_title": normalized_title,
                                        "source1": node1.source.value,
                                        "source2": node2.source.value,
                                    },
                                )
                            )

        return cross_links

    def _normalize_title(self, title: str) -> str:
        """Normalize title for cross-reference matching"""
        if not title:
            return ""

        # Convert to lowercase and strip whitespace
        normalized = title.lower().strip()

        # Remove common variations and articles
        normalized = normalized.replace("the ", "").replace("a ", "").replace("an ", "")

        # Handle file extensions for file nodes
        if normalized in ["image file", "document file", "media file", "file"]:
            return normalized

        # Remove parenthetical content that might differ between sources
        import re

        normalized = re.sub(r"\([^)]*\)", "", normalized).strip()

        return normalized

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles (0.0 to 1.0)"""
        if not title1 or not title2:
            return 0.0

        title1_norm = self._normalize_title(title1)
        title2_norm = self._normalize_title(title2)

        if title1_norm == title2_norm:
            return 1.0

        # Use simple character-based similarity for now
        # Could be enhanced with more sophisticated matching
        shorter = min(len(title1_norm), len(title2_norm))
        longer = max(len(title1_norm), len(title2_norm))

        if longer == 0:
            return 1.0 if shorter == 0 else 0.0

        # Count matching characters
        matches = sum(
            1
            for i in range(min(len(title1_norm), len(title2_norm)))
            if title1_norm[i] == title2_norm[i]
        )

        return matches / longer

    async def _fetch_conceptnet_external_urls(
        self, concept_ids: set
    ) -> List[SearchLink]:
        """
        Fetch external URL relations from ConceptNet for the given concept IDs.
        Creates links to DBpedia, Wikidata, WordNet, and other external knowledge bases.
        """
        external_links = []

        # Process a limited number of concepts to avoid too many API calls
        limited_concepts = list(concept_ids)[:5]  # Limit to avoid timeout

        for concept_id in limited_concepts:
            try:
                # Query ConceptNet for ExternalURL relations from this concept
                source = self._get_source(SourceType.CONCEPTNET)
                async with source:
                    # Use the direct ConceptNet API to get external URLs
                    import aiohttp

                    url = "https://api.conceptnet.io/query"
                    params = {"rel": "/r/ExternalURL", "start": concept_id, "limit": 10}

                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, params=params) as response:
                            if response.status == 200:
                                data = await response.json()

                                for edge in data.get("edges", []):
                                    end_url = edge.get("end", {}).get("@id", "")

                                    if end_url and any(
                                        domain in end_url
                                        for domain in [
                                            "dbpedia.org",
                                            "wikidata.org",
                                            "wordnet",
                                        ]
                                    ):
                                        # Determine the target source type
                                        if "dbpedia.org" in end_url:
                                            target_source = SourceType.DBPEDIA
                                            target_id = f"dbpedia:{end_url}"
                                        elif (
                                            "wikidata.org" in end_url
                                            or "wikidata.dbpedia.org" in end_url
                                        ):
                                            target_source = SourceType.WIKIDATA
                                            # Extract Wikidata Q-ID
                                            if "/Q" in end_url:
                                                q_id = end_url.split("/Q")[-1].rstrip(
                                                    "/"
                                                )
                                                target_id = f"wikidata:http://www.wikidata.org/entity/Q{q_id}"
                                            else:
                                                target_id = f"wikidata:{end_url}"
                                        else:
                                            continue  # Skip WordNet and others for now

                                        # Create external reference link
                                        external_links.append(
                                            SearchLink(
                                                id=f"conceptnet_external:{concept_id}:{end_url}",
                                                source=SourceType.CONCEPTNET,
                                                subject=f"conceptnet:{concept_id}",
                                                predicate="externalURL",
                                                object=target_id,
                                                weight=1.0,
                                                attributes={
                                                    "link_type": "external_reference",
                                                    "external_url": end_url,
                                                    "target_source": target_source.value,
                                                    "source_dataset": edge.get(
                                                        "dataset", ""
                                                    ),
                                                },
                                            )
                                        )

            except Exception as e:
                logger.warning(f"Error fetching external URLs for {concept_id}: {e}")
                continue

        return external_links

    # Keep the old methods for backward compatibility
    async def _search_single_source(
        self, source_type: SourceType, query: str, limit: int, offset: int
    ) -> Tuple[List[SearchNode], List[SearchLink]]:
        """Legacy method for backward compatibility - delegates to normalized version"""
        return await self._search_single_source_normalized(
            source_type, query, limit, offset
        )

    def _discover_cross_references(self, nodes: List[SearchNode]) -> List[SearchLink]:
        """Legacy method for backward compatibility - delegates to aggregator"""
        return self.aggregator.discover_cross_references(nodes)

    def _normalize_title(self, title: str) -> str:
        """Legacy method for backward compatibility - delegates to aggregator"""
        return self.aggregator._normalize_title(title)

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Legacy method for backward compatibility - delegates to aggregator"""
        return self.aggregator._calculate_title_similarity(title1, title2)

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all configured sources"""
        health_status = {
            "overall": "healthy",
            "sources": {},
            "timestamp": datetime.now(UTC),
            "language_config": {
                "default_language": self.settings.reference_sources.default_language
            },
        }

        for source_type in SourceType:
            source_config = self.settings.get_source_config(source_type.value)
            if source_config.enabled:
                try:
                    source = self._get_source(source_type)
                    # Special-case schema_org: use manager status (synchronous) instead of HTTP HEAD
                    if source_type == SourceType.SCHEMA_ORG and hasattr(
                        source, "manager"
                    ):
                        # run manager.get_status in threadpool to avoid blocking
                        loop = asyncio.get_event_loop()
                        status = await loop.run_in_executor(
                            None, source.manager.get_status
                        )
                        # consider healthy if populated or no errors
                        if status and status.get("is_populated"):
                            health_status["sources"][source_type.value] = "healthy"
                        else:
                            health_status["sources"][
                                source_type.value
                            ] = f"unhealthy: {status}"
                            health_status["overall"] = "degraded"
                    else:
                        async with source:
                            # For Wikidata, include a User-Agent header to avoid 403 responses
                            headers = {}
                            if source_type == SourceType.WIKIDATA:
                                headers["User-Agent"] = (
                                    "ContextStudio/LocalServer (contact: devnull@example.com)"
                                )
                            # Perform a simple health check request
                            await source._make_request(
                                "HEAD", source._get_base_url(), headers=headers
                            )
                    health_status["sources"][source_type.value] = "healthy"
                except Exception as e:
                    health_status["sources"][source_type.value] = f"unhealthy: {str(e)}"
                    health_status["overall"] = "degraded"
            else:
                health_status["sources"][source_type.value] = "disabled"

        return health_status

    def get_enabled_sources(self) -> List[str]:
        """Get list of enabled reference sources"""
        enabled_sources = []
        sources = [
            "conceptnet",
            "dbpedia",
            "dbpedia_spotlight",
            "wikidata",
            "schema_org",
        ]

        for source_name in sources:
            config = getattr(self.settings.reference_sources, source_name)
            if config.enabled:
                enabled_sources.append(source_name)

        return enabled_sources

    async def get_source_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all reference sources"""
        status = {}
        for source_name in [
            "conceptnet",
            "dbpedia_lookup",
            "dbpedia_sparql",
            "dbpedia_spotlight",
            "wikidata",
            "duckduckgo",
            "schema_org",
        ]:
            config = getattr(self.settings.reference_sources, source_name)
            status[source_name] = {
                "enabled": config.enabled,
                "use_proxy": config.use_proxy,
                "upstream_url": config.upstream_url,
                "timeout": config.timeout,
                "rate_limit": config.rate_limit.requests_per_hour,
            }
        return status

    # Legacy wrapper methods for backward compatibility
    async def dbpedia_get_resource_legacy(
        self, request: DBpediaResourceRequest
    ) -> DBpediaResourceResponse:
        """Legacy method that returns original response format"""
        source = self._get_source(SourceType.DBPEDIA)
        async with source:
            return await source.get_resource_data(
                request.resource_url, request.format.value
            )

    async def dbpedia_search_legacy(
        self, request: DBpediaSearchRequest
    ) -> DBpediaSearchResponse:
        """Legacy method that returns original response format"""
        source = self._get_source(SourceType.DBPEDIA)
        async with source:
            return await source.search(
                request.query, request.limit, request.offset, request.format.value
            )

    async def dbpedia_sparql_legacy(
        self, request: DBpediaSparqlRequest
    ) -> DBpediaSparqlResponse:
        """Legacy method that returns original response format"""
        source = self._get_source(SourceType.DBPEDIA)
        async with source:
            return await source.sparql_query(request.query, request.format.value)

    async def conceptnet_query_legacy(
        self, request: ConceptNetQueryRequest
    ) -> ConceptNetQueryResponse:
        """Legacy method that returns original response format"""
        source = self._get_source(SourceType.CONCEPTNET)
        async with source:
            return await source.query(
                start=request.start,
                end=request.end,
                node=request.node,
                rel=request.rel,
                limit=request.limit,
                offset=request.offset,
            )

    async def conceptnet_get_concept_legacy(
        self, concept_path: str
    ) -> ConceptNetConceptResponse:
        """Legacy method that returns original response format"""
        source = self._get_source(SourceType.CONCEPTNET)
        async with source:
            return await source.get_concept(concept_path)

    async def conceptnet_get_related_legacy(
        self, concept_path: str, filter: Optional[str] = None, limit: int = 20
    ) -> ConceptNetRelatedResponse:
        """Legacy method that returns original response format"""
        source = self._get_source(SourceType.CONCEPTNET)
        async with source:
            return await source.get_related(concept_path, filter, limit)

    async def wikidata_sparql_legacy(
        self, request: WikidataSparqlRequest
    ) -> WikidataSparqlResponse:
        """Legacy method that returns original response format"""
        source = self._get_source(SourceType.WIKIDATA)
        async with source:
            return await source.sparql_query(request.query, request.format.value)

    async def wikidata_get_entity_legacy(
        self, request: WikidataEntityRequest
    ) -> WikidataEntityResponse:
        """Legacy method that returns original response format"""
        source = self._get_source(SourceType.WIKIDATA)
        async with source:
            return await source.get_entity_data(
                request.entity_url, request.properties, request.format.value
            )

    async def wikidata_search_legacy(
        self, request: WikidataSearchRequest
    ) -> WikidataSearchResponse:
        """Legacy method that returns original response format"""
        source = self._get_source(SourceType.WIKIDATA)
        async with source:
            return await source.search(
                request.query, request.limit, request.offset, request.format.value
            )

    async def schema_org_get_entity_legacy(
        self, request: SchemaOrgEntityRequest
    ) -> SchemaOrgEntityResponse:
        """Legacy method that returns original response format"""
        source = self._get_source(SourceType.SCHEMA_ORG)
        async with source:
            return await source.get_entity(
                request.identifier, request.include_inherited, request.include_children
            )

    async def schema_org_get_property_legacy(
        self, request: SchemaOrgPropertyRequest
    ) -> SchemaOrgPropertyResponse:
        """Legacy method that returns original response format"""
        source = self._get_source(SourceType.SCHEMA_ORG)
        async with source:
            return await source.get_property(request.identifier, request.include_usage)

    async def schema_org_search_legacy(
        self, request: SchemaOrgSearchRequest
    ) -> SchemaOrgSearchResponse:
        """Legacy method that returns original response format"""
        source = self._get_source(SourceType.SCHEMA_ORG)
        async with source:
            return await source.search(
                query=request.query,
                search_type=request.search_type,
                limit=request.limit,
                offset=request.offset,
                similarity_threshold=request.similarity_threshold,
            )
