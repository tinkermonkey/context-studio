"""Wikidata reference source adapter for knowledge base queries."""

import httpx

from adapters.reference.exceptions import (
    ReferenceSourceNetworkError,
    ReferenceSourceTimeoutError,
    ReferenceSourceHTTPError,
    ReferenceSourceParseError,
)
from domain.extraction.ports import ReferenceResult, ReferenceRelation
from utils.logger import get_logger

logger = get_logger(__name__)


class WikidataSource:
    """
    Reference source adapter for Wikidata.

    Queries the Wikidata API for entity enrichment and relationship discovery.
    Gracefully handles network failures without raising exceptions.
    """

    BASE_URL = "https://www.wikidata.org/w/api.php"

    def __init__(self, timeout: int = 10):
        """
        Initialize the Wikidata source adapter.

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
        return "Wikidata"

    def is_available(self) -> bool:
        """
        Check if Wikidata API is available.

        Returns:
            True if API responds, False on any error
        """
        try:
            response = httpx.get(
                self.BASE_URL,
                params={
                    "action": "wbsearchentities",
                    "search": "test",
                    "format": "json",
                },
                timeout=self._timeout,
            )
            return response.status_code == 200
        except httpx.TimeoutException as e:
            logger.warning(f"Wikidata availability check timed out: {e}")
            return False
        except httpx.NetworkError as e:
            logger.warning(f"Wikidata network error during availability check: {e}")
            return False
        except httpx.HTTPError as e:
            logger.warning(f"Wikidata HTTP error during availability check: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during Wikidata availability check: {e}")
            return False

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for entities matching a term in Wikidata.

        Args:
            term: Search query
            limit: Maximum number of results to return

        Returns:
            List of ReferenceResult objects.

        Raises:
            ReferenceSourceNetworkError: On network connectivity issues
            ReferenceSourceTimeoutError: On request timeout
            ReferenceSourceHTTPError: On HTTP error responses
            ReferenceSourceParseError: On JSON parsing failures
        """
        try:
            response = httpx.get(
                self.BASE_URL,
                params={
                    "action": "wbsearchentities",
                    "search": term,
                    "language": "en",
                    "limit": limit,
                    "format": "json",
                },
                timeout=self._timeout,
            )
            response.raise_for_status()

            data = response.json()
            results = []

            # Parse Wikidata API response
            if "search" in data:
                for item in data["search"][:limit]:
                    entity_id = item.get("id", "")
                    label = item.get("label", "")
                    description = item.get("description", None)

                    if entity_id:
                        uri = f"http://www.wikidata.org/entity/{entity_id}"
                        results.append(
                            ReferenceResult(
                                uri=uri,
                                label=label,
                                description=description,
                                source=self.source_name,
                            )
                        )

            return results
        except httpx.TimeoutException as e:
            logger.error(f"Wikidata search timed out for '{term}': {e}")
            raise ReferenceSourceTimeoutError(
                f"Wikidata search timed out for '{term}'"
            ) from e
        except httpx.NetworkError as e:
            logger.error(f"Wikidata network error during search for '{term}': {e}")
            raise ReferenceSourceNetworkError(
                f"Wikidata network error during search for '{term}'"
            ) from e
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Wikidata HTTP {e.response.status_code} error during search for '{term}': {e}"
            )
            raise ReferenceSourceHTTPError(
                f"Wikidata returned HTTP {e.response.status_code} for search '{term}'"
            ) from e
        except httpx.HTTPError as e:
            logger.error(f"Wikidata HTTP error during search for '{term}': {e}")
            raise ReferenceSourceHTTPError(
                f"Wikidata HTTP error during search for '{term}'"
            ) from e
        except ValueError as e:
            logger.error(f"Wikidata JSON parse error during search for '{term}': {e}")
            raise ReferenceSourceParseError(
                f"Wikidata returned invalid JSON for search '{term}'"
            ) from e

    def get_relations(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Get relationships connected to a URI in Wikidata.

        Wikidata URIs are typically in the form http://www.wikidata.org/entity/Q123456.
        This extracts the entity ID and queries the property claims.

        Args:
            uri: URI of the entity to find relations for
            limit: Maximum number of relations to return

        Returns:
            List of ReferenceRelation objects.

        Raises:
            ReferenceSourceNetworkError: On network connectivity issues
            ReferenceSourceTimeoutError: On request timeout
            ReferenceSourceHTTPError: On HTTP error responses
            ReferenceSourceParseError: On JSON parsing failures
        """
        try:
            # Extract entity ID from Wikidata URI
            # Expected format: http://www.wikidata.org/entity/Q123456
            entity_id = uri.split("/")[-1]
            if not entity_id.startswith("Q"):
                return []

            response = httpx.get(
                self.BASE_URL,
                params={
                    "action": "wbgetentities",
                    "ids": entity_id,
                    "props": "claims",
                    "format": "json",
                },
                timeout=self._timeout,
            )
            response.raise_for_status()

            data = response.json()
            relations = []

            # Parse claims from Wikidata entity
            if "entities" in data and entity_id in data["entities"]:
                entity = data["entities"][entity_id]
                if "claims" in entity:
                    claims_count = 0
                    for prop_id, claims in entity["claims"].items():
                        for claim in claims:
                            if claims_count >= limit:
                                break

                            # Extract the target value (object URI)
                            if "mainsnak" in claim:
                                mainsnak = claim["mainsnak"]
                                if mainsnak.get("snaktype") == "value":
                                    value = mainsnak.get("datavalue", {}).get("value", {})
                                    if isinstance(value, dict) and "entity-type" in value:
                                        target_id = value.get("id", "")
                                        if target_id and target_id.startswith("Q"):
                                            relations.append(
                                                ReferenceRelation(
                                                    subject_uri=uri,
                                                    predicate=prop_id,
                                                    object_uri=f"http://www.wikidata.org/entity/{target_id}",
                                                    source=self.source_name,
                                                )
                                            )
                                            claims_count += 1

            return relations
        except httpx.TimeoutException as e:
            logger.error(f"Wikidata get_relations timed out for '{uri}': {e}")
            raise ReferenceSourceTimeoutError(
                f"Wikidata get_relations timed out for '{uri}'"
            ) from e
        except httpx.NetworkError as e:
            logger.error(
                f"Wikidata network error during get_relations for '{uri}': {e}"
            )
            raise ReferenceSourceNetworkError(
                f"Wikidata network error during get_relations for '{uri}'"
            ) from e
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Wikidata HTTP {e.response.status_code} error during get_relations for '{uri}': {e}"
            )
            raise ReferenceSourceHTTPError(
                f"Wikidata returned HTTP {e.response.status_code} for get_relations '{uri}'"
            ) from e
        except httpx.HTTPError as e:
            logger.error(f"Wikidata HTTP error during get_relations for '{uri}': {e}")
            raise ReferenceSourceHTTPError(
                f"Wikidata HTTP error during get_relations for '{uri}'"
            ) from e
        except ValueError as e:
            logger.error(
                f"Wikidata JSON parse error during get_relations for '{uri}': {e}"
            )
            raise ReferenceSourceParseError(
                f"Wikidata returned invalid JSON for get_relations '{uri}'"
            ) from e
