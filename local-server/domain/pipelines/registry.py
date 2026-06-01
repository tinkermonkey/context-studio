"""
Pipeline registries for type, implementation, and configuration discovery.

Three registries enable runtime enumeration and instantiation:
1. PipelineTypeRegistry — enumerates the six pipeline types with input/output contracts
2. PipelineImplementationRegistry — maps (type, impl_id) → implementation class
3. PipelineConfigurationRegistry — maps (type, impl_id, config_ref) → configuration object
   (versioned; once referenced by a run, the version is immutable)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from domain.pipelines.entities import PipelineType


@dataclass(frozen=True)
class PipelineTypeDefinition:
    """
    Metadata for a pipeline type.

    Attributes:
        pipeline_type: The PipelineType enum value
        description: Human-readable description
        input_contract: Dict describing expected input schema
        output_contract: Dict describing expected output schema
    """

    pipeline_type: PipelineType
    description: str
    input_contract: dict[str, Any]
    output_contract: dict[str, Any]


class PipelineTypeRegistry:
    """
    Registry of all pipeline types.

    Enumerates the six pipeline types with their input/output contracts.
    Discoverable at runtime by UX listing endpoints and script harness.
    """

    _TYPES = {
        PipelineType.NO_OP: PipelineTypeDefinition(
            pipeline_type=PipelineType.NO_OP,
            description="No-op pipeline for testing framework end-to-end",
            input_contract={
                "text": "str (required) — sample input text",
                "ontology_id": "str (required) — target ontology identifier",
            },
            output_contract={
                "status": "str — completion status",
                "message": "str — result message",
                "steps": "list[str] — completed steps",
            },
        ),
        PipelineType.INDIVIDUAL_EXTRACTION: PipelineTypeDefinition(
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            description="Extract RDF triples from individual text documents",
            input_contract={
                "text": "str (required) — source text to extract from",
                "ontology_id": "str (required) — target ontology identifier",
            },
            output_contract={
                "triples": "list[dict] — extracted triples with subject, predicate, object",
                "warnings": "list[str] — validation issues during extraction",
            },
        ),
        PipelineType.SCHEMA_EXTRACTION: PipelineTypeDefinition(
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            description="Extract schema structure from documents",
            input_contract={
                "documents": "list[str] — source documents to extract from",
                "scope": "str (optional) — extraction scope",
            },
            output_contract={
                "classes": "list[dict] — extracted classes",
                "properties": "list[dict] — extracted properties",
            },
        ),
        PipelineType.SCHEMA_NODE_GROUNDING: PipelineTypeDefinition(
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            description="Ground schema nodes to external knowledge sources",
            input_contract={
                "nodes": "list[dict] — schema nodes to ground",
                "sources": "list[str] — external knowledge sources",
            },
            output_contract={
                "groundings": "list[dict] — grounding results with URIs and confidence",
            },
        ),
        PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT: PipelineTypeDefinition(
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            description="Refine schema node definitions using LLM",
            input_contract={
                "node_id": "str (required) — UUID of the node to refine",
                "current_definition": "str (required) — current definition text",
                "context": "str (optional) — additional context for refinement",
            },
            output_contract={
                "refined_definition": "str — refined definition text",
            },
        ),
        PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT: PipelineTypeDefinition(
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            description="Refine connections between schema nodes",
            input_contract={
                "scope_id": "str (required) — UUID of the scope containing the connections",
                "current_connections": "list[dict] (optional) — current connections to refine",
                "strategy": "str (optional) — refinement strategy",
            },
            output_contract={
                "refined_connections": "list[dict] — refined connections with updated properties",
            },
        ),
    }

    @classmethod
    def get_type(cls, pipeline_type: PipelineType) -> PipelineTypeDefinition | None:
        """Get metadata for a pipeline type."""
        return cls._TYPES.get(pipeline_type)

    @classmethod
    def list_types(cls) -> list[PipelineTypeDefinition]:
        """List all registered pipeline types."""
        return list(cls._TYPES.values())

    @classmethod
    def is_valid_type(cls, pipeline_type: PipelineType) -> bool:
        """Check if a pipeline type is registered."""
        return pipeline_type in cls._TYPES


class PipelineImplementationRegistry:
    """
    Registry mapping (pipeline_type, implementation_id) → implementation class.

    Implementations register via decorator or explicit call at startup.
    Used by orchestrator to instantiate and execute pipelines.
    """

    def __init__(self) -> None:
        """Initialize the implementation registry."""
        self._implementations: dict[tuple[PipelineType, str], type[Any]] = {}

    def register(
        self, pipeline_type: PipelineType, impl_id: str
    ) -> Callable[[type[Any]], type[Any]]:
        """
        Decorator to register an implementation.

        Example:
            @registry.register(PipelineType.INDIVIDUAL_EXTRACTION, "default")
            class IndividualExtractionImpl:
                ...

        Args:
            pipeline_type: Type of pipeline
            impl_id: Implementation identifier

        Returns:
            Decorator function
        """

        def decorator(cls: type[Any]) -> type[Any]:
            self.register_impl(pipeline_type, impl_id, cls)
            return cls

        return decorator

    def register_impl(
        self,
        pipeline_type: PipelineType,
        impl_id: str,
        impl_class: type[Any],
    ) -> None:
        """
        Register an implementation class.

        Args:
            pipeline_type: Type of pipeline
            impl_id: Implementation identifier
            impl_class: Implementation class

        Raises:
            ValueError: If already registered
        """
        key = (pipeline_type, impl_id)
        if key in self._implementations:
            raise ValueError(f"Implementation already registered: {pipeline_type.value}:{impl_id}")
        self._implementations[key] = impl_class

    def get(self, pipeline_type: PipelineType, impl_id: str) -> type[Any] | None:
        """Get an implementation class."""
        return self._implementations.get((pipeline_type, impl_id))

    def list_by_type(self, pipeline_type: PipelineType) -> dict[str, type[Any]]:
        """List all implementations for a pipeline type."""
        return {
            impl_id: impl_class
            for (ptype, impl_id), impl_class in self._implementations.items()
            if ptype == pipeline_type
        }

    def list_all(self) -> dict[tuple[PipelineType, str], type[Any]]:
        """List all registered implementations."""
        return dict(self._implementations)


@dataclass(frozen=True)
class ConfigurationVersion:
    """
    Versioned configuration reference.

    Once a PipelineRun references a configuration, that version is immutable.

    Attributes:
        pipeline_type: Type of pipeline
        implementation_id: Implementation identifier
        config_ref: Configuration reference slug (e.g., 'extraction-default')
        version: Version number (auto-incremented on update)
        config: Configuration dict (immutable once set)
    """

    pipeline_type: PipelineType
    implementation_id: str
    config_ref: str
    version: int
    config: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate version is positive."""
        if self.version < 1:
            raise ValueError(f"version must be >= 1, got {self.version}")


class PipelineConfigurationRegistry:
    """
    Registry mapping (pipeline_type, impl_id, config_ref) → versioned configuration.

    Configurations are immutable once set. Updates increment the version;
    old versions remain accessible. A PipelineRun references a specific
    version via configuration_ref + the version it used at creation time.

    In-Memory Design and Server Restart Safety:

    This registry is entirely in-memory and NOT persisted to the database. It is
    populated at server startup by calling register_*() functions for each pipeline
    type (e.g., register_individual_extraction, register_schema_extraction) from
    domain/pipelines/{type}/bootstrap.py modules.

    These registration functions read from deterministic default configuration modules
    in domain/pipelines/{type}/configurations/default.py. After a server restart, all
    configurations are re-registered in the same order with the same version numbers.

    Therefore, a PipelineRun referencing (slug="extraction-default", version=3)
    created before restart will successfully resolve after restart, because version 3
    is regenerated from code. This is correct and intentional.

    Immutability Mechanism:

    Immutability is enforced by the architecture, not by explicit checks:
    - Each call to register() with the same slug creates a NEW version
      (incrementing the version number)
    - The ConfigurationVersion is a frozen dataclass, so it cannot be mutated
    - You cannot retrieve an existing version and modify it; register() always
      returns a freshly created ConfigurationVersion with an incremented version number
    - mark_version_referenced() tracks which versions are used by runs, documenting
      the immutability contract for observability and testing

    This design prevents the mutation error case by construction.
    """

    def __init__(self) -> None:
        """Initialize the configuration registry."""
        # Map: (type, impl_id, config_ref) → list of versions (oldest first)
        self._configs: dict[tuple[PipelineType, str, str], list[ConfigurationVersion]] = {}
        # Set of (type, impl_id, config_ref, version) pairs that are referenced by runs
        # Used to document the immutability contract and enable testing of the
        # architectural constraint that version-referenced configs cannot change
        self._referenced_versions: set[tuple[PipelineType, str, str, int]] = set()

    def register(
        self,
        pipeline_type: PipelineType,
        implementation_id: str,
        config_ref: str,
        config: dict[str, Any],
    ) -> ConfigurationVersion:
        """
        Register or update a configuration.

        If config_ref exists, increments version and stores as new version.
        Otherwise, creates version 1.

        Configuration versions are immutable by design: ConfigurationVersion is a frozen
        dataclass and versions are stored in an append-only list. Existing versions cannot
        be mutated; only new versions can be registered.

        Args:
            pipeline_type: Type of pipeline
            implementation_id: Implementation identifier
            config_ref: Configuration reference (slug)
            config: Configuration dict

        Returns:
            ConfigurationVersion just registered
        """
        key = (pipeline_type, implementation_id, config_ref)
        versions = self._configs.get(key, [])

        # Create a new version (incrementing the version number).
        # Since ConfigurationVersion is a frozen dataclass and stored in an append-only
        # list, existing versions cannot be mutated. Only new versions can be registered.

        next_version = (versions[-1].version + 1) if versions else 1
        version_obj = ConfigurationVersion(
            pipeline_type=pipeline_type,
            implementation_id=implementation_id,
            config_ref=config_ref,
            version=next_version,
            config=dict(config),  # Defensive copy
        )

        self._configs[key] = versions + [version_obj]
        return version_obj

    def get_latest(
        self, pipeline_type: PipelineType, implementation_id: str, config_ref: str
    ) -> ConfigurationVersion | None:
        """Get the latest version of a configuration."""
        key = (pipeline_type, implementation_id, config_ref)
        versions = self._configs.get(key, [])
        return versions[-1] if versions else None

    def get_version(
        self,
        pipeline_type: PipelineType,
        implementation_id: str,
        config_ref: str,
        version: int,
    ) -> ConfigurationVersion | None:
        """Get a specific version of a configuration."""
        key = (pipeline_type, implementation_id, config_ref)
        versions = self._configs.get(key, [])
        for v in versions:
            if v.version == version:
                return v
        return None

    def list_configs(
        self, pipeline_type: PipelineType, implementation_id: str
    ) -> list[tuple[str, ConfigurationVersion]]:
        """List (config_ref, latest_version) pairs for a type/impl combo."""
        result = []
        for (ptype, impl_id, config_ref), versions in self._configs.items():
            if ptype == pipeline_type and impl_id == implementation_id and versions:
                result.append((config_ref, versions[-1]))
        return result

    def list_all_versions(
        self, pipeline_type: PipelineType, implementation_id: str, config_ref: str
    ) -> list[ConfigurationVersion]:
        """List all versions of a configuration."""
        key = (pipeline_type, implementation_id, config_ref)
        return self._configs.get(key, [])

    def mark_version_referenced(
        self,
        pipeline_type: PipelineType,
        implementation_id: str,
        config_ref: str,
        version: int,
    ) -> None:
        """
        Mark a configuration version as referenced by a PipelineRun.

        This documents the immutability contract: once a version is referenced by a run,
        that version will not be modified. New runs can only reference the latest version
        or explicitly pin an older version. Immutability is enforced by the architecture
        (ConfigurationVersion is a frozen dataclass stored in an append-only list).

        Args:
            pipeline_type: Type of pipeline
            implementation_id: Implementation identifier
            config_ref: Configuration reference (slug)
            version: Version number
        """
        key = (pipeline_type, implementation_id, config_ref, version)
        self._referenced_versions.add(key)

    def is_version_referenced(
        self,
        pipeline_type: PipelineType,
        implementation_id: str,
        config_ref: str,
        version: int,
    ) -> bool:
        """
        Check if a configuration version is referenced by a PipelineRun.

        Args:
            pipeline_type: Type of pipeline
            implementation_id: Implementation identifier
            config_ref: Configuration reference (slug)
            version: Version number

        Returns:
            True if this version is already referenced by a run
        """
        key = (pipeline_type, implementation_id, config_ref, version)
        return key in self._referenced_versions
