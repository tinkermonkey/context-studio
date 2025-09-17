"""Core enrichment service coordinating all reference API sources"""

from typing import Dict, Any, Optional, List
import asyncio
import aiohttp
from datetime import datetime, UTC

from config import get_config_manager, ConfigurationManager
from .exceptions import EnrichmentError
from .models import *
import time
from .sources import DBpediaSource, ConceptNetSource, WikidataSource, SchemaOrgSource
from utils.logger import get_logger

logger = get_logger(__name__)


class EnrichmentService:
    """Core enrichment service coordinating all reference API sources"""

    def __init__(self, config_manager: ConfigurationManager = None):
        self.config_manager = config_manager or get_config_manager()
        self.settings = self.config_manager.settings
        self._sources = {}  # Cache for source instances

    def _get_source(self, source_type: SourceType):
        """Get or create source instance"""
        if source_type not in self._sources:
            source_config = self.settings.get_source_config(source_type.value)

            if source_type == SourceType.DBPEDIA:
                self._sources[source_type] = DBpediaSource(source_type, source_config)
            elif source_type == SourceType.CONCEPTNET:
                self._sources[source_type] = ConceptNetSource(source_type, source_config)
            elif source_type == SourceType.WIKIDATA:
                self._sources[source_type] = WikidataSource(source_type, source_config)
            elif source_type == SourceType.SCHEMA_ORG:
                self._sources[source_type] = SchemaOrgSource(source_type, source_config)
            else:
                raise EnrichmentError(f"Unknown source type: {source_type}")

        return self._sources[source_type]

    # DBpedia methods
    async def dbpedia_get_resource(self, request: DBpediaResourceRequest) -> DBpediaResourceResponse:
        """Get DBpedia resource data"""
        source = self._get_source(SourceType.DBPEDIA)
        async with source:
            return await source.get_resource_data(request.resource_url, request.format.value)

    async def dbpedia_search(self, request: DBpediaSearchRequest) -> DBpediaSearchResponse:
        """Search DBpedia"""
        source = self._get_source(SourceType.DBPEDIA)
        async with source:
            return await source.search(request.query, request.limit, request.offset, request.format.value)

    async def dbpedia_sparql(self, request: DBpediaSparqlRequest) -> DBpediaSparqlResponse:
        """Execute DBpedia SPARQL query"""
        source = self._get_source(SourceType.DBPEDIA)
        async with source:
            return await source.sparql_query(request.query, request.format.value)

    # ConceptNet methods
    async def conceptnet_query(self, request: ConceptNetQueryRequest) -> ConceptNetQueryResponse:
        """Query ConceptNet"""
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

    async def conceptnet_get_concept(self, concept_path: str) -> ConceptNetConceptResponse:
        """Get ConceptNet concept"""
        source = self._get_source(SourceType.CONCEPTNET)
        async with source:
            return await source.get_concept(concept_path)

    async def conceptnet_get_related(self, concept_path: str, filter: Optional[str] = None, limit: int = 20) -> ConceptNetRelatedResponse:
        """Get ConceptNet related concepts"""
        source = self._get_source(SourceType.CONCEPTNET)
        async with source:
            return await source.get_related(concept_path, filter, limit)

    # Wikidata methods
    async def wikidata_sparql(self, request: WikidataSparqlRequest) -> WikidataSparqlResponse:
        """Execute Wikidata SPARQL query"""
        source = self._get_source(SourceType.WIKIDATA)
        async with source:
            return await source.sparql_query(request.query, request.format.value)

    async def wikidata_get_entity(self, request: WikidataEntityRequest) -> WikidataEntityResponse:
        """Get Wikidata entity data"""
        source = self._get_source(SourceType.WIKIDATA)
        async with source:
            return await source.get_entity_data(request.entity_url, request.properties, request.format.value)

    # Schema.org methods
    async def schema_org_get_entity(self, request: SchemaOrgEntityRequest) -> SchemaOrgEntityResponse:
        """Get Schema.org entity"""
        source = self._get_source(SourceType.SCHEMA_ORG)
        async with source:
            return await source.get_entity(request.identifier, request.include_inherited, request.include_children)

    async def schema_org_get_property(self, request: SchemaOrgPropertyRequest) -> SchemaOrgPropertyResponse:
        """Get Schema.org property"""
        source = self._get_source(SourceType.SCHEMA_ORG)
        async with source:
            return await source.get_property(request.identifier, request.include_usage)

    async def schema_org_search(self, request: SchemaOrgSearchRequest) -> SchemaOrgSearchResponse:
        """Search Schema.org entities and properties"""
        source = self._get_source(SourceType.SCHEMA_ORG)
        async with source:
            return await source.search(
                query=request.query,
                search_type=request.search_type,
                limit=request.limit,
                offset=request.offset,
                similarity_threshold=request.similarity_threshold,
            )

    # Multi-source search method
    async def search(self, request: MultiSourceSearchRequest) -> MultiSourceSearchResponse:
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
            SourceType.SCHEMA_ORG
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

        logger.info(f"Querying {len(enabled_sources)} enabled sources: {[s.value for s in enabled_sources]}")

        # Search each source in parallel
        search_tasks = []
        for source_type in enabled_sources:
            task = self._search_single_source(source_type, request.query, request.limit, request.offset)
            search_tasks.append((source_type, task))

        # Execute all searches in parallel
        results = await self._gather_search_results(search_tasks)

        # Aggregate results
        all_nodes = []
        source_errors = {}
        sources_queried = []

        for source_type, result in results:
            sources_queried.append(source_type.value)

            if isinstance(result, Exception):
                source_errors[source_type.value] = str(result)
                logger.warning(f"Search failed for {source_type.value}: {result}")
            elif result:
                all_nodes.extend(result)
                logger.info(f"Source {source_type.value}: added {len(result)} results")
            else:
                logger.info(f"Source {source_type.value}: no results")

        # Simple result aggregation (no deduplication or ranking)
        total_results = len(all_nodes)

        # Create response
        search_time_ms = (time.time() - start_time) * 1000
        response = MultiSourceSearchResponse(
            query=request.query,
            results=all_nodes,
            total_results=total_results,
            sources_queried=sources_queried,
            source_errors=source_errors,
            offset=request.offset,
            limit=request.limit,
            search_time_ms=search_time_ms
        )

        logger.info(f"Multi-source search completed: '{request.query}' returned {total_results} results in {search_time_ms:.2f}ms")
        return response

    async def _search_single_source(self, source_type: SourceType, query: str, limit: int, offset: int) -> List[SearchNode]:
        """Search a single source and convert results to SearchNode format"""
        try:
            logger.debug(f"Searching {source_type.value} for '{query}'")

            if source_type == SourceType.DBPEDIA:
                request = DBpediaSearchRequest(query=query, limit=limit, offset=offset)
                response = await self.dbpedia_search(request)
                # Normalize DBpedia scores to 0-1 range
                max_score = max((result.score for result in response.results), default=1.0)
                return [
                    SearchNode(
                        id=f"dbpedia:{result.uri}",
                        source=SourceType.DBPEDIA,
                        title=result.label,
                        definition=result.description,
                        attributes={"types": result.types, "uri": result.uri, "raw_score": result.score},
                        source_url=result.uri,
                        relevance_score=min(result.score / max_score, 1.0)
                    )
                    for result in response.results
                ]

            elif source_type == SourceType.CONCEPTNET:
                request = ConceptNetQueryRequest(node=f"/c/en/{query.lower().replace(' ', '_')}", limit=limit, offset=offset)
                response = await self.conceptnet_query(request)
                nodes = []
                for edge in response.edges:
                    # Create nodes for both start and end concepts
                    if edge.start and edge.start.get('@id'):
                        nodes.append(SearchNode(
                            id=f"conceptnet:{edge.start['@id']}",
                            source=SourceType.CONCEPTNET,
                            title=edge.start.get('label', edge.start['@id'].split('/')[-1]),
                            definition=f"Related via {edge.rel.get('label', '')}",
                            attributes={"weight": edge.weight, "relation": edge.rel},
                            source_url=f"http://conceptnet.io{edge.start['@id']}",
                            relevance_score=min(edge.weight, 1.0)
                        ))
                return nodes

            elif source_type == SourceType.WIKIDATA:
                # For Wikidata, use a simpler search approach that's more efficient
                # Escape query string to prevent SPARQL injection
                escaped_query = query.replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')
                sparql_query = f"""
                SELECT ?item ?itemLabel ?itemDescription WHERE {{
                  ?item rdfs:label "{escaped_query}"@en .
                  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
                }}
                LIMIT {limit}
                OFFSET {offset}
                """
                request = WikidataSparqlRequest(query=sparql_query)
                response = await self.wikidata_sparql(request)
                nodes = []
                if response.success and response.results and 'results' in response.results and 'bindings' in response.results['results']:
                    for binding in response.results['results']['bindings']:
                        if 'item' in binding:
                            item_uri = binding['item'].get('value', '')
                            label = binding.get('itemLabel', {}).get('value', item_uri.split('/')[-1])
                            description = binding.get('itemDescription', {}).get('value', '')
                            nodes.append(SearchNode(
                                id=f"wikidata:{item_uri}",
                                source=SourceType.WIKIDATA,
                                title=label,
                                definition=description,
                                attributes={"uri": item_uri},
                                source_url=item_uri,
                                relevance_score=1.0
                            ))
                return nodes

            elif source_type == SourceType.SCHEMA_ORG:
                request = SchemaOrgSearchRequest(query=query, limit=limit, offset=offset)
                response = await self.schema_org_search(request)
                return [
                    SearchNode(
                        id=f"schema_org:{result.identifier}",
                        source=SourceType.SCHEMA_ORG,
                        title=result.title,
                        definition=result.definition,
                        attributes={"type": result.type, "identifier": result.identifier},
                        source_url=f"https://schema.org/{result.identifier}",
                        relevance_score=result.relevance_score
                    )
                    for result in response.results
                ]

            else:
                logger.warning(f"Unknown source type: {source_type}")
                return []

        except Exception as e:
            logger.error(f"Error searching {source_type.value}: {e}")
            raise e

    async def _gather_search_results(self, search_tasks: List[tuple]) -> List[tuple]:
        """Execute search tasks in parallel and gather results"""
        results = []

        # Extract tasks for parallel execution
        task_coroutines = [task for _, task in search_tasks]
        sources = [source for source, _ in search_tasks]

        try:
            # Run all tasks in parallel with a timeout
            completed_results = await asyncio.wait_for(
                asyncio.gather(*task_coroutines, return_exceptions=True),
                timeout=10.0
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

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all configured sources"""
        health_status = {"overall": "healthy", "sources": {}, "timestamp": datetime.now(UTC)}

        for source_type in SourceType:
            source_config = self.settings.get_source_config(source_type.value)
            if source_config.enabled:
                try:
                    source = self._get_source(source_type)
                    # Special-case schema_org: use manager status (synchronous) instead of HTTP HEAD
                    if source_type == SourceType.SCHEMA_ORG and hasattr(source, 'manager'):
                        # run manager.get_status in threadpool to avoid blocking
                        loop = asyncio.get_event_loop()
                        status = await loop.run_in_executor(None, source.manager.get_status)
                        # consider healthy if populated or no errors
                        if status and status.get('is_populated'):
                            health_status['sources'][source_type.value] = 'healthy'
                        else:
                            health_status['sources'][source_type.value] = f"unhealthy: {status}"
                            health_status['overall'] = 'degraded'
                    else:
                        async with source:
                            # For Wikidata, include a User-Agent header to avoid 403 responses
                            headers = {}
                            if source_type == SourceType.WIKIDATA:
                                headers['User-Agent'] = 'ContextStudio/LocalServer (contact: devnull@example.com)'
                            # Perform a simple health check request
                            await source._make_request("HEAD", source._get_base_url(), headers=headers)
                    health_status["sources"][source_type.value] = "healthy"
                except Exception as e:
                    health_status["sources"][source_type.value] = f"unhealthy: {str(e)}"
                    health_status["overall"] = "degraded"
            else:
                health_status["sources"][source_type.value] = "disabled"

        return health_status

    def get_enabled_sources(self) -> List[str]:
        """Get list of enabled enrichment sources"""
        enabled_sources = []
        sources = ["conceptnet", "dbpedia", "dbpedia_spotlight", "wikidata", "schema_org"]
        
        for source_name in sources:
            config = getattr(self.settings.reference_sources, source_name)
            if config.enabled:
                enabled_sources.append(source_name)
                
        return enabled_sources
        
    async def get_source_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all reference sources"""
        status = {}
        for source_name in ["conceptnet", "dbpedia", "dbpedia_spotlight", "wikidata", "schema_org"]:
            config = getattr(self.settings.reference_sources, source_name)
            status[source_name] = {
                "enabled": config.enabled,
                "use_proxy": config.use_proxy,
                "upstream_url": config.upstream_url,
                "timeout": config.timeout,
                "rate_limit": config.rate_limit.requests_per_hour
            }
        return status
