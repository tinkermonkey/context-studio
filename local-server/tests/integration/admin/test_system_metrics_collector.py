"""
Integration tests for SystemMetricsCollector adapter.

Tests the collector's ability to aggregate component health status
into a SystemHealth entity.
"""

import sys
import os
import time
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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

    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time)
    health = collector.collect_health()

    assert isinstance(health, SystemHealth)
    assert health.status in ("healthy", "degraded")
    assert health.database_connected is True
    assert isinstance(health.llm_providers_available, list)
    assert len(health.llm_providers_available) == 0
    assert isinstance(health.uptime_seconds, float)
    assert health.uptime_seconds >= 10.0  # Should be at least ~10 seconds
    assert isinstance(health.issues, list)
    assert "No LLM providers configured" in health.issues


def test_collect_health_structure():
    """Test that collect_health returns complete SystemHealth structure."""
    start_time = datetime.now(timezone.utc)

    llm_router = LLMProviderRouter(openai_api_key="", anthropic_api_key="")
    nlp_processor = SpacyNLPProcessor()
    embedding_service = SentenceTransformerEmbedding()

    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time)
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
    """Test that status is 'degraded' when embedding model is not loaded."""
    start_time = datetime.now(timezone.utc)

    # Invalid model name will prevent loading
    embedding_service = SentenceTransformerEmbedding(model_name="nonexistent-model")
    # Don't trigger loading
    assert not embedding_service.is_loaded()

    llm_router = LLMProviderRouter(openai_api_key="", anthropic_api_key="")
    nlp_processor = SpacyNLPProcessor()

    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time)
    health = collector.collect_health()

    # Should be degraded due to missing embedding and providers
    assert health.status == "degraded"
    assert health.embedding_model_loaded is False
    assert "Embedding model not loaded" in health.issues or len(health.issues) > 0


def test_collect_health_uptime_calculation():
    """Test that uptime is correctly calculated from start time."""
    # Start 30 seconds ago
    start_time = datetime.now(timezone.utc) - timedelta(seconds=30)

    llm_router = LLMProviderRouter(openai_api_key="", anthropic_api_key="")
    nlp_processor = SpacyNLPProcessor()
    embedding_service = SentenceTransformerEmbedding()

    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time)
    health = collector.collect_health()

    # Uptime should be approximately 30 seconds (allowing some variance)
    assert 25.0 < health.uptime_seconds < 35.0


def test_collect_health_checked_at_timestamp():
    """Test that checked_at timestamp is set to approximately now."""
    start_time = datetime.now(timezone.utc)

    llm_router = LLMProviderRouter(openai_api_key="", anthropic_api_key="")
    nlp_processor = SpacyNLPProcessor()
    embedding_service = SentenceTransformerEmbedding()

    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time)
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

    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time)

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

    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time)
    health = collector.collect_health()

    # Should have issues for missing providers and possibly embedding
    assert isinstance(health.issues, list)
    assert len(health.issues) > 0
    assert any("LLM" in issue for issue in health.issues)


def test_collect_health_database_always_connected():
    """Test that database_connected is always True when collector runs."""
    start_time = datetime.now(timezone.utc)

    llm_router = LLMProviderRouter(openai_api_key="", anthropic_api_key="")
    nlp_processor = SpacyNLPProcessor()
    embedding_service = SentenceTransformerEmbedding()

    collector = SystemMetricsCollector(llm_router, nlp_processor, embedding_service, start_time)
    health = collector.collect_health()

    # Database should always be "connected" if we got here
    # (actual DB checks would be implemented separately)
    assert health.database_connected is True
