"""
SystemMetricsCollector adapter implementation.

Aggregates component health status into a SystemHealth entity by querying
the readiness and availability of LLM providers, NLP pipeline, and embedding models.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

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

        # Check database connectivity
        db_connected = self._check_database_connected()
        if not db_connected:
            issues.append('Database not accessible')

        # Track which components had errors during checks
        error_components = set()

        # Check LLM providers with error handling
        llm_providers = []
        try:
            llm_providers = self._llm.list_available_providers()
        except Exception as e:
            logger.warning(f"Failed to check LLM providers: {e}")
            issues.append('Error checking LLM providers')
            error_components.add('llm')

        # Check NLP pipeline readiness with error handling
        nlp_ready = False
        try:
            nlp_ready = self._nlp.is_ready()
        except Exception as e:
            logger.warning(f"Failed to check NLP pipeline: {e}")
            issues.append('Error checking NLP pipeline')
            error_components.add('nlp')

        # Check embedding model with error handling
        embedding_loaded = False
        try:
            embedding_loaded = self._embedding.is_loaded()
        except Exception as e:
            logger.warning(f"Failed to check embedding model: {e}")
            issues.append('Error checking embedding model')
            error_components.add('embedding')

        # Aggregate issues for components that didn't have errors
        if 'nlp' not in error_components and not nlp_ready:
            issues.append('NLP pipeline not ready')
        if 'embedding' not in error_components and not embedding_loaded:
            issues.append('Embedding model not loaded')
        if 'llm' not in error_components and not llm_providers:
            issues.append('No LLM providers configured')

        # Calculate uptime in seconds
        now = datetime.now(timezone.utc)
        uptime = (now - self._start_time).total_seconds()

        # Determine overall status
        # "healthy" if all optional components are available
        # "degraded" if some optional components are missing
        # "unhealthy" if database is down
        if not db_connected:
            status = 'unhealthy'
        elif issues:
            status = 'degraded'
        else:
            status = 'healthy'

        logger.debug(
            f"Health check: status={status}, db_connected={db_connected}, nlp_ready={nlp_ready}, "
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
