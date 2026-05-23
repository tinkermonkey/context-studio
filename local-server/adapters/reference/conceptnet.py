"""ConceptNet reference source adapter for knowledge base queries."""

import httpx

from domain.extraction.ports import ReferenceRelation, ReferenceResult
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

logger = get_logger(__name__)


class ConceptNetSource:
    """
    Reference source adapter for ConceptNet 5.7.

    Queries the ConceptNet API for semantic relationships and concept definitions.
    Gracefully handles network failures without raising exceptions.
    """

    DEFAULT_BASE_URL = "https://api.conceptnet.io"

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: int = 10):
        """
        Initialize the ConceptNet source adapter.

        Args:
            base_url: ConceptNet API base URL
            timeout: HTTP request timeout in seconds
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def source_name(self) -> str:
        """
        Get the name of this reference source.

        Returns:
            Human-readable source name
        """
        return "ConceptNet"

    def is_available(self) -> bool:
        """
        Check if ConceptNet API is available.

        Returns:
            True if API responds with 200 status, False on any error
        """
        try:
            response = httpx.get(
                f"{self._base_url}/c/en/test",
                timeout=self._timeout,
            )
            return response.status_code == 200
        except httpx.TimeoutException as e:
            logger.warning(f"ConceptNet availability check timed out: {e}")
            return False
        except httpx.NetworkError as e:
            logger.warning(f"ConceptNet network error during availability check: {e}")
            return False
        except httpx.HTTPError as e:
            logger.warning(f"ConceptNet HTTP error during availability check: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during ConceptNet availability check: {e}")
            return False

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for concepts matching a term in ConceptNet.

        Args:
            term: Search query
            limit: Maximum number of results to return

        Returns:
            List of ReferenceResult objects. Returns empty list on network failures.
        """
        try:
            response = httpx.get(
                f"{self._base_url}/query",
                params={"text": term, "limit": limit},
                timeout=self._timeout,
            )
            response.raise_for_status()

            data = response.json()
            results = []

            # Parse ConceptNet API response
            if "edges" in data:
                seen_uris = set()
                for edge in data["edges"]:
                    start = edge.get("start", {})
                    uri = start.get("@id", "")
                    label = start.get("label", "")

                    if uri and uri not in seen_uris:
                        seen_uris.add(uri)
                        results.append(
                            ReferenceResult(
                                uri=uri,
                                label=label,
                                description=None,
                                source=self.source_name,
                            )
                        )

                    if len(results) >= limit:
                        break

            return results
        except httpx.TimeoutException as e:
            logger.warning(f"ConceptNet search timed out for '{term}': {e}")
            return []
        except httpx.NetworkError as e:
            logger.warning(f"ConceptNet network error during search for '{term}': {e}")
            return []
        except httpx.HTTPStatusError as e:
            logger.warning(
                f"ConceptNet HTTP {e.response.status_code} error during search for"
                f" '{term}': {e}"
            )
            return []
        except httpx.HTTPError as e:
            logger.warning(f"ConceptNet HTTP error during search for '{term}': {e}")
            return []
        except ValueError as e:
            logger.warning(f"ConceptNet JSON parse error during search for '{term}': {e}")
            return []
        except Exception as e:
            logger.warning(f"Unexpected error during ConceptNet search for '{term}': {e}")
            return []

    def get_relations(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Get relationships connected to a URI in ConceptNet.

        Args:
            uri: URI of the concept to find relations for
            limit: Maximum number of relations to return

        Returns:
            List of ReferenceRelation objects. Returns empty list on network failures.
        """
        try:
            response = httpx.get(
                f"{self._base_url}/query",
                params={"start": uri, "limit": limit},
                timeout=self._timeout,
            )
            response.raise_for_status()

            data = response.json()
            relations = []

            if "edges" in data:
                for edge in data["edges"][:limit]:
                    rel_type = edge.get("rel", {})
                    relation_label = rel_type.get("label", "")

                    start_obj = edge.get("start", {})
                    end_obj = edge.get("end", {})

                    subject_uri = start_obj.get("@id", "")
                    object_uri = end_obj.get("@id", "")

                    if subject_uri and object_uri:
                        relations.append(
                            ReferenceRelation(
                                subject_uri=subject_uri,
                                predicate=relation_label,
                                object_uri=object_uri,
                                source=self.source_name,
                            )
                        )

            return relations
        except httpx.TimeoutException as e:
            logger.warning(f"ConceptNet get_relations timed out for '{uri}': {e}")
            return []
        except httpx.NetworkError as e:
            logger.warning(f"ConceptNet network error during get_relations for '{uri}': {e}")
            return []
        except httpx.HTTPStatusError as e:
            logger.warning(
                f"ConceptNet HTTP {e.response.status_code} error during get_relations"
                f" for '{uri}': {e}"
            )
            return []
        except httpx.HTTPError as e:
            logger.warning(f"ConceptNet HTTP error during get_relations for '{uri}': {e}")
            return []
        except ValueError as e:
            logger.warning(f"ConceptNet JSON parse error during get_relations for '{uri}': {e}")
            return []
        except Exception as e:
            logger.warning(f"Unexpected error during ConceptNet get_relations for '{uri}': {e}")
            return []

    async def is_available_async(self) -> bool:
        """
        Check if ConceptNet API is available (async version).

        Delegates to sync method via executor to avoid code duplication.

        Returns:
            True if API responds with 200 status, False on any error
        """
        return await run_sync_in_executor(self.is_available)

    async def search_async(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for concepts matching a term in ConceptNet (async version).

        Delegates to sync method via executor to avoid code duplication.

        Args:
            term: Search query
            limit: Maximum number of results to return

        Returns:
            List of ReferenceResult objects. Returns empty list on network failures.
        """
        return await run_sync_in_executor(self.search, term, limit)

    async def get_relations_async(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Get relationships connected to a URI in ConceptNet (async version).

        Delegates to sync method via executor to avoid code duplication.

        Args:
            uri: URI of the concept to find relations for
            limit: Maximum number of relations to return

        Returns:
            List of ReferenceRelation objects. Returns empty list on network failures.
        """
        return await run_sync_in_executor(self.get_relations, uri, limit)

    async def cleanup_async(self) -> None:
        """
        Clean up resources.

        No-op for ConceptNet as sync client cleanup is handled separately.
        """
        pass
