"""
Bootstrap module for Individual Extraction pipeline registration.

Provides functions to register the default individual extraction implementation
and configurations with the pipeline registries.
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
    Register the default individual extraction implementation and configurations.

    Registers:
    1. IndividualExtractionOrchestrator as the "default" implementation,
       OpenIndividualExtractionOrchestrator as "open_v1" and
       FindThenTypeOrchestrator as "find_then_type"
    2. Their configurations:
       - "extraction-default": Wave A compatible (Anthropic/Claude Opus)
       - "extraction-openrouter-default": OpenRouter/Gemini 3 Flash
       - "extraction-open-v1": the open spaCy-based pipeline
       - "extraction-find-then-type": find-then-type (Anthropic/Claude Haiku 5.5)

    Args:
        impl_registry: PipelineImplementationRegistry instance (optional)
        config_registry: PipelineConfigurationRegistry instance (optional)
    """
    # Register implementations (LLM-only "default" + open spaCy "open_v1")
    if impl_registry is not None:
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
        impl_registry.register_impl(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "find_then_type",
            FindThenTypeOrchestrator,
        )

    # Register configurations
    if config_registry is not None:
        # Wave A default config (Anthropic/Claude Opus)
        config_registry.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "extraction-default",
            get_default_config(),
        )

        # OpenRouter default config (Gemini 3 Flash)
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
        )

        # Find-then-type config (Claude Haiku 5.5)
        config_registry.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "find_then_type",
            "extraction-find-then-type",
            get_find_then_type_config(),
        )
