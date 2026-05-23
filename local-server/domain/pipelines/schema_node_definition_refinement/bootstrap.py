"""
Bootstrap module for Schema Node Definition Refinement pipeline registration.

Provides functions to register the default definition refinement implementation
and configurations with the pipeline registries.
"""

from domain.pipelines.entities import PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_node_definition_refinement.configurations.default import (
    get_default_config,
)
from domain.pipelines.schema_node_definition_refinement.orchestrator import (
    DefinitionRefinementOrchestrator,
)


def register_schema_node_definition_refinement(
    impl_registry: PipelineImplementationRegistry | None = None,
    config_registry: PipelineConfigurationRegistry | None = None,
) -> None:
    """
    Register the default definition refinement implementation and configuration.

    Registers:
    1. DefinitionRefinementOrchestrator as the "default" implementation
    2. Default configuration: "definition-refinement-default" using OpenRouter + Gemini 3 Flash

    Args:
        impl_registry: PipelineImplementationRegistry instance (optional)
        config_registry: PipelineConfigurationRegistry instance (optional)
    """
    if impl_registry is not None:
        impl_registry.register_impl(
            PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            "default",
            DefinitionRefinementOrchestrator,
        )

    if config_registry is not None:
        config_registry.register(
            PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            "default",
            "definition-refinement-default",
            get_default_config(),
        )
