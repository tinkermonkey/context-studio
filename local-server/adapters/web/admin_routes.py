"""
HTTP route handlers for the System Administration bounded context.

Endpoints:
- GET  /api/v1/admin/health                 - Check system health
- GET  /api/v1/admin/health/database        - Get database component health
- GET  /api/v1/admin/health/services        - Get service-level metrics
- GET  /api/v1/admin/health/embedding       - Get embedding model component status
- GET  /api/v1/admin/health/nlp             - Get NLP pipeline component status
- GET  /api/v1/admin/health/tasks           - Get background task summary
- GET  /api/v1/admin/configuration          - Retrieve configuration
- PATCH /api/v1/admin/configuration/{section} - Update configuration section
- POST /api/v1/admin/configuration/reset    - Reset configuration to defaults
- GET  /api/v1/admin/tasks                  - List background tasks
- GET  /api/v1/admin/tasks/{task_id}        - Get background task details
- GET  /api/v1/admin/stats/trends           - Get rolling daily creation counts per entity type

All route handlers use run_sync_in_executor to prevent blocking the async event loop
when calling synchronous domain service methods.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from adapters.web.dependencies import (
    get_admin_service,
    get_load_demo_dataset,
    get_local_db_session,
    get_operations_db_session,
)
from adapters.web.schemas.admin import (
    AppConfigurationResponse,
    BackgroundTaskResponse,
    BackgroundTaskSummaryResponse,
    ComponentStatusResponse,
    ConfigSectionUpdateRequest,
    DatabaseHealthResponse,
    DatasetCreateRequest,
    DatasetResponse,
    DatasetUpdateRequest,
    DemoDatasetDescriptorResponse,
    DemoDatasetLoadResponse,
    ServiceMetricsResponse,
    StatsTrendsResponse,
    SystemHealthResponse,
)
from domain.admin.demo_dataset_service import LoadDemoDataset
from domain.admin.exceptions import (
    ActiveDatasetError,
    AdminError,
    ConfigurationError,
    DatasetNotFoundError,
    DemoDatasetAlreadyLoadedError,
    DemoDatasetMalformedError,
    DemoDatasetNotFoundError,
    TaskNotFoundError,
)
from domain.admin.services import AdminService
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _handle_admin_error(exc: Exception) -> tuple[int, str]:
    """
    Map admin domain exceptions to HTTP status codes and error messages.

    Args:
        exc: The domain exception

    Returns:
        Tuple of (status_code, error_message)
    """
    if isinstance(exc, DatasetNotFoundError):
        logger.warning(f"Dataset not found: {exc}")
        return (status.HTTP_404_NOT_FOUND, str(exc))
    elif isinstance(exc, DemoDatasetNotFoundError):
        logger.warning(f"Demo dataset not found: {exc}")
        return (status.HTTP_404_NOT_FOUND, str(exc))
    elif isinstance(exc, DemoDatasetAlreadyLoadedError):
        logger.warning(f"Demo dataset already loaded: {exc}")
        return (status.HTTP_409_CONFLICT, str(exc))
    elif isinstance(exc, DemoDatasetMalformedError):
        logger.warning(f"Demo dataset malformed: {exc}")
        return (status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    elif isinstance(exc, ActiveDatasetError):
        logger.warning(f"Active dataset error: {exc}")
        return (status.HTTP_409_CONFLICT, str(exc))
    elif isinstance(exc, ConfigurationError):
        logger.warning(f"Configuration error: {exc}")
        return (status.HTTP_400_BAD_REQUEST, str(exc))
    elif isinstance(exc, TaskNotFoundError):
        logger.warning(f"Task not found: {exc}")
        return (status.HTTP_404_NOT_FOUND, str(exc))
    elif isinstance(exc, AdminError):
        logger.warning(f"Admin error: {exc}")
        return (status.HTTP_400_BAD_REQUEST, str(exc))
    else:
        logger.error(f"Unexpected error in admin endpoint: {exc}", exc_info=exc)
        return (status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred")


@router.get("/health", response_model=SystemHealthResponse)
async def check_health(
    service: AdminService = Depends(get_admin_service),
) -> SystemHealthResponse:
    """
    Check system health and component readiness.

    Returns the overall system health status along with the readiness of optional
    components (NLP pipeline, embedding model, LLM providers).

    Health status rules:
    - "healthy": All systems operational
    - "degraded": One or more issues detected (e.g., missing LLM providers, unavailable
      components, failed background tasks) but core systems functional
    - "unhealthy": Critical systems (database) unavailable

    Returns:
        SystemHealthResponse with status and component readiness

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        health = await run_sync_in_executor(service.check_health)
        return SystemHealthResponse.model_validate(health)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/health/database", response_model=DatabaseHealthResponse)
async def get_database_health(
    service: AdminService = Depends(get_admin_service),
) -> DatabaseHealthResponse:
    """
    Get database component health status.

    Returns detailed health information about the database connection and any issues.

    Returns:
        DatabaseHealthResponse with connectivity status and issues list

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        db_health = await run_sync_in_executor(service.get_database_health)
        return DatabaseHealthResponse.model_validate(db_health)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/health/services", response_model=ServiceMetricsResponse)
async def get_service_metrics(
    service: AdminService = Depends(get_admin_service),
) -> ServiceMetricsResponse:
    """
    Get service-level metrics.

    Returns system uptime and list of available LLM providers.

    Returns:
        ServiceMetricsResponse with uptime and available providers

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        metrics = await run_sync_in_executor(service.get_service_metrics)
        return ServiceMetricsResponse.model_validate(metrics)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/health/embedding", response_model=ComponentStatusResponse)
async def get_embedding_status(
    service: AdminService = Depends(get_admin_service),
) -> ComponentStatusResponse:
    """
    Get embedding model component status.

    Returns availability and status details for the embedding model.

    Returns:
        ComponentStatusResponse with availability and details

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        component_status = await run_sync_in_executor(service.get_embedding_model_status)
        return ComponentStatusResponse.model_validate(component_status)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/health/nlp", response_model=ComponentStatusResponse)
async def get_nlp_status(
    service: AdminService = Depends(get_admin_service),
) -> ComponentStatusResponse:
    """
    Get NLP pipeline component status.

    Returns availability and status details for the NLP pipeline.

    Returns:
        ComponentStatusResponse with availability and details

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        component_status = await run_sync_in_executor(service.get_nlp_pipeline_status)
        return ComponentStatusResponse.model_validate(component_status)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/health/tasks", response_model=BackgroundTaskSummaryResponse)
async def get_task_summary(
    service: AdminService = Depends(get_admin_service),
) -> BackgroundTaskSummaryResponse:
    """
    Get summary of background task execution status.

    Returns counts of tasks grouped by status (pending, running, completed, failed).

    Returns:
        BackgroundTaskSummaryResponse with task counts by status

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        summary = await run_sync_in_executor(service.get_background_task_summary)
        return BackgroundTaskSummaryResponse.from_domain(summary)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/configuration", response_model=AppConfigurationResponse)
async def get_configuration(
    service: AdminService = Depends(get_admin_service),
) -> AppConfigurationResponse:
    """
    Retrieve current application configuration.

    Returns all configuration sections with sensitive values (API keys)
    masked in the API response to prevent exposure through the HTTP interface.

    Returns:
        AppConfigurationResponse with configuration sections and masked API keys

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        config = await run_sync_in_executor(service.get_configuration)
        return AppConfigurationResponse.from_domain(config)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.patch(
    "/configuration/{section}",
    response_model=AppConfigurationResponse,
    status_code=status.HTTP_200_OK,
)
async def update_configuration(
    section: str,
    request: ConfigSectionUpdateRequest,
    service: AdminService = Depends(get_admin_service),
) -> AppConfigurationResponse:
    """
    Update a configuration section.

    Loads the current configuration, updates the specified section with new values,
    and persists the changes. Returns the updated configuration with masked API keys.

    Args:
        section: Name of the configuration section to update (e.g., "llm", "server")
        request: ConfigSectionUpdateRequest with key-value pairs to update
        service: Injected AdminService

    Returns:
        AppConfigurationResponse with updated configuration and masked API keys

    Raises:
        HTTPException 400: If the section does not exist
    """
    try:
        config = await run_sync_in_executor(service.update_configuration, section, request.updates)
        return AppConfigurationResponse.from_domain(config)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/configuration/reset", response_model=AppConfigurationResponse)
async def reset_configuration(
    service: AdminService = Depends(get_admin_service),
) -> AppConfigurationResponse:
    """
    Reset configuration to defaults while preserving credentials.

    Resets all configuration values to their defaults. Credential fields
    (API keys, secrets) are preserved. Returns configuration with masked credentials.

    Returns:
        AppConfigurationResponse with reset configuration and masked credentials

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        config = await run_sync_in_executor(service.reset_configuration)
        return AppConfigurationResponse.from_domain(config)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/tasks", response_model=list[BackgroundTaskResponse])
async def list_tasks(
    service: AdminService = Depends(get_admin_service),
) -> list[BackgroundTaskResponse]:
    """
    List all background tasks.

    Returns metadata and status for all registered background tasks,
    whether pending, running, completed, or failed.

    Returns:
        List of BackgroundTaskResponse objects

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        tasks = await run_sync_in_executor(service.list_tasks)
        return [BackgroundTaskResponse.model_validate(task) for task in tasks]
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/tasks/{task_id}", response_model=BackgroundTaskResponse)
async def get_task(
    task_id: str,
    service: AdminService = Depends(get_admin_service),
) -> BackgroundTaskResponse:
    """
    Retrieve background task details by ID.

    Returns metadata and current status for a specific background task.

    Args:
        task_id: Unique identifier of the task
        service: Injected AdminService

    Returns:
        BackgroundTaskResponse with task details and status

    Raises:
        HTTPException 404: If task_id does not exist
    """
    try:
        task = await run_sync_in_executor(service.get_task, task_id)
        return BackgroundTaskResponse.model_validate(task)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/datasets", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    request: DatasetCreateRequest,
    service: AdminService = Depends(get_admin_service),
) -> DatasetResponse:
    """
    Create a new dataset.

    Args:
        request: DatasetCreateRequest with title, filename, optional description
        service: AdminService from dependency injection

    Returns:
        Created DatasetResponse

    Raises:
        HTTPException: 400 if title is empty
    """
    try:
        dataset = await run_sync_in_executor(
            service.create_dataset,
            request.title,
            request.filename,
            request.description,
        )
        return DatasetResponse.model_validate(dataset)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/datasets", response_model=list[DatasetResponse])
async def list_datasets(
    service: AdminService = Depends(get_admin_service),
) -> list[DatasetResponse]:
    """
    List all datasets.

    Returns:
        List of all datasets
    """
    try:
        datasets = await run_sync_in_executor(service.list_datasets)
        return [DatasetResponse.model_validate(d) for d in datasets]
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    service: AdminService = Depends(get_admin_service),
) -> DatasetResponse:
    """
    Get a dataset by ID.

    Args:
        dataset_id: The dataset ID
        service: AdminService from dependency injection

    Returns:
        DatasetResponse

    Raises:
        HTTPException: 404 if not found
    """
    try:
        dataset = await run_sync_in_executor(service.get_dataset, dataset_id)
        return DatasetResponse.model_validate(dataset)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.put("/datasets/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: str,
    request: DatasetUpdateRequest,
    service: AdminService = Depends(get_admin_service),
) -> DatasetResponse:
    """
    Update a dataset's metadata.

    Args:
        dataset_id: The dataset ID
        request: DatasetUpdateRequest with optional fields to update
        service: AdminService from dependency injection

    Returns:
        Updated DatasetResponse

    Raises:
        HTTPException: 400 if invalid, 404 if not found
    """
    try:
        dataset = await run_sync_in_executor(
            service.update_dataset,
            dataset_id,
            request.title,
            request.description,
        )
        return DatasetResponse.model_validate(dataset)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: str,
    service: AdminService = Depends(get_admin_service),
) -> None:
    """
    Delete a dataset.

    Args:
        dataset_id: The dataset ID
        service: AdminService from dependency injection

    Raises:
        HTTPException: 404 if not found, 409 if it is the active dataset
    """
    try:
        await run_sync_in_executor(service.delete_dataset, dataset_id)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/datasets/{dataset_id}/activate", response_model=DatasetResponse)
async def activate_dataset(
    dataset_id: str,
    service: AdminService = Depends(get_admin_service),
) -> DatasetResponse:
    """
    Activate a dataset as the current workspace.

    Args:
        dataset_id: The dataset ID to activate
        service: AdminService from dependency injection

    Returns:
        Updated DatasetResponse with is_active=true

    Raises:
        HTTPException: 404 if not found
    """
    try:
        dataset = await run_sync_in_executor(service.activate_dataset, dataset_id)
        return DatasetResponse.model_validate(dataset)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/stats/trends", response_model=StatsTrendsResponse)
async def get_stats_trends(
    days: int = Query(default=7, ge=1, le=90, description="Number of calendar days to include"),
    local_db: Session = Depends(get_local_db_session),
    ops_db: Session = Depends(get_operations_db_session),
) -> StatsTrendsResponse:
    """
    Get rolling daily creation counts per entity type.

    Returns `days` integers per entity type (oldest-first), where index 0 represents
    `days-1` days ago and the last index represents today. Missing days are 0.

    Entity types covered:
    - taxonomies: change_events WHERE entity_type='taxonomy' AND operation='create'
    - classes: change_events WHERE entity_type='class' AND operation='create'
    - individuals: change_events WHERE entity_type='individual' AND operation='create'
    - pipelines: pipeline_configurations WHERE created_at >= cutoff (operations.db)

    Args:
        days: Number of calendar days to roll up (default 7, max 90)
        local_db: SQLAlchemy session for local.db (injected)
        ops_db: SQLAlchemy session for operations.db (injected)

    Returns:
        StatsTrendsResponse with per-type daily count arrays
    """
    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)

        # Build ordered date labels: [cutoff.date, ..., today]
        date_labels = [(cutoff + timedelta(days=i)).date() for i in range(days)]

        # --- Query change_events in local.db ---
        rows = local_db.execute(
            text(
                """
                SELECT date(timestamp) AS day, entity_type, COUNT(*) AS cnt
                FROM change_events
                WHERE operation = 'create'
                  AND entity_type IN ('taxonomy', 'class', 'individual')
                  AND timestamp >= :cutoff
                GROUP BY date(timestamp), entity_type
                """
            ),
            {"cutoff": cutoff.isoformat()},
        ).fetchall()

        # Accumulate counts keyed by (date_str, entity_type)
        event_counts: dict[tuple[str, str], int] = defaultdict(int)
        for row in rows:
            event_counts[(row[0], row[1])] += row[2]

        # --- Query pipeline_configurations in operations.db ---
        pipeline_rows = ops_db.execute(
            text(
                """
                SELECT date(created_at) AS day, COUNT(*) AS cnt
                FROM pipeline_configurations
                WHERE created_at >= :cutoff
                GROUP BY date(created_at)
                """
            ),
            {"cutoff": cutoff.isoformat()},
        ).fetchall()

        pipeline_counts: dict[str, int] = defaultdict(int)
        for row in pipeline_rows:
            pipeline_counts[row[0]] += row[1]

        # Build arrays: one integer per calendar day, oldest first
        taxonomies = [event_counts.get((str(d), "taxonomy"), 0) for d in date_labels]
        classes = [event_counts.get((str(d), "class"), 0) for d in date_labels]
        individuals = [event_counts.get((str(d), "individual"), 0) for d in date_labels]
        pipelines = [pipeline_counts.get(str(d), 0) for d in date_labels]

        return StatsTrendsResponse(
            taxonomies=taxonomies,
            classes=classes,
            individuals=individuals,
            pipelines=pipelines,
        )
    except Exception as exc:
        logger.error(f"Error fetching stats trends: {exc}", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve stats trends",
        )


# ==================== Demo datasets ====================


@router.get("/demo-datasets", response_model=list[DemoDatasetDescriptorResponse])
async def list_demo_datasets(
    service: LoadDemoDataset = Depends(get_load_demo_dataset),
) -> list[DemoDatasetDescriptorResponse]:
    """
    List demo datasets available to load.

    Returns:
        List of DemoDatasetDescriptorResponse, one per available dataset.

    Raises:
        HTTPException: 500 for internal errors.
    """
    try:
        descriptors = await run_sync_in_executor(service.list_available)
        return [DemoDatasetDescriptorResponse.model_validate(d) for d in descriptors]
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post(
    "/demo-datasets/{name}/load",
    response_model=DemoDatasetLoadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def load_demo_dataset(
    name: str,
    service: LoadDemoDataset = Depends(get_load_demo_dataset),
) -> DemoDatasetLoadResponse:
    """
    Load a demo dataset into the ontology repository.

    Materializes the dataset's gold-standard ontology slice (taxonomies, concept
    schemes, classes with parent_class_id chains, property definitions, and
    external references) directly into the database. No LLM, no network.

    Args:
        name: Stable identifier of the dataset (e.g. 'software-architecture').

    Returns:
        DemoDatasetLoadResponse with counts of each persisted entity type.

    Raises:
        HTTPException 404: if `name` is not registered.
        HTTPException 409: if the dataset's root taxonomy already exists.
        HTTPException 500: for internal errors.
    """
    try:
        result = await run_sync_in_executor(service.execute, name)
        return DemoDatasetLoadResponse.model_validate(result)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)
