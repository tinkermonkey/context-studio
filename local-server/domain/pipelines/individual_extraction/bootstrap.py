"""
Bootstrap module for Individual Extraction pipeline registration.

Provides the function that registers the individual extraction implementations
and their configurations with the pipeline registries.
"""

from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction.configurations.default import (
    get_default_config,
    get_find_then_type_config,
    get_openrouter_config,
    get_single_call_config,
)
from domain.pipelines.individual_extraction.configurations.open_v1 import (
    get_open_v1_config,
)
from domain.pipelines.individual_extraction.find_then_type import (
    FindThenTypeOrchestrator,
)
from domain.pipelines.individual_extraction.open_orchestrator import (
    OpenIndividualExtractionOrchestrator,
)
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionOrchestrator,
)
from domain.pipelines.individual_extraction.single_call import (
    SingleCallOrchestrator,
)
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)


def register_individual_extraction(
    impl_registry: PipelineImplementationRegistry | None = None,
    config_registry: PipelineConfigurationRegistry | None = None,
) -> None:
    """
    Register the individual extraction implementations and their configurations.

    Registers:
    1. SingleCallOrchestrator as "single_call", the type's default
       implementation: what a run executes when it names none (the user's
       decision of 2026-11-17, on the head-to-head's evidence: one Claude Opus
       5.5 call found and typed individuals at typed F1 0.62 dev / 0.66
       holdout against find_then_type's 0.45 / 0.44, on gold that is
       model-made). Its relationships are find-then-type's relate step.
    2. FindThenTypeOrchestrator as "find_then_type", selectable.
    3. IndividualExtractionOrchestrator, the two-pass implementation, under
       the id "default". The id is a name only: it is not the type's default
       implementation, and runs when a run names it.
    4. OpenIndividualExtractionOrchestrator as "open_v1".
    5. Their configurations (the first of each implementation is its default):
       - "extraction-single-call": single-call (Anthropic/Claude Opus 5.5)
       - "extraction-find-then-type": find-then-type (Anthropic/Claude Haiku 5.5)
       - "extraction-default": two-pass (Anthropic/Claude Haiku 5.5)
       - "extraction-openrouter-default": two-pass (OpenRouter/Gemini 3 Flash)
       - "extraction-open-v1": the open spaCy-based pipeline

    Args:
        impl_registry: PipelineImplementationRegistry instance (optional)
        config_registry: PipelineConfigurationRegistry instance (optional)
    """
    # Register implementations: single-call is the type's default; two-pass
    # keeps the id "default", which does not say it is
    if impl_registry is not None:
        impl_registry.register_impl(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "single_call",
            SingleCallOrchestrator,
            default=True,
        )
        impl_registry.register_impl(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "find_then_type",
            FindThenTypeOrchestrator,
        )
        impl_registry.register_impl(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            IndividualExtractionOrchestrator,
        )
        impl_registry.register_impl(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "open_v1",
            OpenIndividualExtractionOrchestrator,
        )

    # Register configurations
    if config_registry is not None:
        # Two-pass's default config (Anthropic/Claude Haiku 5.5)
        config_registry.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "extraction-default",
            get_default_config(),
            default=True,
        )

        # Two-pass with OpenRouter (Gemini 3 Flash)
        config_registry.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "extraction-openrouter-default",
            get_openrouter_config(),
        )

        # Open spaCy-based config
        config_registry.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "open_v1",
            "extraction-open-v1",
            get_open_v1_config(),
            default=True,
        )

        # Find-then-type config (Claude Haiku 5.5)
        config_registry.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "find_then_type",
            "extraction-find-then-type",
            get_find_then_type_config(),
            default=True,
        )

        # Single-call config (Claude Opus 5.5)
        config_registry.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "single_call",
            "extraction-single-call",
            get_single_call_config(),
            default=True,
        )
