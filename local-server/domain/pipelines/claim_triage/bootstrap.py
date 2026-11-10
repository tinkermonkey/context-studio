"""Registration of the claim triage pipeline."""

from domain.pipelines.claim_triage.configurations.default import get_default_config
from domain.pipelines.claim_triage.orchestrator import ClaimTriageOrchestrator
from domain.pipelines.entities import PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)


def register_claim_triage(
    impl_registry: PipelineImplementationRegistry | None = None,
    config_registry: PipelineConfigurationRegistry | None = None,
) -> None:
    """
    Register the default implementation and its configuration, both "default"
    (what run_refinement uses when no implementation or configuration is named).
    """
    if impl_registry is not None:
        impl_registry.register_impl(PipelineType.CLAIM_TRIAGE, "default", ClaimTriageOrchestrator)
    if config_registry is not None:
        config_registry.register(
            PipelineType.CLAIM_TRIAGE, "default", "default", get_default_config()
        )
