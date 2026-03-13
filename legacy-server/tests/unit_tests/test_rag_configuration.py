"""
Unit tests for RAG pipeline configuration.

Tests configuration defaults, field types, and validation for RAGPipelineConfig.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from config import RAGPipelineConfig, Settings  # noqa: E402


def test_rag_config_defaults():
    """Test that RAGPipelineConfig has correct default values."""
    config = RAGPipelineConfig()

    # Knowledge graph settings
    assert config.kg_context_top_k == 50
    assert config.kg_vector_threshold == 0.6

    # LLM pipeline settings
    assert config.llm_pipeline_flavor is None
    assert config.llm_timeout == 30

    # Gap detection settings
    assert config.gap_detection_deps == []

    # Web search settings
    assert config.web_search_enabled is True
    assert config.web_search_max_attempts == 3
    assert config.web_search_rate_limit == 5
    assert config.web_search_max_per_session == 10

    # Observability settings
    assert config.enable_observability is True
    assert config.observability_retention_days == 30
    assert config.trace_retention_days == 7
    assert config.trace_max_data_size_kb == 100

    # Deduplication settings
    assert config.deduplication_threshold == 0.9

    # Extraction decision thresholds
    assert config.extraction_confidence_threshold == 0.7


def test_rag_config_field_types():
    """Test that RAGPipelineConfig fields have correct types."""
    config = RAGPipelineConfig()

    # Integer fields
    assert isinstance(config.kg_context_top_k, int)
    assert isinstance(config.llm_timeout, int)
    assert isinstance(config.web_search_max_attempts, int)
    assert isinstance(config.web_search_rate_limit, int)
    assert isinstance(config.web_search_max_per_session, int)
    assert isinstance(config.observability_retention_days, int)
    assert isinstance(config.trace_retention_days, int)
    assert isinstance(config.trace_max_data_size_kb, int)

    # Float fields
    assert isinstance(config.kg_vector_threshold, float)
    assert isinstance(config.deduplication_threshold, float)
    assert isinstance(config.extraction_confidence_threshold, float)

    # Boolean fields
    assert isinstance(config.web_search_enabled, bool)
    assert isinstance(config.enable_observability, bool)

    # List fields
    assert isinstance(config.gap_detection_deps, list)

    # Optional fields
    assert config.llm_pipeline_flavor is None or isinstance(
        config.llm_pipeline_flavor, str
    )


def test_rag_config_kg_context_top_k_validation():
    """Test kg_context_top_k field validation."""
    # Valid values
    valid_values = [1, 50, 100, 500, 1000]
    for value in valid_values:
        config = RAGPipelineConfig(kg_context_top_k=value)
        assert config.kg_context_top_k == value

    # Invalid values (below minimum)
    invalid_values = [0, -1, -10]
    for value in invalid_values:
        with pytest.raises(ValidationError):
            RAGPipelineConfig(kg_context_top_k=value)

    # Invalid values (above maximum)
    with pytest.raises(ValidationError):
        RAGPipelineConfig(kg_context_top_k=1001)


def test_rag_config_kg_vector_threshold_validation():
    """Test kg_vector_threshold field validation."""
    # Valid values
    valid_values = [0.0, 0.5, 0.7, 0.9, 1.0]
    for value in valid_values:
        config = RAGPipelineConfig(kg_vector_threshold=value)
        assert config.kg_vector_threshold == value

    # Invalid values
    invalid_values = [-0.1, -1.0, 1.1, 2.0]
    for value in invalid_values:
        with pytest.raises(ValidationError):
            RAGPipelineConfig(kg_vector_threshold=value)


def test_rag_config_llm_timeout_validation():
    """Test llm_timeout field validation."""
    # Valid values
    valid_values = [1, 30, 60, 120, 300]
    for value in valid_values:
        config = RAGPipelineConfig(llm_timeout=value)
        assert config.llm_timeout == value

    # Invalid values
    invalid_values = [0, -1, 301, 400]
    for value in invalid_values:
        with pytest.raises(ValidationError):
            RAGPipelineConfig(llm_timeout=value)


def test_rag_config_web_search_validation():
    """Test web search field validation."""
    # Valid max_attempts
    config = RAGPipelineConfig(web_search_max_attempts=5)
    assert config.web_search_max_attempts == 5

    # Invalid max_attempts
    with pytest.raises(ValidationError):
        RAGPipelineConfig(web_search_max_attempts=0)
    with pytest.raises(ValidationError):
        RAGPipelineConfig(web_search_max_attempts=11)

    # Valid rate_limit
    config = RAGPipelineConfig(web_search_rate_limit=10)
    assert config.web_search_rate_limit == 10

    # Invalid rate_limit
    with pytest.raises(ValidationError):
        RAGPipelineConfig(web_search_rate_limit=0)


def test_rag_config_observability_validation():
    """Test observability field validation."""
    # Valid retention days
    config = RAGPipelineConfig(observability_retention_days=60, trace_retention_days=14)
    assert config.observability_retention_days == 60
    assert config.trace_retention_days == 14

    # Invalid retention days
    with pytest.raises(ValidationError):
        RAGPipelineConfig(observability_retention_days=0)
    with pytest.raises(ValidationError):
        RAGPipelineConfig(observability_retention_days=366)
    with pytest.raises(ValidationError):
        RAGPipelineConfig(trace_retention_days=0)
    with pytest.raises(ValidationError):
        RAGPipelineConfig(trace_retention_days=91)


def test_rag_config_deduplication_threshold_validation():
    """Test deduplication_threshold field validation."""
    # Valid values
    valid_values = [0.0, 0.5, 0.9, 1.0]
    for value in valid_values:
        config = RAGPipelineConfig(deduplication_threshold=value)
        assert config.deduplication_threshold == value

    # Invalid values
    invalid_values = [-0.1, 1.1, 2.0]
    for value in invalid_values:
        with pytest.raises(ValidationError):
            RAGPipelineConfig(deduplication_threshold=value)


def test_rag_config_extraction_confidence_threshold_validation():
    """Test extraction_confidence_threshold field validation."""
    # Valid values
    valid_values = [0.0, 0.5, 0.7, 1.0]
    for value in valid_values:
        config = RAGPipelineConfig(extraction_confidence_threshold=value)
        assert config.extraction_confidence_threshold == value

    # Invalid values
    invalid_values = [-0.1, 1.1, 2.0]
    for value in invalid_values:
        with pytest.raises(ValidationError):
            RAGPipelineConfig(extraction_confidence_threshold=value)


def test_rag_config_in_settings():
    """Test that RAGPipelineConfig is properly integrated into Settings."""
    settings = Settings()

    # Check that rag_pipeline section exists
    assert hasattr(settings, "rag_pipeline")
    assert isinstance(settings.rag_pipeline, RAGPipelineConfig)

    # Check default values through Settings
    assert settings.rag_pipeline.kg_context_top_k == 50
    assert settings.rag_pipeline.enable_observability is True
    assert settings.rag_pipeline.web_search_rate_limit == 5


def test_rag_config_field_descriptions():
    """Test that all RAGPipelineConfig fields have descriptions."""
    model_fields = RAGPipelineConfig.model_fields

    required_fields = [
        "kg_context_top_k",
        "kg_vector_threshold",
        "llm_pipeline_flavor",
        "llm_timeout",
        "gap_detection_deps",
        "web_search_enabled",
        "web_search_max_attempts",
        "web_search_rate_limit",
        "web_search_max_per_session",
        "enable_observability",
        "observability_retention_days",
        "trace_retention_days",
        "trace_max_data_size_kb",
        "deduplication_threshold",
        "extraction_confidence_threshold",
    ]

    for field_name in required_fields:
        assert field_name in model_fields, f"Field {field_name} not found in model"
        field_info = model_fields[field_name]
        assert (
            field_info.description is not None
        ), f"Field {field_name} has no description"
        assert (
            len(field_info.description) > 0
        ), f"Field {field_name} has empty description"


def test_rag_config_custom_values():
    """Test creating RAGPipelineConfig with custom values."""
    config = RAGPipelineConfig(
        kg_context_top_k=100,
        kg_vector_threshold=0.8,
        llm_pipeline_flavor="custom-flavor",
        llm_timeout=60,
        gap_detection_deps=["dep1", "dep2"],
        web_search_enabled=False,
        web_search_max_attempts=5,
        web_search_rate_limit=10,
        web_search_max_per_session=20,
        enable_observability=False,
        observability_retention_days=60,
        trace_retention_days=14,
        trace_max_data_size_kb=200,
        deduplication_threshold=0.95,
        extraction_confidence_threshold=0.8,
    )

    assert config.kg_context_top_k == 100
    assert config.kg_vector_threshold == 0.8
    assert config.llm_pipeline_flavor == "custom-flavor"
    assert config.llm_timeout == 60
    assert config.gap_detection_deps == ["dep1", "dep2"]
    assert config.web_search_enabled is False
    assert config.web_search_max_attempts == 5
    assert config.web_search_rate_limit == 10
    assert config.web_search_max_per_session == 20
    assert config.enable_observability is False
    assert config.observability_retention_days == 60
    assert config.trace_retention_days == 14
    assert config.trace_max_data_size_kb == 200
    assert config.deduplication_threshold == 0.95
    assert config.extraction_confidence_threshold == 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
