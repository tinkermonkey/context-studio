"""ConceptNet reference source adapter for knowledge base queries."""

import httpx

from domain.extraction.ports import ReferenceResult, ReferenceRelation
from utils.logger import get_logger

logger = get_logger(__name__)


class ConceptNetSource:
    """
    Reference source adapter for ConceptNet 5.7.

    Queries the ConceptNet API for semantic relationships and concept definitions.
    Gracefully handles network failures without raising exceptions.
    """

    BASE_URL = "https://api.conceptnet.io"

    def __init__(self, timeout: int = 10):
        """
        Initialize the ConceptNet source adapter.

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
        return "ConceptNet"

    def is_available(self) -> bool:
        """
        Check if ConceptNet API is available.

        Returns:
            True if API responds with 200 status, False on any error
        """
        try:
            response = httpx.get(
                f"{self.BASE_URL}/c/en/test",
                timeout=self._timeout,
            )
            return response.status_code == 200
        except Exception:
            return False

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for concepts matching a term in ConceptNet.

        Args:
            term: Search query
            limit: Maximum number of results to return

        Returns:
            List of ReferenceResult objects. Returns empty list on any error.
        """
        try:
            response = httpx.get(
                f"{self.BASE_URL}/query",
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
        except Exception as e:
            logger.warning(f"ConceptNet search failed for '{term}': {e}")
            return []

    def get_relations(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Get relationships connected to a URI in ConceptNet.

        Args:
            uri: URI of the concept to find relations for
            limit: Maximum number of relations to return

        Returns:
            List of ReferenceRelation objects. Returns empty list on any error.
        """
        try:
            response = httpx.get(
                f"{self.BASE_URL}/query",
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
        except Exception as e:
            logger.warning(f"ConceptNet get_relations failed for '{uri}': {e}")
            return []
