"""
FastAPI routes for the Pipeline Orchestration bounded context.

This module implements HTTP endpoints for generic pipeline execution:
- GET    /api/pipelines/types                                    → List pipeline types
- GET    /api/pipelines/types/{type}/implementations             → List implementations for type
- GET    /api/pipelines/types/{type}/implementations/{id}/configurations → List configs for impl
- POST   /api/pipelines/{type}/run                               → Invoke a pipeline
- GET    /api/pipelines/runs/{run_id}                            → Fetch a PipelineRun by ID
- GET    /api/pipelines/runs                                     → List PipelineRuns with filters

Each endpoint is a thin adapter that:
1. Receives HTTP request + parsed Pydantic schema
2. Calls domain service with domain entities
3. Catches domain exceptions and maps to HTTP status codes
4. Returns response schema serialized as JSON

No business logic lives here—all validation and constraints are in the domain service.
Error handling translates domain exceptions to appropriate HTTP responses.
"""

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi import status as http_status

from adapters.web.orchestrator_factory import create_orchestrator, create_pipeline_state
from adapters.web.schemas.ontology import ListResponse
from adapters.web.schemas.pipelines import (
    CandidateResponse,
    ConfigurationResponse,
    ImplementationResponse,
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineTypeResponse,
)
from domain.pipeline.exceptions import (
    PipelineError,
    PipelineExecutionError,
    PipelineExternalServiceError,
    PipelineInputError,
    PipelineStorageError,
)
from domain.pipelines.entities import PipelineRun, PipelineRunStatus, PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
    PipelineTypeRegistry,
)
from utils.logger import get_logger

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])

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
        return (http_status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to persist pipeline state")
    elif isinstance(exc, PipelineInputError):
        _logger.warning(f"Pipeline input error: {exc}")
        return (http_status.HTTP_400_BAD_REQUEST, str(exc))
    elif isinstance(exc, PipelineExternalServiceError):
        _logger.error(f"External service error: {exc}", exc_info=exc)
        return (http_status.HTTP_503_SERVICE_UNAVAILABLE, "External service unavailable")
    elif isinstance(exc, PipelineExecutionError):
        _logger.error(f"Pipeline execution error: {exc}", exc_info=exc)
        return (http_status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))
    elif isinstance(exc, PipelineError):
        _logger.error(f"Unexpected pipeline error: {exc}", exc_info=exc)
        return (http_status.HTTP_500_INTERNAL_SERVER_ERROR, "Pipeline execution failed")
    elif isinstance(exc, ValueError):
        _logger.warning(f"Invalid pipeline input: {exc}")
        return (http_status.HTTP_400_BAD_REQUEST, str(exc))
    else:
        _logger.error(f"Unexpected error in pipeline endpoint: {exc}", exc_info=exc)
        return (http_status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred")


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
        "weights": config.get("weights", {
            "source_score": 0.3,
            "label_match": 0.3,
            "semantic_similarity": 0.4,
        }),
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
            "input_summary": run.input_summary,
            "output_summary": run.output_summary,
            "llm_metadata": run.llm_metadata,
            "status": run.status.value,
            "created_at": run.created_at,
            "updated_at": None,
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


@router.get(
    "/types/{pipeline_type}/implementations/{impl_id}/configurations",
    response_model=list[ConfigurationResponse],
)
async def list_configurations(
    pipeline_type: str,
    impl_id: str,
    request: Request,
) -> list[ConfigurationResponse]:
    """
    List all configurations for a pipeline type and implementation.

    Args:
        pipeline_type: The pipeline type
        impl_id: The implementation identifier
        request: FastAPI request (for registry access)

    Returns:
        List of ConfigurationResponse objects

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

    configs = config_registry.list_configs(ptype, impl_id)
    return [
        ConfigurationResponse(
            config_ref=config_ref,
            version=version.version,
            config=version.config,
        )
        for config_ref, version in configs
    ]


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
    - schema_node_definition_refinement: requires nodes, optional context
    - schema_node_connection_refinement: requires edges, optional strategy

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

    # Verify configuration exists
    config_version = config_registry.get_latest(
        ptype, request_body.implementation_id, request_body.configuration_ref
    )
    if config_version is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Configuration not found: {request_body.configuration_ref}",
        )

    # Create pipeline run in pending state
    run_id = str(uuid4())

    # Prepare type-specific data
    specific_data: dict[str, Any] = {}
    if ptype == PipelineType.INDIVIDUAL_EXTRACTION:
        # Extract text from raw request body since PipelineRunRequest base class
        # doesn't include type-specific fields (Pydantic drops extra fields)
        raw_body = await request.json()
        text = raw_body.get("text", "")
        source_text_hash = sha256(text.encode()).hexdigest()
        specific_data["source_text_hash"] = source_text_hash

    try:
        repo.create(
            batch_run_id=run_id,
            pipeline_type=ptype,
            implementation_id=request_body.implementation_id,
            configuration_ref=request_body.configuration_ref,
            specific_data=specific_data if specific_data else None,
        )
    except PipelineStorageError as e:
        status_code, message = _handle_domain_error(e)
        raise HTTPException(status_code=status_code, detail=message) from e

    # Prepare services for orchestrator instantiation
    services = {
        "extraction_service": getattr(request.app.state, "extraction_service", None),
        "ontology_repo": getattr(request.app.state, "ontology_repo", None),
        "extraction_repo": getattr(request.app.state, "extraction_repo", None),
        "grounding_adapter": getattr(request.app.state, "grounding_adapter", None),
        "scorer": getattr(request.app.state, "grounding_scorer", None),
        "grounding_config": _get_grounding_config(config_version.config),
        "refinement_config": config_version.config,
    }

    # Instantiate orchestrator with dependencies
    try:
        orchestrator = create_orchestrator(
            orchestrator_class=impl_class,
            llm_provider=llm_provider,
            services=services,
        )
    except ValueError as e:
        exc = PipelineInputError(f"Failed to instantiate orchestrator: {str(e)}")
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message) from e

    # Extract input data from request body (type-specific fields)
    input_data = request_body.model_dump()

    # Create initial state for execution
    state = create_pipeline_state(
        run_id=run_id,
        pipeline_type=ptype,
        input_data=input_data,
        llm_provider=llm_provider,
    )

    # Execute the pipeline
    try:
        result_state = await orchestrator.execute(state)
    except PipelineError as exc:
        status_code, message = _handle_domain_error(exc)
        try:
            repo.update_status(run_id, PipelineRunStatus.FAILED)
            repo.update_summaries(run_id=run_id, output_summary={"error": message})
        except PipelineStorageError as db_err:
            _logger.error(f"Failed to update run status after execution error: {db_err}")
        raise HTTPException(status_code=status_code, detail=message) from exc
    except Exception as exc:
        domain_exc = PipelineExecutionError(f"Unexpected orchestrator failure: {str(exc)}")
        status_code, message = _handle_domain_error(domain_exc)
        try:
            repo.update_status(run_id, PipelineRunStatus.FAILED)
            repo.update_summaries(run_id=run_id, output_summary={"error": str(exc)})
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
        repo.update_status(run_id, PipelineRunStatus.COMPLETED)
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
        CandidateResponse.model_validate({
            "uri": cand.get("uri") or cand.get("id") or "",
            "label": cand.get("label") or cand.get("name") or "",
            "description": cand.get("description") or "",
            "source": cand.get("source") or cand.get("source_uri") or "",
            "confidence": float(cand.get("confidence") or cand.get("match_confidence") or 0.0),
            "provenance": cand.get("provenance") or cand.get("match_rationale") or "",
        })
        for cand in candidates_data
    ]


@router.get("/runs", response_model=ListResponse[PipelineRunResponse])
async def list_pipeline_runs(
    request: Request,
    pipeline_type: Optional[str] = Query(None, description="Filter by pipeline type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    implementation_id: Optional[str] = Query(None, description="Filter by implementation ID"),
    start_date: Optional[str] = Query(None, description="Filter by start date (ISO 8601 format)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (ISO 8601 format)"),
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
        limit: Maximum number of results (1-500, default 100)
        offset: Number of results to skip for pagination (default 0)
        request: FastAPI request (for service access)

    Returns:
        Paginated list of PipelineRunResponse objects with total count

    Raises:
        HTTPException: 400 for invalid filters
    """
    repo = request.app.state.pipeline_run_repo

    # Get all runs; filtering happens in-memory for simplicity
    all_runs = repo.list()

    # Apply filters
    filtered_runs = all_runs
    if pipeline_type:
        try:
            ptype = PipelineType(pipeline_type)
            filtered_runs = [r for r in filtered_runs if r.pipeline_type == ptype]
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid pipeline type: {pipeline_type}",
            )

    if status:
        try:
            status_enum = PipelineRunStatus(status)
            filtered_runs = [r for r in filtered_runs if r.status == status_enum]
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}",
            )

    if implementation_id:
        filtered_runs = [r for r in filtered_runs if r.implementation_id == implementation_id]

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            # Normalize to naive UTC for consistent comparison with naive DB values
            if start_dt.tzinfo is not None:
                start_dt = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
            filtered_runs = [
                r for r in filtered_runs if r.created_at.replace(tzinfo=None) >= start_dt
            ]
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid start_date format: {start_date} (use ISO 8601)",
            )

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            # Normalize to naive UTC for consistent comparison with naive DB values
            if end_dt.tzinfo is not None:
                end_dt = end_dt.astimezone(timezone.utc).replace(tzinfo=None)
            filtered_runs = [
                r for r in filtered_runs if r.created_at.replace(tzinfo=None) <= end_dt
            ]
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid end_date format: {end_date} (use ISO 8601)",
            )

    # Pagination
    total = len(filtered_runs)
    paginated_runs = filtered_runs[offset : offset + limit]

    responses = [_to_response(run) for run in paginated_runs]

    return ListResponse(items=responses, total=total, limit=limit, offset=offset)
