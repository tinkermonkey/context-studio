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
    1. FindThenTypeOrchestrator as "find_then_type", the type's default
       implementation: what a run executes when it names none. On the
       extraction benchmark it types far more of what it finds than two-pass
       does with the same model (dev typed F1 0.465 against 0.09 with Claude
       Haiku 5.5).
    2. IndividualExtractionOrchestrator, the two-pass implementation, under
       the id "default". The id is a name only: it is not the type's default
       implementation, and runs when a run names it.
    3. OpenIndividualExtractionOrchestrator as "open_v1".
    4. Their configurations (the first of each implementation is its default):
       - "extraction-find-then-type": find-then-type (Anthropic/Claude Haiku 5.5)
       - "extraction-default": two-pass (Anthropic/Claude Haiku 5.5)
       - "extraction-openrouter-default": two-pass (OpenRouter/Gemini 3 Flash)
       - "extraction-open-v1": the open spaCy-based pipeline

    Args:
        impl_registry: PipelineImplementationRegistry instance (optional)
        config_registry: PipelineConfigurationRegistry instance (optional)
    """
    # Register implementations: find-then-type is the type's default; two-pass
    # keeps the id "default", which no longer says it is
    if impl_registry is not None:
        impl_registry.register_impl(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "find_then_type",
            FindThenTypeOrchestrator,
            default=True,
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
