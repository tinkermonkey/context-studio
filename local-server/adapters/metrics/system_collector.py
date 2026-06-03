"""
SystemMetricsCollector adapter implementation.

Collects granular health metrics from component adapters (LLM providers, NLP pipeline,
embedding models, and database). Returns individual value objects with aggregation
handled by AdminService.check_health().
"""

from datetime import datetime, timezone
from types import MappingProxyType

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from domain.admin.ports import (
    HealthCheckableEmbedding,
    HealthCheckableLLM,
    HealthCheckableNLP,
)
from domain.admin.value_objects import (
    BackgroundTaskSummary,
    ComponentStatus,
    DatabaseHealth,
    ServiceMetrics,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class SystemMetricsCollector:
    """
    Collects system health metrics from component adapters.

    Aggregates health status across LLM providers, NLP pipeline, and embedding
    models. Tracks uptime since application start. Implements the MetricsCollector
    protocol to provide granular health checks.

    Error handling follows a two-layer pattern: this adapter catches and logs
    errors for ComponentStatus methods (returning safe defaults), but re-raises
    exceptions from get_service_metrics() so the caller can distinguish "no
    providers" from "check failed". AdminService.check_health() catches any
    exceptions that escape this layer.
    """

    def __init__(
        self,
        llm: HealthCheckableLLM,
        nlp: HealthCheckableNLP,
        embedding: HealthCheckableEmbedding,
        db_engine: Engine,
        start_time: float,
    ) -> None:
        """
        Initialize the system metrics collector.

        Args:
            llm: LLM component for checking available providers
            nlp: NLP component for checking readiness
            embedding: Embedding component for checking model load status
            db_engine: SQLAlchemy engine for database connectivity checks
            start_time: Application start time as Unix timestamp (seconds since epoch)
        """
        self._llm = llm
        self._nlp = nlp
        self._embedding = embedding
        self._start_time = start_time
        self._db_engine = db_engine

    def _check_database_connected(self) -> bool:
        """
        Check database connectivity by executing a simple query.

        Returns:
            True if database is accessible, False otherwise
        """
        try:
            with self._db_engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as e:
            logger.warning(f"Database connectivity check failed: {e}")
            return False

    def get_database_health(self) -> DatabaseHealth:
        """
        Get database health status.

        Returns:
            DatabaseHealth with connectivity and issue details
        """
        connected = self._check_database_connected()
        issues: tuple[str, ...] = ()
        if not connected:
            issues = ("Database not accessible",)
        return DatabaseHealth(connected=connected, issues=issues)

    def get_service_metrics(self) -> ServiceMetrics:
        """
        Get service-level metrics.

        Raises:
            Exception: If LLM provider check fails, exception is logged and re-raised
                to allow the service layer to distinguish between "no providers
                configured" and "failed to check providers"

        Returns:
            ServiceMetrics with uptime and available LLM providers
        """
        now = datetime.now(timezone.utc).timestamp()
        uptime = now - self._start_time

        try:
            llm_providers = self._llm.list_available_providers()
        except Exception as e:
            logger.warning(f"Failed to check LLM providers: {e}")
            raise

        return ServiceMetrics(
            uptime_seconds=uptime, llm_providers_available=tuple(llm_providers)
        )

    def get_embedding_model_status(self) -> ComponentStatus:
        """
        Get embedding model component status.

        Returns:
            ComponentStatus of the embedding model
        """
        try:
            loaded = self._embedding.is_loaded()
            details = (
                "Embedding model loaded" if loaded else "Embedding model not loaded"
            )
            return ComponentStatus(available=loaded, details=details)
        except Exception as e:
            logger.warning(f"Failed to check embedding model: {e}")
            return ComponentStatus(
                available=False, details=f"Error checking embedding model: {e}"
            )

    def get_nlp_pipeline_status(self) -> ComponentStatus:
        """
        Get NLP pipeline component status.

        Returns:
            ComponentStatus of the NLP pipeline
        """
        try:
            ready = self._nlp.is_ready()
            details = "NLP pipeline ready" if ready else "NLP pipeline not ready"
            return ComponentStatus(available=ready, details=details)
        except Exception as e:
            logger.warning(f"Failed to check NLP pipeline: {e}")
            return ComponentStatus(
                available=False, details=f"Error checking NLP pipeline: {e}"
            )

    def get_background_task_summary(self) -> BackgroundTaskSummary:
        """
        Get summary of background task statuses.

        Returns:
            BackgroundTaskSummary with task counts by status
        """
        # Currently no background task tracking in the system
        return BackgroundTaskSummary(by_status=MappingProxyType({}))
