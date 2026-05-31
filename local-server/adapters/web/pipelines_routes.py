"""
FastAPI routes for the Pipeline Orchestration bounded context.

This module implements HTTP endpoints for generic pipeline execution:
- GET /api/pipelines/types → List pipeline types
- GET /api/pipelines/types/{type}/implementations → List implementations
- GET /api/pipelines/types/{type}/implementations/{id}/configurations → Configs
- POST /api/pipelines/{type}/run → Invoke a pipeline
- GET /api/pipelines/runs/{run_id} → Fetch a PipelineRun by ID
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

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi import status as http_status

from adapters.factories.orchestrator_factory import (
    build_run_specific_data,
    create_orchestrator,
    create_pipeline_state,
)
from adapters.web.schemas.ontology import ListResponse
from adapters.web.schemas.pipelines import (
    ApplyRunResponse,
    BatchResponse,
    CancelBatchResponse,
    CandidateResponse,
    ConfigurationResponse,
    EnqueueBatchRunsRequest,
    EnqueueBatchRunsResponse,
    ImplementationResponse,
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineTypeResponse,
    ResumeBatchResponse,
    RevertRunResponse,
)
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
        return (
            http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Pipeline execution failed: {str(exc)}",
        )
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

    # Instantiate orchestrator with dependencies (validates service dependencies)
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
            ptype, request_body.implementation_id, config_version.config_ref, config_version.version
        )
    except PipelineStorageError as e:
        status_code, message = _handle_domain_error(e)
        raise HTTPException(status_code=status_code, detail=message) from e

    # Create initial state for execution with the actual run ID
    state = create_pipeline_state(
        run_id=run_id,
        pipeline_type=ptype,
        input_data=input_data,
        llm_provider=llm_provider,
    )

    # Write RUNNING status and started_at before invoking orchestrator
    try:
        repo.update_running_status(run_id, datetime.now(timezone.utc))
    except PipelineStorageError as e:
        status_code, message = _handle_domain_error(e)
        raise HTTPException(status_code=status_code, detail=message) from e

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
        except PipelineStorageError as db_err:
            _logger.error(f"Failed to update run status after execution error: {db_err}")
        raise HTTPException(status_code=status_code, detail=message) from exc
    except Exception as exc:
        domain_exc = PipelineExecutionError(f"Unexpected orchestrator failure: {str(exc)}")
        status_code, message = _handle_domain_error(domain_exc)
        try:
            repo.update_failure_info(run_id, str(exc), output_summary={"error": str(exc)})
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

    filtered_runs, total = repo.list_filtered(
        pipeline_type=ptype,
        status=status_enum,
        implementation_id=implementation_id or None,
        start_date=start_dt,
        end_date=end_dt,
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
            apply_result = svc.apply(run=run, confidence_threshold=confidence_threshold)

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
        external_references_created=apply_result.external_references_created,
        external_references_skipped=apply_result.external_references_skipped,
        created_class_ids=apply_result.created_class_ids,
        created_individual_ids=apply_result.created_individual_ids,
        created_relationship_ids=apply_result.created_relationship_ids,
        created_property_definition_ids=apply_result.created_property_definition_ids,
        created_external_reference_ids=apply_result.created_external_reference_ids,
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

    Walks the change_events for the given run_id in reverse order and applies
    the inverse of each operation. This restores the ontology to its state
    before the run was applied.

    The operation is idempotent — calling revert twice produces the same state
    without error.

    Args:
        run_id: ID of the pipeline run to revert

    Returns:
        RevertRunResponse with count of events reverted

    Raises:
        HTTPException: 404 if run not found, 500 for revert errors
    """
    repo = request.app.state.pipeline_run_repo
    run = repo.get(run_id)
    if run is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run {run_id} not found",
        )

    revert_svc = request.app.state.revert_service
    try:
        events_reverted = revert_svc.revert(run_id)
        return RevertRunResponse(run_id=run_id, events_reverted=events_reverted)
    except Exception as exc:
        _logger.error(f"Failed to revert run {run_id}: {exc}", exc_info=exc)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revert pipeline run: {str(exc)}",
        ) from exc


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
            "run_counts": {"pending": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0},
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

            run = pipeline_run_repo.create(
                batch_run_id=batch_id,
                pipeline_type=ptype,
                implementation_id=impl_id,
                configuration_ref=config_ref,
                configuration_slug=config_version.config_ref,
                configuration_version=config_version.version,
                specific_data=run_data.get("specific_data"),
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
