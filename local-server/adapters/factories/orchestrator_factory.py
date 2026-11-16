"""
Factory for instantiating pipeline orchestrators with proper dependency injection.

This module provides factory functions that instantiate orchestrators
and pipeline states based on pipeline type and available services.
"""

from hashlib import sha256
from typing import Any, Callable, Type

from adapters.interchange.dr_relationships import (
    DrRelationshipRules,
    dr_general_predicates_for,
    dr_predicate_catalog_for,
)
from domain.pipelines.claim_triage.orchestrator import (
    ClaimTriageOrchestrator,
    ClaimTriageState,
)
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.individual_extraction.find_then_type import (
    FindThenTypeOrchestrator,
)
from domain.pipelines.individual_extraction.open_orchestrator import (
    OpenIndividualExtractionOrchestrator,
)
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionOrchestrator,
    IndividualExtractionState,
)
from domain.pipelines.notes_to_claims.orchestrator import (
    NotesToClaimsOrchestrator,
    NotesToClaimsState,
)
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipelines.orchestration.noop import (
    NoOpPipelineOrchestrator,
    NoOpPipelineState,
)
from domain.pipelines.ports import LLMProvider, PipelineRunStatusWriter
from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal
from domain.pipelines.schema_extraction.open_orchestrator import (
    OpenSchemaExtractionOrchestrator,
)
from domain.pipelines.schema_extraction.orchestrator import (
    SchemaExtractionOrchestrator,
    SchemaExtractionState,
    join_documents,
)
from domain.pipelines.schema_node_connection_refinement.orchestrator import (
    ConnectionRefinementOrchestrator,
    ConnectionRefinementState,
)
from domain.pipelines.schema_node_definition_refinement.orchestrator import (
    DefinitionRefinementOrchestrator,
    DefinitionRefinementState,
)
from domain.pipelines.schema_node_grounding.orchestrator import (
    SchemaGroundingOrchestrator,
    SchemaGroundingState,
)
from domain.pipelines.schema_relationship_reflection.orchestrator import (
    RelationshipReflectionOrchestrator,
    RelationshipReflectionState,
)
from domain.pipelines.selection import PipelineSelection
from domain.pipelines.source_proposals import SourceProposer
from utils.logger import get_logger

_logger = get_logger(__name__)


def _build_noop(llm_provider: LLMProvider, services: dict[str, Any]) -> PipelineOrchestrator:
    return NoOpPipelineOrchestrator(
        llm_provider=llm_provider,
        run_id=services.get("run_id"),
        status_writer=services.get("status_writer"),
    )


def _source_proposer(services: dict[str, Any]) -> SourceProposer | None:
    """Proposes an extraction run on a source; None without the proposal service."""
    proposal_service = services.get("proposal_service")
    ontology_repo = services.get("ontology_repo")
    if proposal_service is None or ontology_repo is None:
        return None
    return SourceProposer(proposal_service, ontology_repo)


def _individual_extraction_builder(
    orchestrator_class: type[IndividualExtractionOrchestrator],
) -> Callable[[LLMProvider, dict[str, Any]], PipelineOrchestrator]:
    """The builder of an individual extraction orchestrator over the extraction service."""

    def build(llm_provider: LLMProvider, services: dict[str, Any]) -> PipelineOrchestrator:
        extraction_service = services.get("extraction_service")
        if not extraction_service:
            raise ValueError(f"extraction_service is required for {orchestrator_class.__name__}")
        return orchestrator_class(
            llm_provider=llm_provider,
            extraction_service=extraction_service,
            run_id=services.get("run_id"),
            status_writer=services.get("status_writer"),
            config=services.get("config"),
            proposer=_source_proposer(services),
            configuration_ref=services.get("configuration_ref"),
        )

    return build


def _build_schema_extraction(
    llm_provider: LLMProvider, services: dict[str, Any]
) -> PipelineOrchestrator:
    return SchemaExtractionOrchestrator(
        llm_provider=llm_provider,
        ontology_repo=services.get("ontology_repo"),
        run_id=services.get("run_id"),
        status_writer=services.get("status_writer"),
        config=services.get("config"),
        proposer=_source_proposer(services),
    )


def _build_open_individual_extraction(
    llm_provider: LLMProvider, services: dict[str, Any]
) -> PipelineOrchestrator:
    nlp_processor = services.get("nlp_processor")
    embedding_service = services.get("embedding_service")
    if not nlp_processor or not embedding_service:
        raise ValueError(
            "nlp_processor and embedding_service are required for "
            "OpenIndividualExtractionOrchestrator"
        )
    return OpenIndividualExtractionOrchestrator(
        llm_provider=llm_provider,
        nlp_processor=nlp_processor,
        embedding_service=embedding_service,
        schema_index=services.get("schema_index"),
        config=services.get("open_individual_config"),
        run_id=services.get("run_id"),
        status_writer=services.get("status_writer"),
    )


def _build_open_schema_extraction(
    llm_provider: LLMProvider, services: dict[str, Any]
) -> PipelineOrchestrator:
    nlp_processor = services.get("nlp_processor")
    embedding_service = services.get("embedding_service")
    clusterer = services.get("clusterer")
    if not nlp_processor or not embedding_service or not clusterer:
        raise ValueError(
            "nlp_processor, embedding_service, and clusterer are required for "
            "OpenSchemaExtractionOrchestrator"
        )
    return OpenSchemaExtractionOrchestrator(
        llm_provider=llm_provider,
        nlp_processor=nlp_processor,
        embedding_service=embedding_service,
        clusterer=clusterer,
        ontology_repo=services.get("ontology_repo"),
        reference_source=services.get("reference_source"),
        config=services.get("open_schema_config"),
        run_id=services.get("run_id"),
        status_writer=services.get("status_writer"),
    )


def _build_schema_grounding(
    llm_provider: LLMProvider, services: dict[str, Any]
) -> PipelineOrchestrator:
    grounding_adapter = services.get("grounding_adapter")
    if not grounding_adapter:
        raise ValueError("grounding_adapter is required for SchemaGroundingOrchestrator")
    scorer = services.get("scorer")
    if not scorer:
        raise ValueError("scorer is required for SchemaGroundingOrchestrator")
    return SchemaGroundingOrchestrator(
        llm_provider=llm_provider,
        grounding_adapter=grounding_adapter,
        scorer=scorer,
        config=services.get("grounding_config", {}),
        run_id=services.get("run_id"),
        status_writer=services.get("status_writer"),
        ontology_repo=services.get("ontology_repo"),
    )


def _build_definition_refinement(
    llm_provider: LLMProvider, services: dict[str, Any]
) -> PipelineOrchestrator:
    ontology_repo = services.get("ontology_repo")
    if not ontology_repo:
        raise ValueError("ontology_repo is required for DefinitionRefinementOrchestrator")
    extraction_repo = services.get("extraction_repo")
    traversal = SchemaNeighborhoodTraversal(
        ontology_repo=ontology_repo,
        extraction_repo=extraction_repo,
    )
    return DefinitionRefinementOrchestrator(
        llm_provider=llm_provider,
        traversal=traversal,
        config=services.get("refinement_config", {}),
        run_id=services.get("run_id"),
        status_writer=services.get("status_writer"),
        ontology_repo=ontology_repo,
        proposal_service=services.get("proposal_service"),
    )


def _build_connection_refinement(
    llm_provider: LLMProvider, services: dict[str, Any]
) -> PipelineOrchestrator:
    ontology_repo = services.get("ontology_repo")
    if not ontology_repo:
        raise ValueError("ontology_repo is required for ConnectionRefinementOrchestrator")
    extraction_repo = services.get("extraction_repo")
    traversal = SchemaNeighborhoodTraversal(
        ontology_repo=ontology_repo,
        extraction_repo=extraction_repo,
    )
    return ConnectionRefinementOrchestrator(
        llm_provider=llm_provider,
        traversal=traversal,
        config=services.get("refinement_config", {}),
        run_id=services.get("run_id"),
        status_writer=services.get("status_writer"),
    )


def _build_relationship_reflection(
    llm_provider: LLMProvider, services: dict[str, Any]
) -> PipelineOrchestrator:
    ontology_repo = services.get("ontology_repo")
    decision_models = services.get("decision_models")
    proposal_service = services.get("proposal_service")
    if not ontology_repo or not decision_models or not proposal_service:
        raise ValueError(
            "ontology_repo, decision_models and proposal_service are required for "
            "RelationshipReflectionOrchestrator"
        )
    # DR's predicate catalog, general predicates and relationship identity
    # apply to the dr_spec taxonomy only; any other taxonomy reflects on its
    # own predicates.
    dr_rules = DrRelationshipRules(ontology_repo)
    return RelationshipReflectionOrchestrator(
        ontology_repo=ontology_repo,
        decision_models=decision_models,
        proposal_service=proposal_service,
        predicate_catalog=lambda taxonomy_id: dr_predicate_catalog_for(ontology_repo, taxonomy_id),
        general_predicates=lambda taxonomy_id: dr_general_predicates_for(
            ontology_repo, taxonomy_id
        ),
        complete_fields=dr_rules.complete_triple_fields,
        config=services.get("refinement_config", {}),
        run_id=services.get("run_id"),
        status_writer=services.get("status_writer"),
    )


def _build_claim_triage(
    llm_provider: LLMProvider, services: dict[str, Any]
) -> PipelineOrchestrator:
    ontology_repo = services.get("ontology_repo")
    decision_models = services.get("decision_models")
    claim_service = services.get("claim_service")
    if not ontology_repo or not decision_models or not claim_service:
        raise ValueError(
            "ontology_repo, decision_models and claim_service are required for "
            "ClaimTriageOrchestrator"
        )
    return ClaimTriageOrchestrator(
        ontology_repo=ontology_repo,
        decision_models=decision_models,
        claim_service=claim_service,
        proposal_service=services.get("proposal_service"),
        # DR's predicate meanings for the dr_spec taxonomy's evidence packs
        predicate_catalog=lambda taxonomy_id: dr_predicate_catalog_for(ontology_repo, taxonomy_id),
        config=services.get("refinement_config", {}),
        run_id=services.get("run_id"),
        status_writer=services.get("status_writer"),
    )


def _build_notes_to_claims(
    llm_provider: LLMProvider, services: dict[str, Any]
) -> PipelineOrchestrator:
    ontology_repo = services.get("ontology_repo")
    claim_service = services.get("claim_service")
    if not ontology_repo or not claim_service:
        raise ValueError(
            "ontology_repo and claim_service are required for NotesToClaimsOrchestrator"
        )
    return NotesToClaimsOrchestrator(
        llm_provider=llm_provider,
        ontology_repo=ontology_repo,
        claim_service=claim_service,
        proposal_service=services.get("proposal_service"),
        config=services.get("refinement_config", {}),
        run_id=services.get("run_id"),
        status_writer=services.get("status_writer"),
    )


_ORCHESTRATOR_BUILDERS: dict[
    Type[PipelineOrchestrator],
    Callable[[LLMProvider, dict[str, Any]], PipelineOrchestrator],
] = {
    NoOpPipelineOrchestrator: _build_noop,
    IndividualExtractionOrchestrator: _individual_extraction_builder(
        IndividualExtractionOrchestrator
    ),
    FindThenTypeOrchestrator: _individual_extraction_builder(FindThenTypeOrchestrator),
    OpenIndividualExtractionOrchestrator: _build_open_individual_extraction,
    SchemaExtractionOrchestrator: _build_schema_extraction,
    OpenSchemaExtractionOrchestrator: _build_open_schema_extraction,
    SchemaGroundingOrchestrator: _build_schema_grounding,
    DefinitionRefinementOrchestrator: _build_definition_refinement,
    ConnectionRefinementOrchestrator: _build_connection_refinement,
    RelationshipReflectionOrchestrator: _build_relationship_reflection,
    ClaimTriageOrchestrator: _build_claim_triage,
    NotesToClaimsOrchestrator: _build_notes_to_claims,
}

_PIPELINE_TYPE_TO_STATE: dict[PipelineType, Type[PipelineState]] = {
    PipelineType.NO_OP: NoOpPipelineState,
    PipelineType.INDIVIDUAL_EXTRACTION: IndividualExtractionState,
    PipelineType.SCHEMA_EXTRACTION: SchemaExtractionState,
    PipelineType.SCHEMA_NODE_GROUNDING: SchemaGroundingState,
    PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT: DefinitionRefinementState,
    PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT: ConnectionRefinementState,
    PipelineType.SCHEMA_RELATIONSHIP_REFLECTION: RelationshipReflectionState,
    PipelineType.CLAIM_TRIAGE: ClaimTriageState,
    PipelineType.NOTES_TO_CLAIMS: NotesToClaimsState,
}


def _grounding_config(config: dict[str, Any]) -> dict[str, Any]:
    """The grounding-specific part of a configuration: top_n, weights and sources."""
    return {
        "top_n": config.get("top_n", 10),
        "sources": config.get("sources", []),
        "weights": config.get(
            "weights",
            {
                "source_score": 0.3,
                "label_match": 0.3,
                "semantic_similarity": 0.4,
            },
        ),
    }


def build_orchestrator_services(
    app_state: Any,
    config: dict[str, Any],
    run_id: str,
    status_writer: PipelineRunStatusWriter,
) -> dict[str, Any]:
    """
    The services dict create_orchestrator draws on, from the app's wired adapters.

    Args:
        app_state: The FastAPI app.state holding the wired adapters (missing ones are None)
        config: The run's pinned configuration
        run_id: The run being executed
        status_writer: Where the orchestrator writes the run's status and progress

    Returns:
        Services dict for create_orchestrator
    """
    return {
        "extraction_service": getattr(app_state, "extraction_service", None),
        "ontology_repo": getattr(app_state, "ontology_repo", None),
        "decision_models": getattr(app_state, "decision_models", None),
        "proposal_service": getattr(app_state, "proposal_service", None),
        "claim_service": getattr(app_state, "claim_service", None),
        "extraction_repo": getattr(app_state, "extraction_repo", None),
        "grounding_adapter": getattr(app_state, "grounding_adapter", None),
        "scorer": getattr(app_state, "grounding_scorer", None),
        "config": config,
        "grounding_config": _grounding_config(config),
        "refinement_config": config,
        # Ports + config for the open extraction implementations (open_v1)
        "nlp_processor": getattr(app_state, "nlp_processor", None),
        "embedding_service": getattr(app_state, "embedding_service", None),
        "clusterer": getattr(app_state, "clusterer", None),
        "schema_index": getattr(app_state, "schema_vector_index", None),
        "reference_source": getattr(app_state, "conceptnet_source", None),
        "open_schema_config": config,
        "open_individual_config": config,
        "run_id": run_id,
        "status_writer": status_writer,
    }


def create_orchestrator(
    orchestrator_class: Type[PipelineOrchestrator],
    llm_provider: LLMProvider,
    services: dict[str, Any] | None = None,
) -> PipelineOrchestrator:
    """
    Instantiate a pipeline orchestrator with proper dependencies.

    Args:
        orchestrator_class: The orchestrator class to instantiate
        llm_provider: LLM provider for completions
        services: Dict of available services (extraction_service, grounding_adapter, etc.)

    Returns:
        Instantiated orchestrator with all dependencies injected

    Raises:
        ValueError: If the orchestrator class is unknown or required dependencies are missing
    """
    builder = _ORCHESTRATOR_BUILDERS.get(orchestrator_class)
    if builder is None:
        raise ValueError(f"Unknown orchestrator class: {orchestrator_class.__name__}")
    return builder(llm_provider, services or {})


def create_pipeline_state(
    run_id: str,
    pipeline_type: PipelineType,
    input_data: dict[str, Any],
    llm_provider: Any,
) -> PipelineState:
    """
    Create a pipeline state for the given pipeline type.

    Args:
        run_id: Pipeline run ID
        pipeline_type: Type of pipeline
        input_data: Input data dict
        llm_provider: LLM provider instance

    Returns:
        PipelineState instance (or appropriate subclass)

    Raises:
        ValueError: If the pipeline type has no registered state class
    """
    state_class = _PIPELINE_TYPE_TO_STATE.get(pipeline_type)
    if state_class is None:
        raise ValueError(f"No state class registered for pipeline type: {pipeline_type.value}")
    return state_class(
        run_id=run_id,
        pipeline_type=pipeline_type,
        input_data=input_data,
        current_status=PipelineRunStatus.PENDING,
        llm_provider=llm_provider,
        result=None,
    )


def create_selected_run(
    selection: PipelineSelection,
    llm_provider: LLMProvider,
    services: dict[str, Any],
    run_id: str,
    input_data: dict[str, Any],
) -> tuple[PipelineOrchestrator, PipelineState]:
    """
    The orchestrator and initial state that execute a run of `selection`.

    Everything that executes a run (the run API, the background worker,
    scripts) builds it here, so the model, temperature and output-token limit
    are the configuration's wherever the run's input names none
    (PipelineSelection.run_input). A run stored to execute later already
    carries them in its input, as it was accepted.

    Args:
        selection: The run's implementation and pinned configuration
        llm_provider: LLM provider for completions
        services: Services dict for create_orchestrator, built with the
            selection's configuration (build_orchestrator_services)
        run_id: Pipeline run ID
        input_data: The run's input as the caller gave it

    Raises:
        ValueError: If the orchestrator class is unknown or required dependencies are missing
    """
    orchestrator = create_orchestrator(
        selection.implementation,
        llm_provider,
        {**services, "configuration_ref": selection.configuration_ref},
    )
    state = create_pipeline_state(
        run_id, selection.pipeline_type, selection.run_input(input_data), llm_provider
    )
    return orchestrator, state


def run_llm_metadata(state: PipelineState, result_state: PipelineState) -> dict[str, Any]:
    """
    What a finished run records about its model calls: what its orchestrator
    reported (tokens, latency, the model where it says so), and otherwise the
    model the run executed with, so every run says which model it used.

    Args:
        state: The state the run was executed with (create_selected_run)
        result_state: The state its orchestrator returned
    """
    metadata = dict(result_state.llm_metadata or {})
    model = state.input_data.get("model")
    if model and not metadata.get("model"):
        metadata["model"] = model
    return metadata


def failed_run_llm_metadata(state: PipelineState, error: BaseException) -> dict[str, Any]:
    """
    What a failed run records about its model calls: what the failure carries
    (the tokens and time its calls cost before it failed), and otherwise the
    model the run executed with, so a failed run says which model it was
    given as a completed one does.

    Args:
        state: The state the run was executed with (create_selected_run)
        error: What its orchestrator raised
    """
    metadata = dict(getattr(error, "llm_metadata", None) or {})
    model = state.input_data.get("model")
    if model and not metadata.get("model"):
        metadata["model"] = model
    return metadata


def _source_summary(input_data: dict[str, Any]) -> dict[str, Any]:
    """
    What an extraction run records in its input_summary about where it reads
    from: the dataset it extracts into and, for a run on a source, the source
    and the extract call that started it (so the source's latest extraction
    is found while its runs execute). A run told to read a source's
    boilerplate too records skip_boilerplate false.
    """
    summary: dict[str, Any] = {
        key: str(input_data[key])
        for key in ("dataset_id", "source_id", "extraction_id")
        if input_data.get(key)
    }
    if input_data.get("skip_boilerplate") is False:
        summary["skip_boilerplate"] = False
    return summary


def build_run_specific_data(
    pipeline_type: PipelineType,
    input_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Build the type-specific fields dict to pass to the pipeline run repository.

    Encapsulates any input-derived data transformations (e.g. hashing) so that
    route handlers remain thin adapters with no domain-level computation.

    Args:
        pipeline_type: The pipeline type being run
        input_data: The raw input_data from the request

    Returns:
        Dict of type-specific fields (may be empty for types with no extra fields)
    """
    if pipeline_type == PipelineType.INDIVIDUAL_EXTRACTION:
        text = input_data.get("text", "")
        specific: dict[str, Any] = {
            "source_text_hash": sha256(text.encode()).hexdigest(),
            "source_text": text,
        }
        source_document_uri = input_data.get("source_document_uri")
        if source_document_uri:
            specific["source_document_uri"] = source_document_uri

        # Store input_summary with taxonomy_id for apply operations
        # ontology_id is the field name in the request, we store it as taxonomy_id
        input_summary: dict[str, Any] = _source_summary(input_data)
        ontology_id = input_data.get("ontology_id")
        if ontology_id:
            input_summary["taxonomy_id"] = str(ontology_id)

        ontology_name = input_data.get("ontology_name")
        if ontology_name:
            input_summary["taxonomy_name"] = str(ontology_name)

        example_id = input_data.get("example_id")
        if example_id:
            input_summary["example_id"] = str(example_id)

        if input_summary:
            specific["input_summary"] = input_summary

        return specific
    elif pipeline_type == PipelineType.SCHEMA_EXTRACTION:
        schema_input_summary: dict[str, Any] = _source_summary(input_data)

        # Store the taxonomy for apply; the scheme new classes go to is chosen at apply
        scope = input_data.get("scope")
        if scope:
            schema_input_summary["taxonomy_id"] = str(scope)

        scope_name = input_data.get("scope_name")
        if scope_name:
            schema_input_summary["taxonomy_name"] = str(scope_name)

        example_id = input_data.get("example_id")
        if example_id:
            schema_input_summary["example_id"] = str(example_id)

        schema_specific: dict[str, Any] = {}
        documents = input_data.get("documents")
        if documents:
            schema_specific["source_text"] = join_documents(documents)
        if schema_input_summary:
            schema_specific["input_summary"] = schema_input_summary
        return schema_specific

    return {}
