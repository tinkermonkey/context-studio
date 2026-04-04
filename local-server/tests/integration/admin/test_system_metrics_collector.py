"""
Integration tests for SystemMetricsCollector adapter.

Tests the collector's ability to aggregate component health status
into a SystemHealth entity.
"""

import sys
import os
import time
from datetime import datetime, timezone, timedelta
import tempfile

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine, text

from adapters.metrics.system_collector import SystemMetricsCollector
from adapters.llm.provider_router import LLMProviderRouter
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from domain.admin.entities import SystemHealth


def test_collect_health_with_no_providers():
    """Test health collection when no LLM providers are configured."""
    start_time = datetime.now(timezone.utc) - timedelta(seconds=10)

    llm_router = LLMProviderRouter(openai_api_key="", anthropic_api_key="")
    nlp_processor = SpacyNLPProcessor()
    embedding_service = SentenceTransformerEmbedding()

    # Without db_engine, status will be unhealthy due to database not accessible
    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time, db_engine=None)
    health = collector.collect_health()

    assert isinstance(health, SystemHealth)
    assert health.status in ("healthy", "degraded", "unhealthy")
    assert health.database_connected is False  # No engine provided
    assert isinstance(health.llm_providers_available, list)
    assert len(health.llm_providers_available) == 0
    assert isinstance(health.uptime_seconds, float)
    assert health.uptime_seconds >= 10.0  # Should be at least ~10 seconds
    assert isinstance(health.issues, list)
    assert "No LLM providers configured" in health.issues
    assert "Database not accessible" in health.issues


def test_collect_health_structure():
    """Test that collect_health returns complete SystemHealth structure."""
    start_time = datetime.now(timezone.utc)

    llm_router = LLMProviderRouter(openai_api_key="", anthropic_api_key="")
    nlp_processor = SpacyNLPProcessor()
    embedding_service = SentenceTransformerEmbedding()

    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time, db_engine=None)
    health = collector.collect_health()

    # Verify all required fields are present
    assert hasattr(health, "status")
    assert hasattr(health, "database_connected")
    assert hasattr(health, "nlp_pipeline_ready")
    assert hasattr(health, "embedding_model_loaded")
    assert hasattr(health, "llm_providers_available")
    assert hasattr(health, "uptime_seconds")
    assert hasattr(health, "checked_at")
    assert hasattr(health, "issues")

    # Verify field types
    assert isinstance(health.status, str)
    assert isinstance(health.database_connected, bool)
    assert isinstance(health.nlp_pipeline_ready, bool)
    assert isinstance(health.embedding_model_loaded, bool)
    assert isinstance(health.llm_providers_available, list)
    assert isinstance(health.uptime_seconds, float)
    assert isinstance(health.checked_at, datetime)
    assert isinstance(health.issues, list)


def test_collect_health_status_degraded_without_embedding():
    """Test that status is 'unhealthy' when db engine is missing and 'degraded' when db is ok but components fail."""
    start_time = datetime.now(timezone.utc)

    # Invalid model name will prevent loading
    embedding_service = SentenceTransformerEmbedding(model_name="nonexistent-model")
    # Don't trigger loading
    assert not embedding_service.is_loaded()

    llm_router = LLMProviderRouter(openai_api_key="", anthropic_api_key="")
    nlp_processor = SpacyNLPProcessor()

    # Without db_engine, status will be unhealthy
    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time, db_engine=None)
    health = collector.collect_health()

    # Status is unhealthy due to missing database engine
    assert health.status == "unhealthy"
    assert health.database_connected is False
    assert health.embedding_model_loaded is False
    assert len(health.issues) > 0


def test_collect_health_uptime_calculation():
    """Test that uptime is correctly calculated from start time."""
    # Start 30 seconds ago
    start_time = datetime.now(timezone.utc) - timedelta(seconds=30)

    llm_router = LLMProviderRouter(openai_api_key="", anthropic_api_key="")
    nlp_processor = SpacyNLPProcessor()
    embedding_service = SentenceTransformerEmbedding()

    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time, db_engine=None)
    health = collector.collect_health()

    # Uptime should be approximately 30 seconds (allowing some variance)
    assert 25.0 < health.uptime_seconds < 35.0


def test_collect_health_checked_at_timestamp():
    """Test that checked_at timestamp is set to approximately now."""
    start_time = datetime.now(timezone.utc)

    llm_router = LLMProviderRouter(openai_api_key="", anthropic_api_key="")
    nlp_processor = SpacyNLPProcessor()
    embedding_service = SentenceTransformerEmbedding()

    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time, db_engine=None)
    before = datetime.now(timezone.utc)
    health = collector.collect_health()
    after = datetime.now(timezone.utc)

    # checked_at should be between before and after with a small tolerance
    assert before <= health.checked_at <= after + timedelta(seconds=1)


def test_collect_health_multiple_calls():
    """Test that multiple health checks reflect changing uptime."""
    start_time = datetime.now(timezone.utc)

    llm_router = LLMProviderRouter(openai_api_key="", anthropic_api_key="")
    nlp_processor = SpacyNLPProcessor()
    embedding_service = SentenceTransformerEmbedding()

    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time, db_engine=None)

    health1 = collector.collect_health()
    time.sleep(0.1)  # Small delay
    health2 = collector.collect_health()

    # Second health check should have greater uptime
    assert health2.uptime_seconds > health1.uptime_seconds


def test_collect_health_issues_list():
    """Test that issues list is populated correctly based on component status."""
    start_time = datetime.now(timezone.utc)

    # Create router with no providers
    llm_router = LLMProviderRouter(openai_api_key="", anthropic_api_key="")
    nlp_processor = SpacyNLPProcessor()
    # Don't load the embedding model
    embedding_service = SentenceTransformerEmbedding(model_name="invalid-model")

    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time, db_engine=None)
    health = collector.collect_health()

    # Should have issues for missing providers, embedding, and database
    assert isinstance(health.issues, list)
    assert len(health.issues) > 0
    assert any("LLM" in issue or "Database" in issue for issue in health.issues)


def test_collect_health_database_check_with_no_engine():
    """Test that database_connected is False when no engine is provided."""
    start_time = datetime.now(timezone.utc)

    llm_router = LLMProviderRouter(openai_api_key="", anthropic_api_key="")
    nlp_processor = SpacyNLPProcessor()
    embedding_service = SentenceTransformerEmbedding()

    # Collector without db_engine should report database not connected
    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time, db_engine=None)
    health = collector.collect_health()

    # Database should be reported as not connected when no engine is provided
    assert health.database_connected is False
    assert "Database not accessible" in health.issues


def test_collect_health_database_connected_with_real_engine():
    """Test that database_connected is True when a real SQLite engine is provided."""
    start_time = datetime.now(timezone.utc)

    # Create a temporary SQLite database for testing
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Create a real SQLite engine
        db_engine = create_engine(f"sqlite:///{db_path}")

        # Verify the engine is functional by executing a test query
        with db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        llm_router = LLMProviderRouter(openai_api_key="", anthropic_api_key="")
        nlp_processor = SpacyNLPProcessor()
        embedding_service = SentenceTransformerEmbedding()

        # Collector with real db_engine should report database connected
        collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time, db_engine=db_engine)
        health = collector.collect_health()

        # Database should be reported as connected
        assert health.database_connected is True
        assert "Database not accessible" not in health.issues
        # Status should be degraded (not healthy) due to missing providers, but not unhealthy
        assert health.status in ("healthy", "degraded")
        assert health.status != "unhealthy"
    finally:
        # Cleanup
        import os as os_module
        if os_module.path.exists(db_path):
            os_module.unlink(db_path)
