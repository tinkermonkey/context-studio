"""DBpedia reference source adapter for knowledge base queries."""

import httpx

from domain.extraction.ports import ReferenceRelation, ReferenceResult
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

logger = get_logger(__name__)


class DBpediaSource:
    """
    Reference source adapter for DBpedia.

    Queries the DBpedia Lookup API for entity enrichment and relationship discovery.
    Gracefully handles network failures without raising exceptions.
    """

    LOOKUP_URL = "https://lookup.dbpedia.org/api/search"

    def __init__(self, timeout: int = 10, async_client: httpx.AsyncClient | None = None):
        """
        Initialize the DBpedia source adapter.

        Args:
            timeout: HTTP request timeout in seconds
            async_client: Optional httpx.AsyncClient for async operations (e.g., with cassettes)
        """
        self._timeout = timeout
        self._async_client = async_client

    @property
    def source_name(self) -> str:
        """
        Get the name of this reference source.

        Returns:
            Human-readable source name
        """
        return "DBpedia"

    def is_available(self) -> bool:
        """
        Check if DBpedia Lookup API is available.

        Returns:
            True if API responds, False on any error
        """
        try:
            response = httpx.get(
                self.LOOKUP_URL,
                params={"query": "test", "format": "json"},
                timeout=self._timeout,
            )
            return response.status_code == 200
        except httpx.TimeoutException as e:
            logger.warning(f"DBpedia availability check timed out: {e}")
            return False
        except httpx.NetworkError as e:
            logger.warning(f"DBpedia network error during availability check: {e}")
            return False
        except httpx.HTTPError as e:
            logger.warning(f"DBpedia HTTP error during availability check: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during DBpedia availability check: {e}")
            return False

    def _parse_search_response(self, data: dict, limit: int) -> list[ReferenceResult]:
        """Parse DBpedia search response into ReferenceResult objects."""
        results = []
        if "results" in data:
            for result in data["results"][:limit]:
                uri = result.get("uri", "")
                label = result.get("label", "")
                description = result.get("description", None)

                if uri:
                    results.append(
                        ReferenceResult(
                            uri=uri,
                            label=label,
                            description=description,
                            source=self.source_name,
                        )
                    )
        return results

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for entities matching a term in DBpedia.

        Args:
            term: Search query
            limit: Maximum number of results to return

        Returns:
            List of ReferenceResult objects. Returns empty list on network failures.
        """
        try:
            response = httpx.get(
                self.LOOKUP_URL,
                params={
                    "query": term,
                    "format": "json",
                    "maxResults": limit,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_search_response(data, limit)
        except httpx.TimeoutException as e:
            logger.warning(f"DBpedia search timed out for '{term}': {e}")
            return []
        except httpx.NetworkError as e:
            logger.warning(f"DBpedia network error during search for '{term}': {e}")
            return []
        except httpx.HTTPStatusError as e:
            logger.warning(
                f"DBpedia HTTP {e.response.status_code} error during search for" f" '{term}': {e}"
            )
            return []
        except httpx.HTTPError as e:
            logger.warning(f"DBpedia HTTP error during search for '{term}': {e}")
            return []
        except ValueError as e:
            logger.warning(f"DBpedia JSON parse error during search for '{term}': {e}")
            return []

    def get_relations(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Get relationships connected to a URI in DBpedia.

        DBpedia's public SPARQL endpoint is rate-limited. This returns empty results
        to avoid API throttling. For real implementation, would use DBpedia's
        SPARQL endpoint with appropriate rate limiting.

        Args:
            uri: URI of the resource to find relations for
            limit: Maximum number of relations to return

        Returns:
            Empty list (DBpedia SPARQL requires rate limiting not implemented here)
        """
        logger.debug(
            f"DBpedia get_relations not implemented for '{uri}' "
            "(requires SPARQL with rate limiting)"
        )
        return []

    async def is_available_async(self) -> bool:
        """
        Check if DBpedia Lookup API is available (async version).

        Delegates to sync method via executor to avoid code duplication.

        Returns:
            True if API responds, False on any error
        """
        return await run_sync_in_executor(self.is_available)

    async def search_async(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for entities matching a term in DBpedia (async version).

        Uses provided async client if available, otherwise delegates to sync method.

        Args:
            term: Search query
            limit: Maximum number of results to return

        Returns:
            List of ReferenceResult objects. Returns empty list on network failures.
        """
        if self._async_client is None:
            return await run_sync_in_executor(self.search, term, limit)

        try:
            response = await self._async_client.get(
                self.LOOKUP_URL,
                params={
                    "query": term,
                    "format": "json",
                    "maxResults": limit,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_search_response(data, limit)
        except httpx.TimeoutException as e:
            logger.warning(f"DBpedia search timed out for '{term}': {e}")
            return []
        except httpx.NetworkError as e:
            logger.warning(f"DBpedia network error during search for '{term}': {e}")
            return []
        except httpx.HTTPStatusError as e:
            logger.warning(
                f"DBpedia HTTP {e.response.status_code} error during search for '{term}': {e}"
            )
            return []
        except httpx.HTTPError as e:
            logger.warning(f"DBpedia HTTP error during search for '{term}': {e}")
            return []
        except ValueError as e:
            logger.warning(f"DBpedia JSON parse error during search for '{term}': {e}")
            return []

    async def get_relations_async(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Get relationships connected to a URI in DBpedia (async version).

        Returns:
            Empty list (DBpedia SPARQL requires rate limiting not implemented here)
        """
        logger.debug(
            f"DBpedia get_relations not implemented for '{uri}' "
            "(requires SPARQL with rate limiting)"
        )
        return []

    async def cleanup_async(self) -> None:
        """
        Clean up resources.

        No-op for DBpedia as sync client cleanup is handled separately.
        """
        pass
