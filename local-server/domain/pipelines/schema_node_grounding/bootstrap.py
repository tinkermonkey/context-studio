"""
Bootstrap module for Schema Node Grounding pipeline registration.

Provides functions to register the default schema node grounding implementation
and configurations with the pipeline registries.
"""

from domain.pipelines.entities import PipelineType
from domain.pipelines.schema_node_grounding.configurations.default import get_default_config
from domain.pipelines.schema_node_grounding.orchestrator import SchemaGroundingOrchestrator
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)


def register_schema_node_grounding(
    impl_registry: PipelineImplementationRegistry | None = None,
    config_registry: PipelineConfigurationRegistry | None = None,
    orchestrator: SchemaGroundingOrchestrator | None = None,
) -> None:
    """
    Register the default schema node grounding implementation and configurations.

    Registers:
    1. SchemaGroundingOrchestrator as the "default" implementation
    2. Default configuration: "grounding-default" using OpenRouter + Gemini 3 Flash

    Args:
        impl_registry: PipelineImplementationRegistry instance (optional)
        config_registry: PipelineConfigurationRegistry instance (optional)
        orchestrator: Pre-built SchemaGroundingOrchestrator instance (for testing)
    """
    if impl_registry is not None:
        if orchestrator is not None:
            impl_registry.register_impl(
                PipelineType.SCHEMA_NODE_GROUNDING,
                "default",
                orchestrator.__class__,
            )
        else:
            impl_registry.register_impl(
                PipelineType.SCHEMA_NODE_GROUNDING,
                "default",
                SchemaGroundingOrchestrator,
            )

    if config_registry is not None:
        config_registry.register(
            PipelineType.SCHEMA_NODE_GROUNDING,
            "default",
            "grounding-default",
            get_default_config(),
        )
