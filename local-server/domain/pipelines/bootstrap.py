"""
Registration of every pipeline: each type's implementations and their
configurations, with the defaults a run gets when it names none.

The app and the scripts that run pipelines register through here, so they
offer the same implementations, configurations and defaults.
"""

from domain.pipelines.claim_triage.bootstrap import register_claim_triage
from domain.pipelines.individual_extraction.bootstrap import register_individual_extraction
from domain.pipelines.notes_to_claims.bootstrap import register_notes_to_claims
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_extraction.bootstrap import register_schema_extraction
from domain.pipelines.schema_node_connection_refinement.bootstrap import (
    register_schema_node_connection_refinement,
)
from domain.pipelines.schema_node_definition_refinement.bootstrap import (
    register_schema_node_definition_refinement,
)
from domain.pipelines.schema_node_grounding.bootstrap import register_schema_node_grounding
from domain.pipelines.schema_relationship_reflection.bootstrap import (
    register_schema_relationship_reflection,
)
from domain.pipelines.selection import PipelineResolver


def register_pipelines(
    impl_registry: PipelineImplementationRegistry,
    config_registry: PipelineConfigurationRegistry,
) -> PipelineResolver:
    """
    Register every pipeline's implementations and system configurations.

    Returns:
        The resolver over the two registries

    Raises:
        ValueError: If a registered type lacks a default implementation, or an
            implementation a default configuration
    """
    for register in (
        register_individual_extraction,
        register_schema_extraction,
        register_schema_node_grounding,
        register_schema_node_definition_refinement,
        register_schema_node_connection_refinement,
        register_schema_relationship_reflection,
        register_claim_triage,
        register_notes_to_claims,
    ):
        register(impl_registry=impl_registry, config_registry=config_registry)
    resolver = PipelineResolver(impl_registry, config_registry)
    resolver.check_defaults()
    return resolver
