"""schema.org reference source adapter for vocabulary definitions."""

from adapters.reference.exceptions import (
    ReferenceSourceError,
    ReferenceSourceParseError,
)
from domain.extraction.ports import ReferenceRelation, ReferenceResult
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

logger = get_logger(__name__)

# Minimal schema.org vocabulary subset for common entity types
# In a production system, this would be loaded from a comprehensive JSON-LD file
SCHEMA_ORG_DEFINITIONS = {
    "Person": {
        "uri": "http://schema.org/Person",
        "label": "Person",
        "description": "A person (alive, dead, undead, or fictional).",
    },
    "Organization": {
        "uri": "http://schema.org/Organization",
        "label": "Organization",
        "description": "An organization such as a school, NGO, corporation, club, etc.",
    },
    "Place": {
        "uri": "http://schema.org/Place",
        "label": "Place",
        "description": "Entities that have a somewhat fixed, physical extension.",
    },
    "Event": {
        "uri": "http://schema.org/Event",
        "label": "Event",
        "description": "An event happening at a certain time and location.",
    },
    "Thing": {
        "uri": "http://schema.org/Thing",
        "label": "Thing",
        "description": "The most generic type of item.",
    },
    "Product": {
        "uri": "http://schema.org/Product",
        "label": "Product",
        "description": "Any offered product or service.",
    },
    "CreativeWork": {
        "uri": "http://schema.org/CreativeWork",
        "label": "CreativeWork",
        "description": "The most generic kind of creative work.",
    },
}

# Schema.org type hierarchy (simplified)
SCHEMA_ORG_RELATIONS = {
    "Person": [("subClassOf", "Thing")],
    "Organization": [("subClassOf", "Thing")],
    "Place": [("subClassOf", "Thing")],
    "Event": [("subClassOf", "Thing")],
    "Product": [("subClassOf", "Thing")],
    "CreativeWork": [("subClassOf", "Thing")],
}


class SchemaOrgSource:
    """
    Reference source adapter for schema.org vocabulary.

    Provides local, offline access to schema.org type definitions.
    This is always available and never makes network requests.
    """

    def __init__(self, timeout: int = 10):
        """
        Initialize the schema.org source adapter.

        Args:
            timeout: Unused (included for protocol compatibility)
        """
        self._timeout = timeout

    @property
    def source_name(self) -> str:
        """
        Get the name of this reference source.

        Returns:
            Human-readable source name
        """
        return "schema.org"

    def is_available(self) -> bool:
        """
        Check if schema.org vocabulary is available.

        Always returns True since schema.org is a local vocabulary.

        Returns:
            True (always available)
        """
        return True

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for schema.org type definitions matching a term.

        Performs substring matching on labels and descriptions (case-insensitive).

        Args:
            term: Search query
            limit: Maximum number of results to return

        Returns:
            List of ReferenceResult objects matching the term

        Raises:
            ReferenceSourceParseError: On unexpected data structure errors
        """
        try:
            term_lower = term.lower()
            results = []

            for key, definition in SCHEMA_ORG_DEFINITIONS.items():
                label_match = term_lower in definition["label"].lower()
                desc_match = (
                    term_lower in definition["description"].lower()
                    if definition.get("description")
                    else False
                )

                if label_match or desc_match:
                    results.append(
                        ReferenceResult(
                            uri=definition["uri"],
                            label=definition["label"],
                            description=definition["description"],
                            source=self.source_name,
                        )
                    )

                if len(results) >= limit:
                    break

            return results
        except KeyError as e:
            logger.error(f"schema.org malformed definition structure for '{term}': {e}")
            raise ReferenceSourceParseError(
                "schema.org vocabulary has malformed definition"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error during schema.org search for '{term}': {e}")
            raise ReferenceSourceError(
                "Unexpected error during schema.org search"
            ) from e

    def get_relations(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Get relationships connected to a URI in schema.org.

        Retrieves the type hierarchy relationships for a given schema.org type.

        Args:
            uri: URI of the type to find relations for (e.g., http://schema.org/Person)
            limit: Maximum number of relations to return

        Returns:
            List of ReferenceRelation objects

        Raises:
            ReferenceSourceParseError: On unexpected data structure errors
        """
        try:
            # Extract type name from URI
            # Expected format: http://schema.org/TypeName
            type_name = uri.split("/")[-1]

            relations = []
            if type_name in SCHEMA_ORG_RELATIONS:
                for predicate, object_type in SCHEMA_ORG_RELATIONS[type_name][:limit]:
                    relations.append(
                        ReferenceRelation(
                            subject_uri=uri,
                            predicate=predicate,
                            object_uri=f"http://schema.org/{object_type}",
                            source=self.source_name,
                        )
                    )

            return relations
        except Exception as e:
            logger.error(
                f"Unexpected error during schema.org get_relations for '{uri}': {e}"
            )
            raise ReferenceSourceError(
                "Unexpected error during schema.org get_relations"
            ) from e

    async def is_available_async(self) -> bool:
        """
        Check if schema.org vocabulary is available (async version).

        Delegates to sync method via executor to avoid code duplication.

        Returns:
            True (always available)
        """
        return await run_sync_in_executor(self.is_available)

    async def search_async(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for schema.org type definitions matching a term (async version).

        Delegates to sync method via executor to avoid code duplication.

        Args:
            term: Search query
            limit: Maximum number of results to return

        Returns:
            List of ReferenceResult objects matching the term

        Raises:
            ReferenceSourceParseError: On unexpected data structure errors
        """
        return await run_sync_in_executor(self.search, term, limit)

    async def get_relations_async(
        self, uri: str, limit: int = 10
    ) -> list[ReferenceRelation]:
        """
        Get relationships connected to a URI in schema.org (async version).

        Delegates to sync method via executor to avoid code duplication.

        Args:
            uri: URI of the type to find relations for
            limit: Maximum number of relations to return

        Returns:
            List of ReferenceRelation objects

        Raises:
            ReferenceSourceParseError: On unexpected data structure errors
        """
        return await run_sync_in_executor(self.get_relations, uri, limit)

    async def cleanup_async(self) -> None:
        """
        Clean up resources.

        No-op for schema.org since it uses local data only.
        """
        pass
