"""DBpedia reference source adapter for knowledge base queries."""

import httpx

from domain.extraction.ports import ReferenceResult, ReferenceRelation
from utils.logger import get_logger

logger = get_logger(__name__)


class DBpediaSource:
    """
    Reference source adapter for DBpedia.

    Queries the DBpedia Lookup API for entity enrichment and relationship discovery.
    Gracefully handles network failures without raising exceptions.
    """

    LOOKUP_URL = "https://lookup.dbpedia.org/api/search"

    def __init__(self, timeout: int = 10):
        """
        Initialize the DBpedia source adapter.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self._timeout = timeout

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
        except Exception:
            return False

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for entities matching a term in DBpedia.

        Args:
            term: Search query
            limit: Maximum number of results to return

        Returns:
            List of ReferenceResult objects. Returns empty list on any error.
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
            results = []

            # Parse DBpedia Lookup API response
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
        except Exception as e:
            logger.warning(f"DBpedia search failed for '{term}': {e}")
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
