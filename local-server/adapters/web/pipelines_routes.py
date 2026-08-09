"""
FastAPI routes for the Pipeline Orchestration bounded context.

This module implements HTTP endpoints for generic pipeline execution:
- GET /api/pipelines/types → List pipeline types
- GET /api/pipelines/types/{type}/implementations → List implementations
- GET /api/pipelines/types/{type}/implementations/{id}/configurations → Configs
- POST /api/pipelines/{type}/run → Invoke a pipeline
- GET /api/pipelines/runs/{run_id} → Fetch a PipelineRun by ID
- GET /api/pipelines/runs/{run_id}/candidates → Get pipeline run candidates
- GET /api/pipelines/runs/{run_id}/change-events → Get change events produced by a run
- GET /api/pipelines/runs → List PipelineRuns with filters
- POST /api/pipelines/runs/{run_id}/apply → Materialize run output into ontology

Each endpoint is a thin adapter that:
1. Receives HTTP request + parsed Pydantic schema
2. Calls domain service with domain entities
3. Catches domain exceptions and maps to HTTP status codes
4. Returns response schema serialized as JSON

No business logic lives here—all validation and constraints are in the domain service.
Error handling translates domain exceptions to appropriate HTTP responses.
"""  # noqa: E501

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi import status as http_status
from sqlalchemy.exc import IntegrityError, OperationalError

from adapters.factories.orchestrator_factory import (
    build_run_specific_data,
    create_orchestrator,
    create_pipeline_state,
)
from adapters.persistence.sqlite.pipeline_config_repo import PipelineConfigurationRepository
from adapters.web.dependencies import get_versioning_service
from adapters.web.schemas.ontology import ListResponse
from adapters.web.schemas.pipelines import (
    ApplyRunResponse,
    BatchResponse,
    CancelBatchResponse,
    CandidateResponse,
    EnqueueBatchRunsRequest,
    EnqueueBatchRunsResponse,
    ImplementationResponse,
    PipelineConfigurationCreateRequest,
    PipelineConfigurationParameters,
    PipelineConfigurationResponse,
    PipelineConfigurationUpdateRequest,
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineTypeResponse,
    ResumeBatchResponse,
    RevertRunResponse,
)
from adapters.web.schemas.versioning import VersioningChangeEventResponse
from domain.interchange.services import set_batch_run_context
from domain.pipelines.entities import (
    PipelineRun,
    PipelineRunStatus,
    PipelineType,
)
from domain.pipelines.exceptions import (
    PipelineExecutionError,
    PipelineExternalServiceError,
    PipelineInputError,
    PipelineStorageError,
)
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
    PipelineTypeRegistry,
)
from domain.versioning.services import VersioningService
from utils.logger import get_logger

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])
config_router = APIRouter(prefix="/api/pipeline_configurations", tags=["pipelines"])

_logger = get_logger(__name__)


# ==================== Helper Functions ====================


def _handle_domain_error(exc: Exception) -> tuple[int, str]:
    """
    Map domain exceptions to HTTP status codes and error messages.

    Args:
        exc: The domain exception

    Returns:
        Tuple of (status_code, error_message)
    """
    if isinstance(exc, PipelineStorageError):
        _logger.error(f"Pipeline storage error: {exc}", exc_info=exc)
        return (
            http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Failed to persist pipeline state",
        )
    elif isinstance(exc, PipelineInputError):
        _logger.warning(f"Pipeline input error: {exc}")
        return (http_status.HTTP_400_BAD_REQUEST, str(exc))
    elif isinstance(exc, PipelineExternalServiceError):
        _logger.error(f"External service error: {exc}", exc_info=exc)
        return (
            http_status.HTTP_503_SERVICE_UNAVAILABLE,
            "External service unavailable",
        )
    elif isinstance(exc, PipelineExecutionError):
        _logger.error(f"Pipeline execution error: {exc}", exc_info=exc)
        return (
            http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Pipeline execution failed",
        )
    elif isinstance(exc, ValueError):
        _logger.error(f"Server misconfiguration error: {exc}", exc_info=exc)
        return (http_status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))
    else:
        _logger.error(f"Unexpected error in pipeline endpoint: {exc}", exc_info=exc)
        return (
            http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            "An unexpected error occurred",
        )


def _get_grounding_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Extract grounding-specific configuration.

    Args:
        config: Configuration dict

    Returns:
        Grounding config dict with top_n and weights
    """
    return {
        "top_n": config.get("top_n", 10),
        "weights": config.get(
            "weights",
            {
                "source_score": 0.3,
                "label_match": 0.3,
                "semantic_similarity": 0.4,
            },
        ),
    }


# ==================== Response Mapping ====================


def _to_response(run: PipelineRun) -> PipelineRunResponse:
    """
    Convert a domain PipelineRun to a response schema.

    Args:
        run: Domain PipelineRun entity

    Returns:
        PipelineRunResponse for JSON serialization
    """
    return PipelineRunResponse.model_validate(
        {
            "id": run.id,
            "batch_run_id": run.batch_run_id,
            "pipeline_type": run.pipeline_type.value,
            "implementation_id": run.implementation_id,
            "configuration_ref": run.configuration_ref,
            "configuration_slug": run.configuration_slug,
            "configuration_version": run.configuration_version,
            "input_summary": run.input_summary,
            "output_summary": run.output_summary,
            "llm_metadata": run.llm_metadata,
            "status": run.status.value,
            "created_at": run.created_at,
            "updated_at": None,
            "started_at": run.started_at,
            "failure_reason": run.failure_reason,
        }
    )


# ==================== Pipeline Type Enumeration ====================


@router.get("/types", response_model=list[PipelineTypeResponse])
async def list_pipeline_types() -> list[PipelineTypeResponse]:
    """
    List all registered pipeline types with input/output contracts.

    Returns:
        List of PipelineTypeResponse objects with type metadata
    """
    type_defs = PipelineTypeRegistry.list_types()
    return [
        PipelineTypeResponse(
            pipeline_type=td.pipeline_type.value,
            description=td.description,
            input_contract=td.input_contract,
            output_contract=td.output_contract,
        )
        for td in type_defs
    ]


@router.get(
    "/types/{pipeline_type}/implementations",
    response_model=list[ImplementationResponse],
)
async def list_implementations(
    pipeline_type: str,
    request: Request,
) -> list[ImplementationResponse]:
    """
    List all registered implementations for a pipeline type.

    Args:
        pipeline_type: The pipeline type (e.g., individual_extraction)
        request: FastAPI request (for registry access)

    Returns:
        List of ImplementationResponse objects

    Raises:
        HTTPException: 400 if pipeline type is invalid
    """
    try:
        ptype = PipelineType(pipeline_type)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pipeline type: {pipeline_type}",
        )

    impl_registry: PipelineImplementationRegistry = request.app.state.implementation_registry
    impls = impl_registry.list_by_type(ptype)

    return [
        ImplementationResponse(id=impl_id, pipeline_type=ptype.value) for impl_id in impls.keys()
    ]


def _system_config_to_response(
    pipeline_type: str,
    impl_id: str,
    config_ref: str,
    version_obj: Any,
) -> PipelineConfigurationResponse:
    """Convert an in-memory system configuration to a response schema."""
    cfg = version_obj.config
    params = None
    if any(k in cfg for k in ("temperature", "max_tokens", "top_p")):
        params = PipelineConfigurationParameters(
            temperature=cfg.get("temperature", 0.4),
            max_tokens=cfg.get("max_tokens", 800),
            top_p=cfg.get("top_p", 0.9),
        )
    provider = cfg.get("llm_provider") or cfg.get("provider")
    return PipelineConfigurationResponse(
        id=f"{pipeline_type}:{impl_id}:{config_ref}",
        config_ref=config_ref,
        pipeline_type=pipeline_type,
        implementation_id=impl_id,
        name=cfg.get("name") or config_ref,
        description=cfg.get("description"),
        provider=provider,
        model=cfg.get("model"),
        system_prompt=cfg.get("system_prompt"),
        user_prompt_template=cfg.get("user_prompt_template"),
        parameters=params,
        enabled=cfg.get("enabled", True),
        version=version_obj.version,
        is_system=True,
        created_at=None,
        updated_at=None,
    )


def _db_config_to_response(record: Any) -> PipelineConfigurationResponse:
    """Convert a DB pipeline configuration record to a response schema."""
    def _parse_dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except (ValueError, TypeError):
            return None

    return PipelineConfigurationResponse(
        id=record.id,
        config_ref=record.config_ref,
        pipeline_type=record.pipeline_type,
        implementation_id=record.implementation_id,
        name=record.name,
        description=record.description,
        provider=record.provider,
        model=record.model,
        system_prompt=record.system_prompt,
        user_prompt_template=record.user_prompt_template,
        parameters=PipelineConfigurationParameters(
            temperature=record.temperature,
            max_tokens=record.max_tokens,
            top_p=record.top_p,
        ),
        enabled=record.enabled,
        version=record.version,
        is_system=False,
        created_at=_parse_dt(record.created_at),
        updated_at=_parse_dt(record.updated_at),
    )


@router.get(
    "/types/{pipeline_type}/implementations/{impl_id}/configurations",
    response_model=list[PipelineConfigurationResponse],
)
async def list_configurations(
    pipeline_type: str,
    impl_id: str,
    request: Request,
) -> list[PipelineConfigurationResponse]:
    """
    List all configurations for a pipeline type and implementation.

    Returns both system (code-defined) and user-created configurations.

    Args:
        pipeline_type: The pipeline type
        impl_id: The implementation identifier
        request: FastAPI request (for registry and repo access)

    Returns:
        List of PipelineConfigurationResponse objects

    Raises:
        HTTPException: 400 if pipeline type is invalid, 404 if implementation not found
    """
    try:
        ptype = PipelineType(pipeline_type)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pipeline type: {pipeline_type}",
        )

    impl_registry: PipelineImplementationRegistry = request.app.state.implementation_registry
    config_registry: PipelineConfigurationRegistry = request.app.state.config_registry

    impl = impl_registry.get(ptype, impl_id)
    if impl is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Implementation not found: {ptype.value}:{impl_id}",
        )

    # User-created configs from the database (collected first to deduplicate registry)
    user_configs: list[Any] = []
    known_user_refs: set[str] = set()
    if hasattr(request.app.state, "pipeline_config_repo"):
        config_repo: PipelineConfigurationRepository = request.app.state.pipeline_config_repo
        try:
            user_configs = config_repo.list_for_type(ptype.value, impl_id)
            known_user_refs = config_repo.list_known_config_refs(ptype.value, impl_id)
        except Exception:
            _logger.warning("Failed to load user configurations from DB", exc_info=True)

    # System configs from the in-memory registry, excluding user-owned refs (active or deleted)
    system_configs = config_registry.list_configs(ptype, impl_id)
    result: list[PipelineConfigurationResponse] = [
        _system_config_to_response(ptype.value, impl_id, config_ref, version_obj)
        for config_ref, version_obj in system_configs
        if config_ref not in known_user_refs
    ]

    result.extend(_db_config_to_response(r) for r in user_configs)
    return result


@router.post(
    "/types/{pipeline_type}/implementations/{impl_id}/configurations",
    response_model=PipelineConfigurationResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_configuration(
    pipeline_type: str,
    impl_id: str,
    request: Request,
    body: PipelineConfigurationCreateRequest = Body(...),
) -> PipelineConfigurationResponse:
    """
    Create a new user pipeline configuration.

    Stores the configuration in operations.db and registers it in the
    in-memory registry so it is immediately available for pipeline runs.

    Args:
        pipeline_type: The pipeline type
        impl_id: The implementation identifier
        body: Configuration create request
        request: FastAPI request

    Returns:
        PipelineConfigurationResponse for the created configuration

    Raises:
        HTTPException: 400 if pipeline type invalid, 404 if implementation not found
    """
    try:
        ptype = PipelineType(pipeline_type)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pipeline type: {pipeline_type}",
        )

    impl_registry: PipelineImplementationRegistry = request.app.state.implementation_registry
    config_registry: PipelineConfigurationRegistry = request.app.state.config_registry

    if impl_registry.get(ptype, impl_id) is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Implementation not found: {ptype.value}:{impl_id}",
        )

    if not hasattr(request.app.state, "pipeline_config_repo"):
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configuration persistence not available",
        )

    config_repo: PipelineConfigurationRepository = request.app.state.pipeline_config_repo
    params = body.parameters

    record = config_repo.create(
        pipeline_type=ptype.value,
        implementation_id=impl_id,
        name=body.name,
        provider=body.provider,
        model=body.model,
        user_prompt_template=body.user_prompt_template,
        description=body.description,
        system_prompt=body.system_prompt,
        temperature=params.temperature,
        max_tokens=params.max_tokens,
        top_p=params.top_p,
        enabled=body.enabled,
    )

    # Register in the in-memory registry so runs can use it immediately
    config_dict = {
        "provider": record.provider,
        "model": record.model,
        "system_prompt": record.system_prompt or "",
        "user_prompt_template": record.user_prompt_template,
        "temperature": record.temperature,
        "max_tokens": record.max_tokens,
        "top_p": record.top_p,
        "enabled": record.enabled,
    }
    config_registry.register(ptype, impl_id, record.config_ref, config_dict)

    return _db_config_to_response(record)


# ==================== Pipeline Execution ====================


@router.post(
    "/{pipeline_type}/run",
    response_model=PipelineRunResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def run_pipeline(
    pipeline_type: str,
    request: Request,
    request_body: PipelineRunRequest = Body(...),
) -> PipelineRunResponse:
    """
    Invoke a pipeline by type.

    The request body structure depends on the pipeline type. Supported types:
    - individual_extraction: requires text and ontology_id
    - schema_extraction: requires documents, optional scope
    - schema_node_grounding: requires nodes and sources
    - schema_node_definition_refinement: requires node_id and
      current_definition, optional groundings and extraction_usages
    - schema_node_connection_refinement: requires scope_id and
      current_connections, optional groundings and extraction_usages

    Creates a pipeline run, executes it with the registered implementation,
    and returns the run with execution results.

    Args:
        pipeline_type: The pipeline type (e.g., individual_extraction)
        request_body: Type-specific request payload
        request: FastAPI request (for service access)

    Returns:
        PipelineRunResponse with the executed PipelineRun

    Raises:
        HTTPException: 400 for invalid input, 404 for missing config/impl, 500 for execution errors
    """
    try:
        ptype = PipelineType(pipeline_type)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pipeline type: {pipeline_type}",
        )

    repo = request.app.state.pipeline_run_repo
    batch_repo = request.app.state.batch_repo
    impl_registry = request.app.state.implementation_registry
    config_registry = request.app.state.config_registry
    llm_provider = request.app.state.llm_router

    # Verify implementation exists
    impl_class = impl_registry.get(ptype, request_body.implementation_id)
    if impl_class is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Implementation not found: {ptype.value}:{request_body.implementation_id}",
        )

    # Verify configuration exists. get_latest() retrieves the current version,
    # which is stored in the database along with the run. After a server restart,
    # get_version(slug, version) can re-resolve the same configuration because
    # configs are deterministically re-registered from code at startup.
    # This ensures that runs can always resolve their pinned (slug, version) pair
    # even across server restarts.
    config_version = config_registry.get_latest(
        ptype, request_body.implementation_id, request_body.configuration_ref
    )
    if config_version is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Configuration not found: {request_body.configuration_ref}",
        )

    # Create a batch for this single-run submission
    try:
        batch = batch_repo.create()
        batch_id = batch.id
    except Exception as e:
        status_code, message = _handle_domain_error(e)
        raise HTTPException(status_code=status_code, detail=message) from e

    # Extract input data from request body (now includes type-specific fields)
    input_data = request_body.model_dump()

    # Persist pipeline run to database only after validation succeeds
    specific_data = build_run_specific_data(ptype, input_data)
    try:
        run = repo.create(
            batch_run_id=batch_id,
            pipeline_type=ptype,
            implementation_id=request_body.implementation_id,
            configuration_ref=request_body.configuration_ref,
            configuration_slug=config_version.config_ref,
            configuration_version=config_version.version,
            specific_data=specific_data or None,
        )
        run_id = run.id  # Use the actual run ID returned by repo.create()
        # Mark this configuration version as referenced by this run
        config_registry.mark_version_referenced(
            ptype,
            request_body.implementation_id,
            config_version.config_ref,
            config_version.version,
        )
        # Update batch started_at timestamp
        batch_repo.update_started_at(batch_id)
    except PipelineStorageError as e:
        status_code, message = _handle_domain_error(e)
        raise HTTPException(status_code=status_code, detail=message) from e

    # Prepare services for orchestrator instantiation, including status writer
    services = {
        "extraction_service": getattr(request.app.state, "extraction_service", None),
        "ontology_repo": getattr(request.app.state, "ontology_repo", None),
        "extraction_repo": getattr(request.app.state, "extraction_repo", None),
        "grounding_adapter": getattr(request.app.state, "grounding_adapter", None),
        "scorer": getattr(request.app.state, "grounding_scorer", None),
        "grounding_config": _get_grounding_config(config_version.config),
        "refinement_config": config_version.config,
        # Ports + config for the open extraction implementations (open_v1)
        "nlp_processor": getattr(request.app.state, "nlp_processor", None),
        "embedding_service": getattr(request.app.state, "embedding_service", None),
        "clusterer": getattr(request.app.state, "clusterer", None),
        "schema_index": getattr(request.app.state, "schema_vector_index", None),
        "reference_source": getattr(request.app.state, "conceptnet_source", None),
        "open_schema_config": config_version.config,
        "open_individual_config": config_version.config,
        "run_id": run_id,
        "status_writer": repo,
    }

    # Instantiate orchestrator with dependencies (validates service dependencies)
    try:
        orchestrator = create_orchestrator(
            orchestrator_class=impl_class,
            llm_provider=llm_provider,
            services=services,
        )
    except ValueError as e:
        status_code, message = _handle_domain_error(e)
        raise HTTPException(status_code=status_code, detail=message) from e

    # Create initial state for execution with the actual run ID
    state = create_pipeline_state(
        run_id=run_id,
        pipeline_type=ptype,
        input_data=input_data,
        llm_provider=llm_provider,
    )

    # Execute the pipeline
    try:
        result_state = await orchestrator.execute(state)
    except (
        PipelineStorageError,
        PipelineInputError,
        PipelineExternalServiceError,
        PipelineExecutionError,
    ) as exc:
        status_code, message = _handle_domain_error(exc)
        try:
            repo.update_failure_info(run_id, str(exc), output_summary={"error": message})
            # Update batch timestamps and status when run fails
            batch_repo.update_completed_at(batch_id)
            batch_repo.update_status(batch_id, batch_repo.compute_aggregate_status(batch_id))
        except PipelineStorageError as db_err:
            _logger.error(f"Failed to update run status after execution error: {db_err}")
        raise HTTPException(status_code=status_code, detail=message) from exc
    except Exception as exc:
        domain_exc = PipelineExecutionError(f"Unexpected orchestrator failure: {str(exc)}")
        status_code, message = _handle_domain_error(domain_exc)
        try:
            repo.update_failure_info(run_id, str(exc), output_summary={"error": str(exc)})
            # Update batch timestamps and status when run fails
            batch_repo.update_completed_at(batch_id)
            batch_repo.update_status(batch_id, batch_repo.compute_aggregate_status(batch_id))
        except PipelineStorageError as db_err:
            _logger.error(f"Failed to update run status after execution error: {db_err}")
        raise HTTPException(status_code=status_code, detail=message) from exc

    # Update run with execution results (including any parse warnings)
    output_summary = result_state.result or {}
    parse_warnings = result_state.parse_warnings
    if parse_warnings:
        output_summary["warnings"] = parse_warnings
        for warning in parse_warnings:
            _logger.warning(
                f"Parse warning in {warning.get('stage', 'unknown')} for run {run_id}: "
                f"{warning.get('error', 'unknown error')}. "
                f"Response preview: {warning.get('response_preview', 'N/A')}. "
                f"Fallback action: {warning.get('fallback_action', 'N/A')}"
            )

    try:
        repo.update_summaries(
            run_id=run_id,
            output_summary=output_summary,
            llm_metadata={},
        )
        repo.update_status(run_id, result_state.current_status)
        # Update batch completed_at timestamp since this single-run batch is now complete
        batch_repo.update_completed_at(batch_id)
        # Compute and update batch status from its runs
        new_batch_status = batch_repo.compute_aggregate_status(batch_id)
        batch_repo.update_status(batch_id, new_batch_status)
    except PipelineStorageError as e:
        status_code, message = _handle_domain_error(e)
        raise HTTPException(status_code=status_code, detail=message) from e

    # Fetch updated run for response
    updated_run = repo.get(run_id)
    if updated_run is None:
        _logger.error(f"Failed to retrieve updated run: {run_id}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pipeline run after execution",
        )

    return _to_response(updated_run)


# ==================== Pipeline Run Retrieval ====================


@router.get("/runs/{run_id}", response_model=PipelineRunResponse)
async def get_pipeline_run(
    run_id: str,
    request: Request,
) -> PipelineRunResponse:
    """
    Fetch a PipelineRun by ID.

    Args:
        run_id: The pipeline run ID
        request: FastAPI request (for service access)

    Returns:
        PipelineRunResponse with the run details

    Raises:
        HTTPException: 404 if run not found
    """
    repo = request.app.state.pipeline_run_repo
    run = repo.get(run_id)

    if run is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run not found: {run_id}",
        )

    return _to_response(run)


@router.get("/runs/{run_id}/candidates", response_model=list[CandidateResponse])
async def get_pipeline_candidates(
    run_id: str,
    request: Request,
) -> list[CandidateResponse]:
    """
    Retrieve candidates from a completed pipeline run.

    Extracts the full candidate list with provenance and confidence scores
    from the pipeline run's output. The structure of candidates depends on
    the pipeline type:
    - schema_node_grounding: returns groundings with URI, label, confidence
    - schema_node_definition_refinement: returns definition candidates
    - schema_node_connection_refinement: returns connection candidates

    Args:
        run_id: The pipeline run ID
        request: FastAPI request (for service access)

    Returns:
        List of CandidateResponse objects with full provenance and confidence

    Raises:
        HTTPException: 404 if run not found, 400 if run has no candidates
    """
    repo = request.app.state.pipeline_run_repo
    run = repo.get(run_id)

    if run is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run not found: {run_id}",
        )

    # Extract candidates from output_summary based on pipeline type
    output_summary = run.output_summary or {}

    # Determine which key contains candidates based on pipeline type
    candidates_key = None
    candidates_data = []

    if run.pipeline_type == PipelineType.SCHEMA_NODE_GROUNDING:
        candidates_key = "groundings"
    elif run.pipeline_type == PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT:
        candidates_key = "candidates"
    elif run.pipeline_type == PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT:
        candidates_key = "deltas"
    elif run.pipeline_type == PipelineType.INDIVIDUAL_EXTRACTION:
        candidates_key = "triples"
    # NO_OP and SCHEMA_EXTRACTION pipelines don't produce candidates, return empty list

    if candidates_key and candidates_key in output_summary:
        candidates_data = output_summary[candidates_key]

    # Convert candidate dicts to response schema
    return [
        CandidateResponse.model_validate(
            {
                "uri": cand.get("uri") or cand.get("id") or "",
                "label": cand.get("label") or cand.get("name") or "",
                "description": cand.get("description") or "",
                "source": cand.get("source") or cand.get("source_uri") or "",
                "confidence": float(cand.get("confidence") or cand.get("match_confidence") or 0.0),
                "provenance": cand.get("provenance") or cand.get("match_rationale") or "",
            }
        )
        for cand in candidates_data
    ]


@router.get(
    "/runs/{run_id}/change-events",
    response_model=ListResponse[VersioningChangeEventResponse],
)
async def get_pipeline_run_change_events(
    run_id: str,
    request: Request,
    versioning_service: VersioningService = Depends(get_versioning_service),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
) -> ListResponse[VersioningChangeEventResponse]:
    """
    Get change events produced by applying a pipeline run.

    Args:
        run_id: The pipeline run ID
        request: FastAPI request (for service access)
        versioning_service: VersioningService for change history queries
        offset: Number of results to skip
        limit: Maximum number of results to return

    Returns:
        Paginated list of change events produced by this run

    Raises:
        HTTPException: 404 if run not found
    """
    repo = request.app.state.pipeline_run_repo
    run = repo.get(run_id)

    if run is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run not found: {run_id}",
        )

    # Get change events for this run's batch_run_id (fetch all for in-memory pagination)
    result = versioning_service.get_change_history(batch_run_id=run.batch_run_id, limit=None)

    # Apply pagination
    paginated_events = result.events[offset : offset + limit]

    return ListResponse(
        items=[VersioningChangeEventResponse.model_validate(e) for e in paginated_events],
        total=result.total,
        offset=offset,
        limit=limit,
    )


@router.get("/runs", response_model=ListResponse[PipelineRunResponse])
async def list_pipeline_runs(
    request: Request,
    pipeline_type: Optional[str] = Query(None, description="Filter by pipeline type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    implementation_id: Optional[str] = Query(None, description="Filter by implementation ID"),
    start_date: Optional[str] = Query(None, description="Filter by start date (ISO 8601 format)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (ISO 8601 format)"),
    applied: Optional[str] = Query(
        None, description="Filter by applied status: 'applied' or 'not-applied'"
    ),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> ListResponse[PipelineRunResponse]:
    """
    List pipeline runs with optional filtering.

    Results are returned in reverse chronological order (most recent first).

    Args:
        pipeline_type: Filter by pipeline type (optional)
        status: Filter by status (pending, running, completed, failed, etc.)
        implementation_id: Filter by implementation ID (optional)
        start_date: Filter by start date (ISO 8601 format, optional)
        end_date: Filter by end date (ISO 8601 format, optional)
        applied: Filter by applied status ('applied' or 'not-applied', optional)
        limit: Maximum number of results (1-500, default 100)
        offset: Number of results to skip for pagination (default 0)
        request: FastAPI request (for service access)

    Returns:
        Paginated list of PipelineRunResponse objects with total count

    Raises:
        HTTPException: 400 for invalid filters
    """
    repo = request.app.state.pipeline_run_repo

    # Validate and parse filter params before hitting the database
    ptype: PipelineType | None = None
    if pipeline_type:
        try:
            ptype = PipelineType(pipeline_type)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid pipeline type: {pipeline_type}",
            )

    status_enum: PipelineRunStatus | None = None
    if status:
        try:
            status_enum = PipelineRunStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}",
            )

    start_dt: datetime | None = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            if start_dt.tzinfo is not None:
                start_dt = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid start_date format: {start_date} (use ISO 8601)",
            )

    end_dt: datetime | None = None
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            if end_dt.tzinfo is not None:
                end_dt = end_dt.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid end_date format: {end_date} (use ISO 8601)",
            )

    applied_filter: bool | None = None
    if applied:
        if applied == "applied":
            applied_filter = True
        elif applied == "not-applied":
            applied_filter = False
        else:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Invalid applied filter: must be 'applied' or 'not-applied'",
            )

    filtered_runs, total = repo.list_filtered(
        pipeline_type=ptype,
        status=status_enum,
        implementation_id=implementation_id or None,
        start_date=start_dt,
        end_date=end_dt,
        applied=applied_filter,
        limit=limit,
        offset=offset,
    )

    responses = [_to_response(run) for run in filtered_runs]
    return ListResponse(items=responses, total=total, limit=limit, offset=offset)


@router.post(
    "/runs/{run_id}/apply",
    response_model=ApplyRunResponse,
    status_code=http_status.HTTP_200_OK,
)
async def apply_pipeline_run(
    run_id: str,
    request: Request,
    concept_scheme_id: Optional[str] = Query(
        None,
        description="Target concept scheme (required for schema_extraction)",
    ),
    taxonomy_id: Optional[str] = Query(
        None, description="Parent taxonomy (required for schema_extraction)"
    ),
    node_id: Optional[str] = Query(
        None,
        description="Target class node ID (required for schema_node_grounding)",
    ),
    confidence_threshold: float = Query(
        0.0,
        ge=0.0,
        le=1.0,
        description="Minimum candidate confidence",
    ),
    recognition_threshold: Optional[float] = Query(
        None,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum similarity for individual_extraction's recognition stage to "
            "resolve a mention to an existing individual. Defaults to the "
            "recognizer's configured value when omitted."
        ),
    ),
) -> ApplyRunResponse:
    """
    Apply a completed pipeline run's output to the ontology.

    Materializes pipeline candidates into DRAFT ontology entities:
    - schema_extraction: creates Class, PropertyDefinition, and Relationship entities
    - individual_extraction: creates Individual and Relationship entities
    - schema_node_grounding: adds ExternalReference entries to an existing Class
    - schema_node_definition_refinement: updates the description of an existing Class
    - schema_node_connection_refinement: adds or removes Relationship entities

    All created entities are stamped with Status.DRAFT and source_run_id set to the run ID
    for full traceability. The operation is idempotent — applying the same run twice
    produces no duplicates.

    Args:
        run_id: ID of the completed pipeline run to apply
        concept_scheme_id: Required for schema_extraction — target concept scheme
        taxonomy_id: Required for schema_extraction — parent taxonomy
        node_id: Required for schema_node_grounding — class to apply groundings to
        confidence_threshold: Minimum confidence score (0.0–1.0) for candidates to include
        recognition_threshold: Minimum similarity (0.0–1.0) for individual_extraction's
            recognition stage; defaults to the recognizer's configured value

    Returns:
        ApplyRunResponse with counts of created and skipped entities

    Raises:
        HTTPException: 404 if run not found, 422 if run is not completed, 400 for missing params
    """
    repo = request.app.state.pipeline_run_repo
    run = repo.get(run_id)
    if run is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run {run_id} not found",
        )

    if run.status != PipelineRunStatus.COMPLETED:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Pipeline run {run_id} is not completed (status: {run.status.value})",
        )

    ptype = run.pipeline_type

    set_batch_run_context(run.batch_run_id)
    try:
        try:
            if ptype == PipelineType.SCHEMA_EXTRACTION:
                if not concept_scheme_id:
                    raise HTTPException(
                        status_code=http_status.HTTP_400_BAD_REQUEST,
                        detail="concept_scheme_id is required for schema_extraction apply",
                    )
                if not taxonomy_id:
                    raise HTTPException(
                        status_code=http_status.HTTP_400_BAD_REQUEST,
                        detail="taxonomy_id is required for schema_extraction apply",
                    )
                svc = request.app.state.schema_extraction_apply_svc
                apply_result = svc.apply(
                    run=run,
                    concept_scheme_id=concept_scheme_id,
                    taxonomy_id=taxonomy_id,
                    confidence_threshold=confidence_threshold,
                )

            elif ptype == PipelineType.INDIVIDUAL_EXTRACTION:
                svc = request.app.state.individual_extraction_apply_svc
                apply_result = svc.apply(
                    run=run,
                    confidence_threshold=confidence_threshold,
                    recognition_threshold=recognition_threshold,
                )
                # Recognition sync (#1142): apply writes individuals directly via
                # the repo (bypassing OntologyService), so index the newly created
                # ones here. Best-effort — a failure must not fail the apply, and
                # the startup backfill catches any that slip through. Targeted to
                # created ids, so cost scales with the apply, not the whole graph.
                _index = getattr(request.app.state, "individual_vector_index", None)
                _repo = getattr(request.app.state, "ontology_repo", None)
                if _index is not None and _repo is not None:
                    for _iid in apply_result.created_individual_ids:
                        try:
                            _ind = _repo.get_individual(_iid)
                            if _ind is not None:
                                _index.index_individual(_ind.id, _ind.title, _ind.description)
                        except Exception:  # noqa: BLE001 - index sync must not fail the apply
                            _logger.error(
                                "Individual index sync failed for %s post-apply",
                                _iid,
                                exc_info=True,
                            )

            elif ptype == PipelineType.SCHEMA_NODE_GROUNDING:
                if not node_id:
                    raise HTTPException(
                        status_code=http_status.HTTP_400_BAD_REQUEST,
                        detail="node_id is required for schema_node_grounding apply",
                    )
                svc = request.app.state.schema_grounding_apply_svc
                apply_result = svc.apply(
                    run=run,
                    node_id=node_id,
                    confidence_threshold=confidence_threshold,
                )

            elif ptype == PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT:
                svc = request.app.state.schema_definition_apply_svc
                apply_result = svc.apply(run=run, confidence_threshold=confidence_threshold)

            elif ptype == PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT:
                svc = request.app.state.schema_connection_apply_svc
                apply_result = svc.apply(run=run, confidence_threshold=confidence_threshold)

            else:
                # NO_OP and any future types return empty result
                from domain.pipelines.apply_result import ApplyResult

                apply_result = ApplyResult()

        except ValueError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except (PipelineStorageError, IntegrityError, OperationalError) as exc:
            _logger.error(f"Storage/database error applying run {run_id}: {exc}")
            status_code, message = _handle_domain_error(
                exc if isinstance(exc, PipelineStorageError) else PipelineStorageError(str(exc))
            )
            raise HTTPException(status_code=status_code, detail=message) from exc
        except KeyError as exc:
            _logger.error(f"Malformed output data for run {run_id}: missing key {exc}")
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Pipeline output is malformed: missing key {str(exc)}",
            ) from exc
    finally:
        set_batch_run_context(None)

    return ApplyRunResponse(
        run_id=run_id,
        pipeline_type=ptype.value,
        classes_created=apply_result.classes_created,
        classes_updated=apply_result.classes_updated,
        classes_skipped=apply_result.classes_skipped,
        properties_created=apply_result.properties_created,
        properties_skipped=apply_result.properties_skipped,
        relationships_created=apply_result.relationships_created,
        relationships_removed=apply_result.relationships_removed,
        relationships_modified=apply_result.relationships_modified,
        relationships_skipped=apply_result.relationships_skipped,
        individuals_created=apply_result.individuals_created,
        individuals_skipped=apply_result.individuals_skipped,
        individuals_recognized=apply_result.individuals_recognized,
        external_references_created=apply_result.external_references_created,
        external_references_skipped=apply_result.external_references_skipped,
        created_class_ids=apply_result.created_class_ids,
        created_individual_ids=apply_result.created_individual_ids,
        created_relationship_ids=apply_result.created_relationship_ids,
        created_property_definition_ids=apply_result.created_property_definition_ids,
        created_external_reference_ids=apply_result.created_external_reference_ids,
        recognized_individual_ids=apply_result.recognized_individual_ids,
    )


@router.post(
    "/runs/{run_id}/revert",
    response_model=RevertRunResponse,
    status_code=http_status.HTTP_200_OK,
)
async def revert_pipeline_run(
    run_id: str,
    request: Request,
) -> RevertRunResponse:
    """
    Revert all changes made by a specific pipeline run.

    Walks the change_events for the given run in reverse order and applies
    the inverse of each operation. This restores the ontology to its state
    before the run was applied.

    The operation is idempotent — calling revert twice produces the same state
    without error.

    This endpoint only supports reverting runs from single-run batches. For multi-run
    batches, use the batch revert endpoint instead.

    Args:
        run_id: ID of the pipeline run to revert

    Returns:
        RevertRunResponse with count of events reverted

    Raises:
        HTTPException: 404 if run not found, 422 if batch has multiple runs, 500 for errors
    """
    repo = request.app.state.pipeline_run_repo
    run = repo.get(run_id)
    if run is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run {run_id} not found",
        )

    batch_runs = repo.list_by_batch_id(run.batch_run_id)
    if len(batch_runs) > 1:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot revert single run from multi-run batch. "
            f"Batch {run.batch_run_id} contains {len(batch_runs)} runs. "
            f"Use batch revert endpoint instead.",
        )

    revert_svc = request.app.state.revert_service
    try:
        revert_result = revert_svc.revert_with_summary(run.batch_run_id)
    except (PipelineStorageError, IntegrityError, OperationalError) as exc:
        _logger.error(f"Storage/database error reverting run {run_id}: {exc}")
        status_code, message = _handle_domain_error(
            exc if isinstance(exc, PipelineStorageError) else PipelineStorageError(str(exc))
        )
        raise HTTPException(status_code=status_code, detail=message) from exc
    except Exception as exc:
        _logger.error(f"Failed to revert run {run_id}: {exc}", exc_info=exc)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revert pipeline run due to an internal error",
        ) from exc
    return RevertRunResponse(
        run_id=run_id,
        events_reverted=revert_result.events_reverted,
        classes_deleted=revert_result.classes_deleted,
        individuals_deleted=revert_result.individuals_deleted,
        relationships_deleted=revert_result.relationships_deleted,
        properties_deleted=revert_result.properties_deleted,
        taxonomies_deleted=revert_result.taxonomies_deleted,
        concept_schemes_deleted=revert_result.concept_schemes_deleted,
        entities_restored=revert_result.entities_restored,
    )


# ==================== Batch Management ====================


@router.post(
    "/batches",
    status_code=http_status.HTTP_201_CREATED,
    response_model=BatchResponse,
)
async def create_batch(request: Request) -> dict[str, Any]:
    """
    Create a new batch.

    Args:
        request: FastAPI request (for service access)

    Returns:
        Batch info with id and status

    Raises:
        HTTPException: 500 for creation errors
    """
    batch_repo = request.app.state.batch_repo
    try:
        batch = batch_repo.create()
        return {
            "id": batch.id,
            "status": batch.status.value,
            "created_at": batch.created_at,
            "started_at": batch.started_at,
            "completed_at": batch.completed_at,
            "last_updated": batch.last_updated,
            "run_count": 0,
            "run_counts": {
                "pending": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
            },
        }
    except Exception as e:
        status_code, message = _handle_domain_error(e)
        raise HTTPException(status_code=status_code, detail=message) from e


@router.get("/batches/{batch_id}", response_model=BatchResponse)
async def get_batch(batch_id: str, request: Request) -> dict[str, Any]:
    """
    Get batch info and aggregate status over child runs.

    Args:
        batch_id: Batch ID
        request: FastAPI request (for service access)

    Returns:
        Batch info including aggregate status

    Raises:
        HTTPException: 404 if batch not found
    """
    batch_repo = request.app.state.batch_repo

    try:
        batch = batch_repo.get(batch_id)
        if not batch:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Batch not found: {batch_id}",
            )

        run_counts = batch_repo.get_run_counts(batch_id)
        total_runs = sum(run_counts.values())

        return {
            "id": batch.id,
            "status": batch.status.value,
            "created_at": batch.created_at,
            "started_at": batch.started_at,
            "completed_at": batch.completed_at,
            "last_updated": batch.last_updated,
            "run_count": total_runs,
            "run_counts": run_counts,
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        status_code, message = _handle_domain_error(e)
        raise HTTPException(status_code=status_code, detail=message) from e


@router.post(
    "/batches/{batch_id}/runs",
    status_code=http_status.HTTP_201_CREATED,
    response_model=EnqueueBatchRunsResponse,
)
async def enqueue_batch_runs(
    batch_id: str,
    request: Request,
    request_body: EnqueueBatchRunsRequest = Body(...),
) -> dict[str, Any]:
    """
    Enqueue multiple runs in a batch.

    Args:
        batch_id: Batch ID
        request_body: Contains 'runs' list with pipeline type and config
        request: FastAPI request (for service access)

    Returns:
        List of created run IDs

    Raises:
        HTTPException: 400 for invalid input, 404 for missing batch, 500 for errors
    """
    batch_repo = request.app.state.batch_repo
    pipeline_run_repo = request.app.state.pipeline_run_repo
    config_registry = request.app.state.config_registry
    impl_registry = request.app.state.implementation_registry

    # Verify batch exists
    batch = batch_repo.get(batch_id)
    if not batch:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Batch not found: {batch_id}",
        )

    runs_data = request_body.runs
    if not runs_data:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="'runs' must be a non-empty list",
        )

    created_run_ids = []
    try:
        for run_data in runs_data:
            pipeline_type_str = run_data.get("pipeline_type")
            impl_id = run_data.get("implementation_id", "default")
            config_ref = run_data.get("configuration_ref", "default")

            try:
                ptype = PipelineType(pipeline_type_str)
            except ValueError:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid pipeline type: {pipeline_type_str}",
                )

            # Validate implementation exists
            impl = impl_registry.get(ptype, impl_id)
            if not impl:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Implementation not found: {impl_id}",
                )

            config_version = config_registry.get_latest(ptype, impl_id, config_ref)
            if not config_version:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Configuration not found: {config_ref}",
                )

            specific_data = build_run_specific_data(ptype, run_data.get("specific_data") or {})
            run = pipeline_run_repo.create(
                batch_run_id=batch_id,
                pipeline_type=ptype,
                implementation_id=impl_id,
                configuration_ref=config_ref,
                configuration_slug=config_version.config_ref,
                configuration_version=config_version.version,
                specific_data=specific_data or None,
            )
            created_run_ids.append(run.id)

        # Update batch started_at timestamp if this is the first run
        if created_run_ids:
            batch_repo.update_started_at(batch_id)

        run_counts = batch_repo.get_run_counts(batch_id)
        total_runs = sum(run_counts.values())

        return {
            "batch_id": batch_id,
            "run_ids": created_run_ids,
            "run_count": total_runs,
        }
    except HTTPException:
        raise
    except Exception as e:
        status_code, message = _handle_domain_error(e)
        raise HTTPException(status_code=status_code, detail=message) from e


@router.post(
    "/batches/{batch_id}/cancel",
    status_code=http_status.HTTP_200_OK,
    response_model=CancelBatchResponse,
)
async def cancel_batch_runs(batch_id: str, request: Request) -> dict[str, Any]:
    """
    Cancel all PENDING runs in a batch.

    Args:
        batch_id: Batch ID
        request: FastAPI request (for service access)

    Returns:
        Count of cancelled runs

    Raises:
        HTTPException: 404 if batch not found
    """
    batch_repo = request.app.state.batch_repo
    pipeline_run_repo = request.app.state.pipeline_run_repo

    batch = batch_repo.get(batch_id)
    if not batch:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Batch not found: {batch_id}",
        )

    try:
        runs = pipeline_run_repo.list_by_batch_id(batch_id)
        cancelled_count = 0

        for run in runs:
            if run.status == PipelineRunStatus.PENDING:
                pipeline_run_repo.update_status(run.id, PipelineRunStatus.CANCELLED)
                cancelled_count += 1

        # Recompute batch status based on child runs
        if cancelled_count > 0:
            run_counts = batch_repo.get_run_counts(batch_id)
            # Only set completed_at if all runs are in terminal state
            if run_counts.get("pending", 0) == 0 and run_counts.get("running", 0) == 0:
                batch_repo.update_completed_at(batch_id)
            # Recompute status from child runs
            updated_batch = batch_repo.get(batch_id)
            if updated_batch:
                new_status = batch_repo.compute_aggregate_status(batch_id)
                batch_repo.update_status(batch_id, new_status)
        else:
            run_counts = batch_repo.get_run_counts(batch_id)

        updated_batch = batch_repo.get(batch_id)

        return {
            "batch_id": batch_id,
            "cancelled_count": cancelled_count,
            "status": updated_batch.status.value if updated_batch else batch.status.value,
            "run_counts": run_counts,
        }
    except Exception as e:
        status_code, message = _handle_domain_error(e)
        raise HTTPException(status_code=status_code, detail=message) from e


@router.post(
    "/batches/{batch_id}/resume",
    status_code=http_status.HTTP_200_OK,
    response_model=ResumeBatchResponse,
)
async def resume_batch_runs(batch_id: str, request: Request) -> dict[str, Any]:
    """
    Resume (re-enqueue) cancelled or failed runs in a batch back to PENDING status.

    Args:
        batch_id: Batch ID
        request: FastAPI request (for service access)

    Returns:
        Count of resumed runs

    Raises:
        HTTPException: 404 if batch not found
    """
    batch_repo = request.app.state.batch_repo
    pipeline_run_repo = request.app.state.pipeline_run_repo

    batch = batch_repo.get(batch_id)
    if not batch:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Batch not found: {batch_id}",
        )

    try:
        runs = pipeline_run_repo.list_by_batch_id(batch_id)
        resumed_count = 0

        for run in runs:
            if run.status in (PipelineRunStatus.CANCELLED, PipelineRunStatus.FAILED):
                pipeline_run_repo.update_status(run.id, PipelineRunStatus.PENDING)
                resumed_count += 1

        # Recompute batch status based on child runs
        if resumed_count > 0:
            new_status = batch_repo.compute_aggregate_status(batch_id)
            batch_repo.update_status(batch_id, new_status)

        run_counts = batch_repo.get_run_counts(batch_id)
        updated_batch = batch_repo.get(batch_id)

        return {
            "batch_id": batch_id,
            "resumed_count": resumed_count,
            "status": updated_batch.status.value if updated_batch else batch.status.value,
            "run_counts": run_counts,
        }
    except Exception as e:
        status_code, message = _handle_domain_error(e)
        raise HTTPException(status_code=status_code, detail=message) from e


# ==================== Pipeline Configuration CRUD ====================


@config_router.get(
    "/{config_id}",
    response_model=PipelineConfigurationResponse,
)
async def get_configuration(
    config_id: str,
    request: Request,
) -> PipelineConfigurationResponse:
    """
    Get a single user pipeline configuration by ID.

    Args:
        config_id: The configuration UUID
        request: FastAPI request

    Returns:
        PipelineConfigurationResponse

    Raises:
        HTTPException: 404 if not found or deleted
    """
    if not hasattr(request.app.state, "pipeline_config_repo"):
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configuration persistence not available",
        )

    config_repo: PipelineConfigurationRepository = request.app.state.pipeline_config_repo
    record = config_repo.get(config_id)
    if record is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Configuration not found: {config_id}",
        )
    return _db_config_to_response(record)


@config_router.put(
    "/{config_id}",
    response_model=PipelineConfigurationResponse,
)
async def update_configuration(
    config_id: str,
    request: Request,
    body: PipelineConfigurationUpdateRequest = Body(...),
) -> PipelineConfigurationResponse:
    """
    Update a user pipeline configuration, incrementing its version.

    Each update registers a new version in the in-memory registry so
    pipeline runs using it will see the latest configuration.

    Args:
        config_id: The configuration UUID
        body: Updated configuration fields
        request: FastAPI request

    Returns:
        PipelineConfigurationResponse with incremented version

    Raises:
        HTTPException: 404 if not found
    """
    if not hasattr(request.app.state, "pipeline_config_repo"):
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configuration persistence not available",
        )

    config_repo: PipelineConfigurationRepository = request.app.state.pipeline_config_repo
    config_registry: PipelineConfigurationRegistry = request.app.state.config_registry

    params = body.parameters
    record = config_repo.update(
        config_id=config_id,
        name=body.name,
        provider=body.provider,
        model=body.model,
        user_prompt_template=body.user_prompt_template,
        description=body.description,
        system_prompt=body.system_prompt,
        temperature=params.temperature,
        max_tokens=params.max_tokens,
        top_p=params.top_p,
        enabled=body.enabled,
    )
    if record is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Configuration not found: {config_id}",
        )

    # Register new version in the in-memory registry
    try:
        ptype = PipelineType(record.pipeline_type)
        config_dict = {
            "provider": record.provider,
            "model": record.model,
            "system_prompt": record.system_prompt or "",
            "user_prompt_template": record.user_prompt_template,
            "temperature": record.temperature,
            "max_tokens": record.max_tokens,
            "top_p": record.top_p,
            "enabled": record.enabled,
        }
        config_registry.register(ptype, record.implementation_id, record.config_ref, config_dict)
    except Exception:
        _logger.warning("Failed to register updated config in registry", exc_info=True)

    return _db_config_to_response(record)


@config_router.delete(
    "/{config_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
async def delete_configuration(
    config_id: str,
    request: Request,
) -> None:
    """
    Soft-delete a user pipeline configuration.

    The in-memory registry entry is preserved for run traceability.
    The configuration will no longer appear in list responses.

    Args:
        config_id: The configuration UUID
        request: FastAPI request

    Raises:
        HTTPException: 404 if not found or already deleted
    """
    if not hasattr(request.app.state, "pipeline_config_repo"):
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configuration persistence not available",
        )

    config_repo: PipelineConfigurationRepository = request.app.state.pipeline_config_repo
    deleted = config_repo.soft_delete(config_id)
    if not deleted:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Configuration not found: {config_id}",
        )
