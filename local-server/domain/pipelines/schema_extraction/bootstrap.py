"""
Bootstrap module for Schema Extraction pipeline registration.

Registers the schema extraction implementations (LLM-only "default" and open
spaCy-based "open_v1") and their configurations with the pipeline registries.
"""

from domain.pipelines.entities import PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_extraction.configurations.default import get_default_config
from domain.pipelines.schema_extraction.configurations.open_v1 import get_open_v1_config
from domain.pipelines.schema_extraction.open_orchestrator import (
    OpenSchemaExtractionOrchestrator,
)
from domain.pipelines.schema_extraction.orchestrator import SchemaExtractionOrchestrator


def register_schema_extraction(
    impl_registry: PipelineImplementationRegistry | None = None,
    config_registry: PipelineConfigurationRegistry | None = None,
) -> None:
    """
    Register the schema extraction implementations and configurations.

    Registers the LLM-only "default" and the open spaCy-based "open_v1"
    implementations side by side so the quality harness can A/B them.

    Args:
        impl_registry: PipelineImplementationRegistry instance (optional)
        config_registry: PipelineConfigurationRegistry instance (optional)
    """
    # Register implementations
    if impl_registry is not None:
        impl_registry.register_impl(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            SchemaExtractionOrchestrator,
        )
        impl_registry.register_impl(
            PipelineType.SCHEMA_EXTRACTION,
            "open_v1",
            OpenSchemaExtractionOrchestrator,
        )

    # Register configurations
    if config_registry is not None:
        config_registry.register(
            PipelineType.SCHEMA_EXTRACTION,
            "default",
            "schema-extraction-default",
            get_default_config(),
        )
        config_registry.register(
            PipelineType.SCHEMA_EXTRACTION,
            "open_v1",
            "schema-extraction-open-v1",
            get_open_v1_config(),
        )
