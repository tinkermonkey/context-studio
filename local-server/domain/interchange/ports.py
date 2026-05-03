"""
Ports for the Data Interchange bounded context.

Defines the contracts for serializing and deserializing ontology data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .value_objects import SerializationScope
from .entities import ImportRun
from .value_objects import ImportPlan


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
    def deserialize(
        self, source: bytes, dry_run: bool = True
    ) -> ImportPlan:
        """
        Deserialize ontology data and produce an import plan.

        Args:
            source: Serialized ontology as bytes
            dry_run: If True, returns ImportPlan without persisting.
                     If False, commits changes and returns ImportPlan with ImportRun.

        Returns:
            ImportPlan describing what the import would/did do

        Raises:
            ValueError: If the source is malformed
            RuntimeError: If deserialization fails
        """
        ...
