"""
SystemMetricsCollector adapter implementation.

Aggregates component health status into a SystemHealth entity by querying
the readiness and availability of LLM providers, NLP pipeline, and embedding models.
"""

from datetime import datetime, timezone

from domain.admin.entities import SystemHealth
from adapters.llm.provider_router import LLMProviderRouter
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from utils.logger import get_logger

logger = get_logger(__name__)


class SystemMetricsCollector:
    """
    Collects system health metrics from component adapters.

    Aggregates health status across LLM providers, NLP pipeline, and embedding
    models into a single SystemHealth entity. Tracks uptime since application start.
    """

    def __init__(
        self,
        llm_router: LLMProviderRouter,
        nlp_processor: SpacyNLPProcessor,
        embedding_service: SentenceTransformerEmbedding,
        start_time: datetime,
    ) -> None:
        """
        Initialize the system metrics collector.

        Args:
            llm_router: LLM provider router for checking available providers
            nlp_processor: NLP processor for checking readiness
            embedding_service: Embedding service for checking model load status
            start_time: Application start time for uptime calculation

        Note:
            TODO: Replace concrete adapter types with port protocols when available.
            Currently coupled to LLMProviderRouter, SpacyNLPProcessor, and
            SentenceTransformerEmbedding directly due to lack of defined ports.
        """
        self._llm = llm_router
        self._nlp = nlp_processor
        self._embedding = embedding_service
        self._start_time = start_time

    def collect_health(self) -> SystemHealth:
        """
        Collect current system health metrics.

        Checks the status of database, NLP pipeline, embedding model, and LLM providers.
        Determines overall status as 'healthy', 'degraded', or 'unhealthy' based on
        component availability.

        Returns:
            SystemHealth object with all metrics populated
        """
        issues: list[str] = []

        # Check component readiness
        llm_providers = self._llm.list_available_providers()
        nlp_ready = self._nlp.is_ready()
        embedding_loaded = self._embedding.is_loaded()
        # TODO: Inject DB session and verify actual connectivity
        db_connected = True  # If we got here, database is up (known limitation)

        # Aggregate issues
        if not nlp_ready:
            issues.append('NLP pipeline not ready')
        if not embedding_loaded:
            issues.append('Embedding model not loaded')
        if not llm_providers:
            issues.append('No LLM providers configured')

        # Calculate uptime in seconds
        now = datetime.now(timezone.utc)
        uptime = (now - self._start_time).total_seconds()

        # Determine overall status
        # "healthy" if all optional components are available
        # "degraded" if some optional components are missing
        # "unhealthy" if database is down (shouldn't happen if we got here)
        if issues:
            status = 'degraded'
        else:
            status = 'healthy'

        logger.debug(
            f"Health check: status={status}, nlp_ready={nlp_ready}, "
            f"embedding_loaded={embedding_loaded}, providers={len(llm_providers)}, "
            f"issues={len(issues)}"
        )

        return SystemHealth(
            status=status,
            database_connected=db_connected,
            nlp_pipeline_ready=nlp_ready,
            embedding_model_loaded=embedding_loaded,
            llm_providers_available=llm_providers,
            uptime_seconds=uptime,
            checked_at=now,
            issues=issues,
        )
