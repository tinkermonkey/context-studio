"""Registration of the schema relationship reflection pipeline."""

from domain.pipelines.entities import PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_relationship_reflection.configurations.default import (
    get_default_config,
)
from domain.pipelines.schema_relationship_reflection.orchestrator import (
    RelationshipReflectionOrchestrator,
)


def register_schema_relationship_reflection(
    impl_registry: PipelineImplementationRegistry | None = None,
    config_registry: PipelineConfigurationRegistry | None = None,
) -> None:
    """
    Register the default implementation and its configuration, both "default"
    (what run_refinement uses when no implementation or configuration is named).
    """
    if impl_registry is not None:
        impl_registry.register_impl(
            PipelineType.SCHEMA_RELATIONSHIP_REFLECTION,
            "default",
            RelationshipReflectionOrchestrator,
            default=True,
        )
    if config_registry is not None:
        config_registry.register(
            PipelineType.SCHEMA_RELATIONSHIP_REFLECTION,
            "default",
            "default",
            get_default_config(),
            default=True,
        )
