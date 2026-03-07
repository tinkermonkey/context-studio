"""Response building utilities for reference service.

This module provides consistent response construction for all reference service methods.
"""

from typing import List, Dict, Optional
import time

from .models import SearchNode, SearchLink, SourceType, MultiSourceSearchResponse
from utils.logger import get_logger

logger = get_logger(__name__)


class ResponseBuilder:
    """Builds consistent MultiSourceSearchResponse objects for all reference service methods."""

    def __init__(self):
        pass

    def build_single_source_response(self,
                                   source: SourceType,
                                   query: str,
                                   nodes: List[SearchNode],
                                   links: List[SearchLink],
                                   limit: int = 20,
                                   offset: int = 0,
                                   search_time_ms: Optional[float] = None,
                                   error: Optional[str] = None) -> MultiSourceSearchResponse:
        """
        Build a MultiSourceSearchResponse for a single source.

        Args:
            source: The source type that provided the data
            query: The original search query
            nodes: List of SearchNode objects
            links: List of SearchLink objects
            limit: The limit used for the search
            offset: The offset used for the search
            search_time_ms: Search time in milliseconds (will be calculated if not provided)
            error: Error message if the search failed

        Returns:
            MultiSourceSearchResponse object
        """
        if search_time_ms is None:
            search_time_ms = 0.0

        source_errors = {}
        if error:
            source_errors[source.value] = error

        return MultiSourceSearchResponse(
            query=query,
            results=nodes,
            links=links,
            total_results=len(nodes),
            total_links=len(links),
            sources_queried=[source.value],
            source_errors=source_errors,
            offset=offset,
            limit=limit,
            search_time_ms=search_time_ms
        )

    def build_multi_source_response(self,
                                  query: str,
                                  all_nodes: List[SearchNode],
                                  all_links: List[SearchLink],
                                  sources_queried: List[str],
                                  source_errors: Dict[str, str],
                                  limit: int = 20,
                                  offset: int = 0,
                                  search_time_ms: float = 0.0) -> MultiSourceSearchResponse:
        """
        Build a MultiSourceSearchResponse for multiple sources.

        Args:
            query: The original search query
            all_nodes: List of all SearchNode objects from all sources
            all_links: List of all SearchLink objects from all sources
            sources_queried: List of source names that were queried
            source_errors: Dictionary of errors per source
            limit: The limit used per source
            offset: The offset used for the search
            search_time_ms: Total search time in milliseconds

        Returns:
            MultiSourceSearchResponse object
        """
        return MultiSourceSearchResponse(
            query=query,
            results=all_nodes,
            links=all_links,
            total_results=len(all_nodes),
            total_links=len(all_links),
            sources_queried=sources_queried,
            source_errors=source_errors,
            offset=offset,
            limit=limit,
            search_time_ms=search_time_ms
        )

    def build_empty_response(self,
                           query: str,
                           source: Optional[SourceType] = None,
                           error: Optional[str] = None,
                           limit: int = 20,
                           offset: int = 0) -> MultiSourceSearchResponse:
        """
        Build an empty MultiSourceSearchResponse for cases where no results are found or errors occur.

        Args:
            query: The original search query
            source: The source type (if single source) that was queried
            error: Error message if applicable
            limit: The limit used for the search
            offset: The offset used for the search

        Returns:
            Empty MultiSourceSearchResponse object
        """
        sources_queried = [source.value] if source else []
        source_errors = {source.value: error} if source and error else {}

        return MultiSourceSearchResponse(
            query=query,
            results=[],
            links=[],
            total_results=0,
            total_links=0,
            sources_queried=sources_queried,
            source_errors=source_errors,
            offset=offset,
            limit=limit,
            search_time_ms=0.0
        )

    def build_error_response(self,
                           query: str,
                           error: str,
                           source: Optional[SourceType] = None,
                           limit: int = 20,
                           offset: int = 0) -> MultiSourceSearchResponse:
        """
        Build a MultiSourceSearchResponse for error cases.

        Args:
            query: The original search query
            error: The error message
            source: The source type that caused the error (if applicable)
            limit: The limit used for the search
            offset: The offset used for the search

        Returns:
            MultiSourceSearchResponse object with error information
        """
        sources_queried = [source.value] if source else []
        source_errors = {source.value: error} if source else {"general": error}

        return MultiSourceSearchResponse(
            query=query,
            results=[],
            links=[],
            total_results=0,
            total_links=0,
            sources_queried=sources_queried,
            source_errors=source_errors,
            offset=offset,
            limit=limit,
            search_time_ms=0.0
        )

    def merge_responses(self, responses: List[MultiSourceSearchResponse]) -> MultiSourceSearchResponse:
        """
        Merge multiple MultiSourceSearchResponse objects into a single response.
        This is a simple merge without deduplication - use ResultAggregator for more sophisticated merging.

        Args:
            responses: List of MultiSourceSearchResponse objects to merge

        Returns:
            Merged MultiSourceSearchResponse object
        """
        if not responses:
            return self.build_empty_response("")

        # Use the first response as a template
        base_response = responses[0]

        # Aggregate all data
        all_nodes = []
        all_links = []
        all_source_errors = {}
        all_sources_queried = []
        total_search_time = 0.0

        for response in responses:
            all_nodes.extend(response.results)
            all_links.extend(response.links)
            all_source_errors.update(response.source_errors)
            all_sources_queried.extend(response.sources_queried)
            total_search_time += response.search_time_ms

        # Remove duplicate sources from sources_queried
        unique_sources_queried = list(dict.fromkeys(all_sources_queried))

        return MultiSourceSearchResponse(
            query=base_response.query,
            results=all_nodes,
            links=all_links,
            total_results=len(all_nodes),
            total_links=len(all_links),
            sources_queried=unique_sources_queried,
            source_errors=all_source_errors,
            offset=base_response.offset,
            limit=base_response.limit,
            search_time_ms=total_search_time
        )

    def create_timing_wrapper(func):
        """
        Decorator to automatically time function calls and include timing in response.
        This is a utility method for use in the service layer.

        Args:
            func: Function to wrap with timing

        Returns:
            Wrapped function that includes timing information
        """
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                search_time_ms = (time.time() - start_time) * 1000

                # If the result is a MultiSourceSearchResponse, update its timing
                if isinstance(result, MultiSourceSearchResponse):
                    result.search_time_ms = search_time_ms

                return result
            except Exception as e:
                search_time_ms = (time.time() - start_time) * 1000
                logger.error(f"Function {func.__name__} failed after {search_time_ms:.2f}ms: {e}")
                raise

        return wrapper