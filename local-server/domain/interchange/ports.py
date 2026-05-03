"""
Ports for the Data Interchange bounded context.

Defines the contracts for serializing, deserializing, and persisting import data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from .entities import ImportRun, ImportRunStatus
from .value_objects import SerializationScope, ImportPlan


class OntologySerializer(ABC):
    """
    Port for exporting ontology data in various formats.

    Implementations serialize the ontology to bytes according to a scope.
    """

    @abstractmethod
    def serialize(self, scope: SerializationScope) -> bytes:
        """
        Serialize the ontology according to the given scope.

        Args:
            scope: Describes what to serialize (whole_graph, taxonomy, scheme, entity_set)

        Returns:
            Serialized ontology as bytes

        Raises:
            ValueError: If the scope is invalid
            RuntimeError: If serialization fails
        """
        ...


class OntologyDeserializer(ABC):
    """
    Port for importing ontology data from various formats.

    Implementations deserialize bytes into domain entities and produce an ImportPlan.
    """

    @abstractmethod
    def deserialize(self, source: bytes | str, dry_run: bool = True) -> ImportPlan:
        """
        Deserialize ontology data and produce an import plan.

        Args:
            source: Serialized ontology as bytes or string
            dry_run: If True, returns ImportPlan without persisting.
                     If False, commits changes and returns ImportPlan with ImportRun.

        Returns:
            ImportPlan describing what the import would/did do

        Raises:
            ValueError: If the source is malformed
            RuntimeError: If deserialization fails
        """
        ...


class ImportRunRepository(Protocol):
    """
    Port for persisting and querying import runs.

    Implementations handle storage and retrieval of ImportRun entities
    with support for filtering by status and pagination.
    """

    def create(self, import_run: ImportRun) -> ImportRun:
        """
        Persist a new import run.

        Args:
            import_run: The ImportRun entity to persist

        Returns:
            The persisted ImportRun

        Raises:
            RuntimeError: If persistence fails
        """
        ...

    def get(self, import_run_id: str) -> ImportRun | None:
        """
        Retrieve an import run by ID.

        Args:
            import_run_id: The ID of the import run

        Returns:
            The ImportRun if found, None otherwise
        """
        ...

    def list_all(self, limit: int = 100, offset: int = 0) -> list[ImportRun]:
        """
        Retrieve all import runs with pagination.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of ImportRun entities
        """
        ...

    def list_by_status(
        self, status: ImportRunStatus, limit: int = 100, offset: int = 0
    ) -> list[ImportRun]:
        """
        Retrieve import runs filtered by status.

        Args:
            status: The ImportRunStatus to filter by
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of ImportRun entities matching the status
        """
        ...

    def update(self, import_run: ImportRun) -> ImportRun:
        """
        Update an existing import run.

        Args:
            import_run: The ImportRun entity with updated state

        Returns:
            The updated ImportRun

        Raises:
            RuntimeError: If the run does not exist or update fails
        """
        ...

    def get_change_events_for_run(self, import_run_id: str) -> list[dict]:
        """
        Retrieve change events associated with an import run.

        Args:
            import_run_id: The ID of the import run

        Returns:
            List of change event dicts for the run
        """
        ...
