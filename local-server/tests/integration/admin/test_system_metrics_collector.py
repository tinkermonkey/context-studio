"""
Integration tests for SystemMetricsCollector adapter.

Tests the adapter's ability to collect system metrics from protocol-typed
health-check components, without depending on concrete adapter types.
"""

import sys
import os
import time

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from sqlalchemy import create_engine, text
from adapters.metrics.system_collector import SystemMetricsCollector


class FakeHealthCheckableNLP:
    """Fake NLP component implementing HealthCheckableNLP protocol."""

    def __init__(self, is_ready: bool = True):
        self._is_ready = is_ready

    def is_ready(self) -> bool:
        return self._is_ready


class FakeHealthCheckableEmbedding:
    """Fake embedding component implementing HealthCheckableEmbedding protocol."""

    def __init__(self, is_loaded: bool = True):
        self._is_loaded = is_loaded

    def is_loaded(self) -> bool:
        return self._is_loaded


class FakeHealthCheckableLLM:
    """Fake LLM component implementing HealthCheckableLLM protocol."""

    def __init__(self, providers: list[str] | None = None):
        self._providers = providers or ["openai"]

    def list_available_providers(self) -> list[str]:
        return self._providers


def test_metrics_collector_with_protocol_types():
    """Test that SystemMetricsCollector accepts protocol-typed components."""
    # Create in-memory SQLite database for testing
    db_engine = create_engine("sqlite:///:memory:")

    # Create fake health-checkable components
    nlp = FakeHealthCheckableNLP(is_ready=True)
    embedding = FakeHealthCheckableEmbedding(is_loaded=True)
    llm = FakeHealthCheckableLLM(providers=["openai", "anthropic"])

    # Record start time as Unix timestamp
    start_time = time.time()

    # Create metrics collector with protocol types
    collector = SystemMetricsCollector(
        llm=llm,
        nlp=nlp,
        embedding=embedding,
        db_engine=db_engine,
        start_time=start_time,
    )

    # Verify collector was created
    assert collector is not None


def test_get_database_health_with_valid_engine():
    """Test database health check with valid connection."""
    db_engine = create_engine("sqlite:///:memory:")

    # Create a simple table to verify connectivity
    with db_engine.connect() as conn:
        conn.execute(text("CREATE TABLE test (id INTEGER)"))
        conn.commit()

    nlp = FakeHealthCheckableNLP()
    embedding = FakeHealthCheckableEmbedding()
    llm = FakeHealthCheckableLLM()
    start_time = time.time()

    collector = SystemMetricsCollector(
        llm=llm,
        nlp=nlp,
        embedding=embedding,
        db_engine=db_engine,
        start_time=start_time,
    )

    health = collector.get_database_health()
    assert health.connected is True
    assert len(health.issues) == 0


def test_get_service_metrics():
    """Test service metrics collection."""
    db_engine = create_engine("sqlite:///:memory:")

    nlp = FakeHealthCheckableNLP()
    embedding = FakeHealthCheckableEmbedding()
    llm = FakeHealthCheckableLLM(providers=["openai", "anthropic"])

    start_time = time.time()
    collector = SystemMetricsCollector(
        llm=llm,
        nlp=nlp,
        embedding=embedding,
        db_engine=db_engine,
        start_time=start_time,
    )

    # Small delay to ensure uptime is measurable
    time.sleep(0.01)

    metrics = collector.get_service_metrics()
    assert metrics.uptime_seconds >= 0.01
    assert metrics.llm_providers_available == ("openai", "anthropic")


def test_get_embedding_model_status_loaded():
    """Test embedding model status when loaded."""
    db_engine = create_engine("sqlite:///:memory:")

    nlp = FakeHealthCheckableNLP()
    embedding = FakeHealthCheckableEmbedding(is_loaded=True)
    llm = FakeHealthCheckableLLM()
    start_time = time.time()

    collector = SystemMetricsCollector(
        llm=llm,
        nlp=nlp,
        embedding=embedding,
        db_engine=db_engine,
        start_time=start_time,
    )

    status = collector.get_embedding_model_status()
    assert status.available is True
    assert "loaded" in status.details.lower()


def test_get_embedding_model_status_not_loaded():
    """Test embedding model status when not loaded."""
    db_engine = create_engine("sqlite:///:memory:")

    nlp = FakeHealthCheckableNLP()
    embedding = FakeHealthCheckableEmbedding(is_loaded=False)
    llm = FakeHealthCheckableLLM()
    start_time = time.time()

    collector = SystemMetricsCollector(
        llm=llm,
        nlp=nlp,
        embedding=embedding,
        db_engine=db_engine,
        start_time=start_time,
    )

    status = collector.get_embedding_model_status()
    assert status.available is False


def test_get_nlp_pipeline_status_ready():
    """Test NLP pipeline status when ready."""
    db_engine = create_engine("sqlite:///:memory:")

    nlp = FakeHealthCheckableNLP(is_ready=True)
    embedding = FakeHealthCheckableEmbedding()
    llm = FakeHealthCheckableLLM()
    start_time = time.time()

    collector = SystemMetricsCollector(
        llm=llm,
        nlp=nlp,
        embedding=embedding,
        db_engine=db_engine,
        start_time=start_time,
    )

    status = collector.get_nlp_pipeline_status()
    assert status.available is True
    assert "ready" in status.details.lower()


def test_get_nlp_pipeline_status_not_ready():
    """Test NLP pipeline status when not ready."""
    db_engine = create_engine("sqlite:///:memory:")

    nlp = FakeHealthCheckableNLP(is_ready=False)
    embedding = FakeHealthCheckableEmbedding()
    llm = FakeHealthCheckableLLM()
    start_time = time.time()

    collector = SystemMetricsCollector(
        llm=llm,
        nlp=nlp,
        embedding=embedding,
        db_engine=db_engine,
        start_time=start_time,
    )

    status = collector.get_nlp_pipeline_status()
    assert status.available is False


def test_get_background_task_summary():
    """Test background task summary (currently empty)."""
    db_engine = create_engine("sqlite:///:memory:")

    nlp = FakeHealthCheckableNLP()
    embedding = FakeHealthCheckableEmbedding()
    llm = FakeHealthCheckableLLM()
    start_time = time.time()

    collector = SystemMetricsCollector(
        llm=llm,
        nlp=nlp,
        embedding=embedding,
        db_engine=db_engine,
        start_time=start_time,
    )

    summary = collector.get_background_task_summary()
    assert summary.total == 0
    assert summary.by_status == {}


def test_health_check_exception_handling():
    """Test that exceptions in health checks are handled gracefully."""
    db_engine = create_engine("sqlite:///:memory:")

    # Create fakes that raise exceptions
    class FaultyNLP:
        def is_ready(self) -> bool:
            raise RuntimeError("NLP error")

    class FaultyEmbedding:
        def is_loaded(self) -> bool:
            raise RuntimeError("Embedding error")

    class FaultyLLM:
        def list_available_providers(self) -> list[str]:
            raise RuntimeError("LLM error")

    nlp = FaultyNLP()
    embedding = FaultyEmbedding()
    llm = FaultyLLM()
    start_time = time.time()

    collector = SystemMetricsCollector(
        llm=llm,
        nlp=nlp,
        embedding=embedding,
        db_engine=db_engine,
        start_time=start_time,
    )

    # Each should handle exceptions gracefully
    nlp_status = collector.get_nlp_pipeline_status()
    assert nlp_status.available is False
    assert "Error" in nlp_status.details

    embedding_status = collector.get_embedding_model_status()
    assert embedding_status.available is False
    assert "Error" in embedding_status.details

    # Service metrics should re-raise LLM error to allow caller to handle it
    with pytest.raises(RuntimeError, match="LLM error"):
        collector.get_service_metrics()
