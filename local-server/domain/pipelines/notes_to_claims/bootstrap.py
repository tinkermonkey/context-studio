"""Registration of the notes-to-claims pipeline."""

from domain.pipelines.entities import PipelineType
from domain.pipelines.notes_to_claims.configurations.default import get_default_config
from domain.pipelines.notes_to_claims.orchestrator import NotesToClaimsOrchestrator
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)


def register_notes_to_claims(
    impl_registry: PipelineImplementationRegistry | None = None,
    config_registry: PipelineConfigurationRegistry | None = None,
) -> None:
    """
    Register the default implementation and its configuration, both "default"
    (what run_refinement uses when no implementation or configuration is named).
    """
    if impl_registry is not None:
        impl_registry.register_impl(
            PipelineType.NOTES_TO_CLAIMS, "default", NotesToClaimsOrchestrator, default=True
        )
    if config_registry is not None:
        config_registry.register(
            PipelineType.NOTES_TO_CLAIMS, "default", "default", get_default_config(), default=True
        )
