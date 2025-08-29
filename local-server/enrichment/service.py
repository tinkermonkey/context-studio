"""Core enrichment service coordinating all reference API sources"""

from typing import Dict, Any, Optional, List
import asyncio
import logging
from datetime import datetime, UTC

from config import EnrichmentConfig, SourceType
from .sources.dbpedia import DBpediaSource
from .sources.conceptnet import ConceptNetSource
from .sources.wikidata import WikidataSource
from .sources.schema_org import SchemaOrgSource
from .exceptions import EnrichmentError
from .models import *

logger = logging.getLogger(__name__)


class EnrichmentService:
    """Core enrichment service coordinating all reference API sources"""

    def __init__(self, config: EnrichmentConfig):
        self.config = config
        self._sources: Dict[SourceType, Any] = {}

    def _get_source(self, source_type: SourceType):
        """Get or create source instance"""
        if source_type not in self._sources:
            source_config = self.config.get_source_config(source_type)

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

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all configured sources"""
        health_status = {"overall": "healthy", "sources": {}, "timestamp": datetime.now(UTC)}

        for source_type in SourceType:
            source_config = self.config.get_source_config(source_type)
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
