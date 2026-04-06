"""
SystemMetricsCollector adapter implementation.

Aggregates component health status into a SystemHealth entity by querying
the readiness and availability of LLM providers, NLP pipeline, and embedding models.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from domain.admin.value_objects import (
    SystemHealthStatus,
    DatabaseHealth,
    ServiceMetrics,
    ComponentStatus,
    BackgroundTaskSummary,
)
from adapters.llm.provider_router import LLMProviderRouter
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from utils.logger import get_logger

logger = get_logger(__name__)


class SystemMetricsCollector:
    """
    Collects system health metrics from component adapters.

    Aggregates health status across LLM providers, NLP pipeline, and embedding
    models. Tracks uptime since application start. Implements the MetricsCollector
    protocol to provide granular health checks.
    """

    def __init__(
        self,
        llm_router: LLMProviderRouter,
        nlp_processor: SpacyNLPProcessor,
        embedding_service: SentenceTransformerEmbedding,
        start_time: datetime,
        db_engine: Optional[Engine] = None,
    ) -> None:
        """
        Initialize the system metrics collector.

        Args:
            llm_router: LLM provider router for checking available providers
            nlp_processor: NLP processor for checking readiness
            embedding_service: Embedding service for checking model load status
            start_time: Application start time for uptime calculation
            db_engine: SQLAlchemy engine for database connectivity checks

        Note:
            TODO: Replace concrete adapter types with port protocols when available.
            Currently coupled to LLMProviderRouter, SpacyNLPProcessor, and
            SentenceTransformerEmbedding directly due to lack of defined ports.
        """
        self._llm = llm_router
        self._nlp = nlp_processor
        self._embedding = embedding_service
        self._start_time = start_time
        self._db_engine = db_engine

    def _check_database_connected(self) -> bool:
        """
        Check database connectivity by executing a simple query.

        Returns:
            True if database is accessible, False otherwise
        """
        if self._db_engine is None:
            logger.warning("Database engine not provided to metrics collector")
            return False

        try:
            with self._db_engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.warning(f"Database connectivity check failed: {e}")
            return False

    def get_database_health(self) -> DatabaseHealth:
        """
        Get database health status.

        Returns:
            DatabaseHealth with connectivity and issue details
        """
        connected = self._check_database_connected()
        issues = []
        if not connected:
            issues.append("Database not accessible")
        return DatabaseHealth(connected=connected, issues=issues)

    def get_service_metrics(self) -> ServiceMetrics:
        """
        Get service-level metrics.

        Returns:
            ServiceMetrics with uptime and available LLM providers
        """
        now = datetime.now(timezone.utc)
        uptime = (now - self._start_time).total_seconds()

        llm_providers = []
        try:
            llm_providers = self._llm.list_available_providers()
        except Exception as e:
            logger.warning(f"Failed to check LLM providers: {e}")

        return ServiceMetrics(
            uptime_seconds=uptime, llm_providers_available=llm_providers
        )

    def get_embedding_model_status(self) -> ComponentStatus:
        """
        Get embedding model component status.

        Returns:
            ComponentStatus of the embedding model
        """
        try:
            loaded = self._embedding.is_loaded()
            details = "Embedding model loaded" if loaded else "Embedding model not loaded"
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
        return BackgroundTaskSummary(total=0, by_status={})
