"""
Bootstrap module for Schema Extraction pipeline registration.

Provides a function to register the default schema extraction implementation
and configuration with the pipeline registries.
"""

from domain.pipelines.entities import PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_extraction.configurations.default import get_default_config
from domain.pipelines.schema_extraction.orchestrator import SchemaExtractionOrchestrator


def register_schema_extraction(
    impl_registry: PipelineImplementationRegistry | None = None,
    config_registry: PipelineConfigurationRegistry | None = None,
) -> None:
    """
    Register the default schema extraction implementation and configuration.

    Args:
        impl_registry: PipelineImplementationRegistry instance (optional)
        config_registry: PipelineConfigurationRegistry instance (optional)
    """
    # Register the default implementation
    if impl_registry is not None:
        impl_registry.register_impl(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            SchemaExtractionOrchestrator,
        )

    # Register the default configuration
    if config_registry is not None:
        config_registry.register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "schema-extraction-default",
            get_default_config(),
        )
