"""Main service for unified reference access"""

from typing import List, Dict, Optional
import asyncio
import time
import logging

from .models import (
    UnifiedNode, UnifiedLink, UnifiedSearchRequest,
    UnifiedSearchResponse, UnifiedLinksRequest, UnifiedLinksResponse,
    ReferenceSource
)
from .adapters import get_adapter
from .cache import CacheManager
from .deduplication import DeduplicationEngine
from .ranking import RankingEngine
from .circuit_breaker import CircuitBreaker, CircuitBreakerError
from ..exceptions import EnrichmentError

logger = logging.getLogger(__name__)

class UnifiedReferenceService:
    """Main service for unified reference access across all sources"""

    def __init__(self):
        """Initialize the unified reference service"""
        self.adapters = self._initialize_adapters()
        self.cache_manager = CacheManager()
        self.dedup_engine = DeduplicationEngine()
        self.ranking_engine = RankingEngine()
        self.circuit_breakers = self._initialize_circuit_breakers()

    def _initialize_adapters(self) -> Dict[ReferenceSource, object]:
        """Initialize all available adapters"""
        adapters = {}

        for source in ReferenceSource:
            try:
                adapter = get_adapter(source)
                adapters[source] = adapter
                logger.info(f"Initialized adapter for {source.value}")
            except Exception as e:
                logger.warning(f"Failed to initialize adapter for {source.value}: {e}")

        return adapters

    def _initialize_circuit_breakers(self) -> Dict[ReferenceSource, CircuitBreaker]:
        """Initialize circuit breakers for each source"""
        circuit_breakers = {}

        for source in ReferenceSource:
            # Configure circuit breaker per source
            if source == ReferenceSource.WORDNET:
                # WordNet is local, so more lenient settings
                circuit_breaker = CircuitBreaker(
                    failure_threshold=10,
                    recovery_timeout=30,
                    success_threshold=2
                )
            else:
                # External sources get standard settings
                circuit_breaker = CircuitBreaker(
                    failure_threshold=5,
                    recovery_timeout=60,
                    success_threshold=3
                )

            circuit_breakers[source] = circuit_breaker

        return circuit_breakers

    async def search(self, request: UnifiedSearchRequest) -> UnifiedSearchResponse:
        """
        Unified search across configured sources

        Args:
            request: Search request parameters

        Returns:
            Unified search response with ranked, deduplicated results
        """
        start_time = time.time()

        # Generate cache key
        cache_key = self._generate_search_cache_key(request)

        # Check cache first
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for search query: {request.query}")
            return UnifiedSearchResponse(**cached_result)

        # Determine sources to query
        sources_to_query = request.sources or list(ReferenceSource)
        available_sources = [s for s in sources_to_query if s in self.adapters]

        if not available_sources:
            return UnifiedSearchResponse(
                query=request.query,
                results=[],
                total_results=0,
                sources_queried=[],
                source_errors={"general": "No available sources"},
                offset=request.offset,
                limit=request.limit,
                search_time_ms=0
            )

        # Query sources in parallel with circuit breaker protection
        search_tasks = []
        for source in available_sources:
            adapter = self.adapters[source]
            circuit_breaker = self.circuit_breakers[source]

            task = self._search_with_circuit_breaker(
                circuit_breaker,
                adapter,
                request.query,
                request.search_type,
                request.limit + request.offset,  # Get extra to handle offset after dedup
                0  # Start from 0, handle offset later
            )
            search_tasks.append((source, task))

        # Gather results with timeout
        results = await self._gather_with_timeout(search_tasks, timeout=10.0)

        # Process results
        all_nodes = []
        source_errors = {}
        sources_queried = []

        for source, result in results:
            sources_queried.append(source.value)

            if isinstance(result, Exception):
                source_errors[source.value] = str(result)
                logger.warning(f"Search failed for {source.value}: {result}")
            elif result:
                all_nodes.extend(result)
                logger.debug(f"Got {len(result)} results from {source.value}")

        # Deduplicate nodes
        logger.debug(f"Deduplicating {len(all_nodes)} nodes")
        deduplicated_nodes = await self.dedup_engine.deduplicate(all_nodes)

        # Rank results
        logger.debug(f"Ranking {len(deduplicated_nodes)} nodes")
        ranked_nodes = self.ranking_engine.rank(deduplicated_nodes, request.query)

        # Apply pagination
        total_results = len(ranked_nodes)
        paginated_nodes = ranked_nodes[request.offset:request.offset + request.limit]

        # Create response
        search_time_ms = (time.time() - start_time) * 1000
        response = UnifiedSearchResponse(
            query=request.query,
            results=paginated_nodes,
            total_results=total_results,
            sources_queried=sources_queried,
            source_errors=source_errors,
            offset=request.offset,
            limit=request.limit,
            search_time_ms=search_time_ms
        )

        # Cache the response
        await self.cache_manager.set(cache_key, response.dict(), memory_ttl=300, db_ttl=1800)

        logger.info(f"Search for '{request.query}' returned {len(paginated_nodes)} results in {search_time_ms:.2f}ms")
        return response

    async def get_node(self, node_id: str) -> Optional[UnifiedNode]:
        """
        Get details for a specific node

        Args:
            node_id: Unified node ID

        Returns:
            Node details if found, None otherwise
        """
        # Try cache first
        cache_key = f"node:{node_id}"
        cached_node = await self.cache_manager.get(cache_key)
        if cached_node:
            return UnifiedNode(**cached_node)

        # Extract source from node ID
        if ':' in node_id:
            source_prefix = node_id.split(':', 1)[0]
            try:
                source = ReferenceSource(source_prefix)
                if source in self.adapters:
                    # This would require additional implementation in adapters
                    # for now, return None as this is primarily a search interface
                    pass
            except ValueError:
                pass

        return None

    async def get_links(self, request: UnifiedLinksRequest) -> UnifiedLinksResponse:
        """
        Get links for a specific node

        Args:
            request: Links request parameters

        Returns:
            Links response with related nodes
        """
        start_time = time.time()

        # Generate cache key
        cache_key = self._generate_links_cache_key(request)

        # Check cache
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            return UnifiedLinksResponse(**cached_result)

        # Determine sources to query
        sources_to_query = request.sources or list(ReferenceSource)
        available_sources = [s for s in sources_to_query if s in self.adapters]

        # Query sources for links
        link_tasks = []
        for source in available_sources:
            adapter = self.adapters[source]
            circuit_breaker = self.circuit_breakers[source]

            task = self._get_links_with_circuit_breaker(
                circuit_breaker,
                adapter,
                request.node_id,
                request.direction
            )
            link_tasks.append((source, task))

        # Gather results
        results = await self._gather_with_timeout(link_tasks, timeout=10.0)

        # Process results
        all_links = []
        source_errors = {}
        sources_queried = []

        for source, result in results:
            sources_queried.append(source.value)

            if isinstance(result, Exception):
                source_errors[source.value] = str(result)
            elif result:
                all_links.extend(result)

        # Apply limit
        limited_links = all_links[:request.limit]

        # Create response
        search_time_ms = (time.time() - start_time) * 1000
        response = UnifiedLinksResponse(
            node_id=request.node_id,
            links=limited_links,
            total_links=len(all_links),
            sources_queried=sources_queried,
            source_errors=source_errors
        )

        # Cache the response
        await self.cache_manager.set(cache_key, response.dict(), memory_ttl=600, db_ttl=3600)

        return response

    async def _search_with_circuit_breaker(
        self,
        circuit_breaker: CircuitBreaker,
        adapter,
        query: str,
        search_type: str,
        limit: int,
        offset: int
    ) -> List[UnifiedNode]:
        """Execute search with circuit breaker protection"""
        try:
            return await circuit_breaker.call(
                adapter.search_nodes,
                query=query,
                search_type=search_type,
                limit=limit,
                offset=offset
            )
        except CircuitBreakerError as e:
            logger.warning(f"Circuit breaker open for {adapter.source_type.value}: {e}")
            return []
        except Exception as e:
            logger.error(f"Search failed for {adapter.source_type.value}: {e}")
            raise e

    async def _get_links_with_circuit_breaker(
        self,
        circuit_breaker: CircuitBreaker,
        adapter,
        node_id: str,
        direction: str
    ) -> List[UnifiedLink]:
        """Execute get_links with circuit breaker protection"""
        try:
            return await circuit_breaker.call(
                adapter.get_links,
                node_id=node_id,
                direction=direction
            )
        except CircuitBreakerError as e:
            logger.warning(f"Circuit breaker open for {adapter.source_type.value}: {e}")
            return []
        except Exception as e:
            logger.error(f"Get links failed for {adapter.source_type.value}: {e}")
            raise e

    async def _gather_with_timeout(
        self,
        tasks: List[tuple],
        timeout: float
    ) -> List[tuple]:
        """Gather task results with timeout protection"""
        results = []

        for source, task in tasks:
            try:
                result = await asyncio.wait_for(task, timeout=timeout)
                results.append((source, result))
            except asyncio.TimeoutError:
                error = f"Timeout after {timeout}s"
                results.append((source, TimeoutError(error)))
            except Exception as e:
                results.append((source, e))

        return results

    def _generate_search_cache_key(self, request: UnifiedSearchRequest) -> str:
        """Generate cache key for search request"""
        import hashlib
        import json

        key_data = {
            "query": request.query,
            "search_type": request.search_type,
            "sources": sorted([s.value for s in request.sources]) if request.sources else None,
            "limit": request.limit,
            "offset": request.offset
        }

        key_str = json.dumps(key_data, sort_keys=True)
        return f"search:{hashlib.md5(key_str.encode()).hexdigest()}"

    def _generate_links_cache_key(self, request: UnifiedLinksRequest) -> str:
        """Generate cache key for links request"""
        import hashlib
        import json

        key_data = {
            "node_id": request.node_id,
            "direction": request.direction,
            "sources": sorted([s.value for s in request.sources]) if request.sources else None,
            "limit": request.limit
        }

        key_str = json.dumps(key_data, sort_keys=True)
        return f"links:{hashlib.md5(key_str.encode()).hexdigest()}"

    async def get_health(self) -> Dict[str, any]:
        """Get health status of all sources and components"""
        health = {
            "overall": "healthy",
            "timestamp": time.time(),
            "sources": {},
            "circuit_breakers": {},
            "cache": {}
        }

        # Check circuit breaker states
        for source, cb in self.circuit_breakers.items():
            cb_stats = cb.get_stats()
            health["circuit_breakers"][source.value] = cb_stats

            if cb.is_open:
                health["overall"] = "degraded"

        # Check cache health
        try:
            cache_stats = await self.cache_manager.get_stats()
            health["cache"] = cache_stats
        except Exception as e:
            health["cache"] = {"error": str(e)}
            health["overall"] = "degraded"

        # Check adapter availability
        for source, adapter in self.adapters.items():
            try:
                # Simple health check - this could be enhanced per adapter
                health["sources"][source.value] = "available"
            except Exception as e:
                health["sources"][source.value] = f"error: {str(e)}"
                health["overall"] = "degraded"

        return health

    async def get_stats(self) -> Dict[str, any]:
        """Get service statistics"""
        stats = {
            "adapters_count": len(self.adapters),
            "available_sources": list(self.adapters.keys()),
            "cache_stats": await self.cache_manager.get_stats(),
            "circuit_breaker_stats": {
                source.value: cb.get_stats()
                for source, cb in self.circuit_breakers.items()
            }
        }

        return stats