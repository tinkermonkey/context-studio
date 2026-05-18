"""
Unit tests for pipeline domain entities.

Tests cover entity construction, field initialization, and dataclass behavior
for PipelineConfiguration and Execution.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime, timezone

import pytest

from domain.pipeline.entities import Execution, PipelineConfiguration


@pytest.fixture
def make_config():
    """Factory fixture for PipelineConfiguration with sensible defaults."""

    def _make(**overrides):
        now = datetime.now(timezone.utc)
        defaults = {
            "id": "config-default",
            "pipeline": "test-pipeline",
            "title": "Test Pipeline",
            "provider": "openai",
            "model": "gpt-4",
            "config": {},
            "system_prompt": "You are a helpful assistant.",
            "user_prompt": "Process: {text}",
            "version": 1,
            "enabled": True,
            "created_at": now,
            "last_updated": now,
        }
        defaults.update(overrides)
        return PipelineConfiguration(**defaults)

    return _make


@pytest.fixture
def make_execution():
    """Factory fixture for Execution with sensible defaults."""

    def _make(**overrides):
        now = datetime.now(timezone.utc)
        defaults = {
            "id": "exec-default",
            "pipeline_config_id": "config-default",
            "input_text": "Test input",
            "output_text": "Test output",
            "provider": "openai",
            "model": "gpt-4",
            "tokens_in": 10,
            "tokens_out": 10,
            "duration_ms": 100,
            "status": "success",
            "error_message": None,
            "timestamp": now,
        }
        defaults.update(overrides)
        return Execution(**defaults)

    return _make


class TestPipelineConfiguration:
    """Tests for PipelineConfiguration dataclass and validation."""

    def test_construct_with_all_fields(self, make_config):
        """Create a PipelineConfiguration with all fields."""
        config = make_config(
            id="config-123",
            pipeline="document-extractor",
            title="Extract Key Information",
            provider="openai",
            model="gpt-4",
            config={"timeout": 30, "temperature": 0.0, "max_tokens": 2000},
            system_prompt="You are a helpful assistant.",
            user_prompt="Extract key information from: {text}",
            version=2,
            enabled=True,
        )

        assert config.id == "config-123"
        assert config.pipeline == "document-extractor"
        assert config.title == "Extract Key Information"
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.config == {"timeout": 30, "temperature": 0.0, "max_tokens": 2000}
        assert config.system_prompt == "You are a helpful assistant."
        assert config.user_prompt == "Extract key information from: {text}"
        assert config.version == 2
        assert config.enabled is True

    def test_construct_with_minimal_fields(self, make_config):
        """Create a PipelineConfiguration with default fields."""
        config = make_config(
            id="config-456",
            pipeline="ner",
            title="Named Entity Recognition",
            provider="anthropic",
            model="claude-opus",
        )

        assert config.id == "config-456"
        assert config.pipeline == "ner"
        assert config.title == "Named Entity Recognition"

    def test_pipeline_configuration_config_is_mutable_dict(self, make_config):
        """PipelineConfiguration config dict can be modified."""
        config = make_config(config={"timeout": 30})
        config.config["temperature"] = 0.5
        assert config.config["temperature"] == 0.5

    def test_pipeline_configuration_with_empty_config(self, make_config):
        """PipelineConfiguration can have empty config dict."""
        config = make_config(config={})
        assert config.config == {}

    def test_pipeline_configuration_config_dict_isolation(self, make_config):
        """PipelineConfiguration config dicts don't share state across instances."""
        config1 = make_config(config={"timeout": 30})
        config2 = make_config(config={})

        config1.config["temperature"] = 0.5
        assert "temperature" not in config2.config
        assert config2.config == {}

    def test_pipeline_configuration_invalid_provider(self, make_config):
        """PipelineConfiguration raises ValueError for invalid provider."""
        with pytest.raises(ValueError, match="provider must be"):
            make_config(provider="invalid_provider")

    def test_pipeline_configuration_invalid_provider_lowercase(self, make_config):
        """PipelineConfiguration raises ValueError for unrecognized provider."""
        with pytest.raises(ValueError, match="provider must be"):
            make_config(provider="claude")

    def test_pipeline_configuration_valid_provider_openai(self, make_config):
        """PipelineConfiguration accepts provider='openai'."""
        config = make_config(provider="openai")
        assert config.provider == "openai"

    def test_pipeline_configuration_valid_provider_anthropic(self, make_config):
        """PipelineConfiguration accepts provider='anthropic'."""
        config = make_config(provider="anthropic")
        assert config.provider == "anthropic"

    def test_pipeline_configuration_invalid_version_zero(self, make_config):
        """PipelineConfiguration raises ValueError if version is 0."""
        with pytest.raises(ValueError, match="version must be >= 1"):
            make_config(version=0)

    def test_pipeline_configuration_invalid_version_negative(self, make_config):
        """PipelineConfiguration raises ValueError if version is negative."""
        with pytest.raises(ValueError, match="version must be >= 1"):
            make_config(version=-1)

    def test_pipeline_configuration_valid_version_one(self, make_config):
        """PipelineConfiguration accepts version=1."""
        config = make_config(version=1)
        assert config.version == 1

    def test_pipeline_configuration_valid_version_high(self, make_config):
        """PipelineConfiguration accepts high version numbers."""
        config = make_config(version=100)
        assert config.version == 100

    def test_pipeline_configuration_seed_none_is_accepted(self, make_config):
        """PipelineConfiguration accepts seed=None."""
        config = make_config(seed=None)
        assert config.seed is None

    def test_pipeline_configuration_seed_zero_is_accepted(self, make_config):
        """PipelineConfiguration accepts seed=0."""
        config = make_config(seed=0)
        assert config.seed == 0

    def test_pipeline_configuration_seed_positive_is_accepted(self, make_config):
        """PipelineConfiguration accepts positive seed values."""
        config = make_config(seed=42)
        assert config.seed == 42

    def test_pipeline_configuration_seed_negative_is_rejected(self, make_config):
        """PipelineConfiguration rejects negative seed values."""
        with pytest.raises(ValueError, match="seed must be non-negative"):
            make_config(seed=-1)


class TestExecution:
    """Tests for Execution dataclass and validation."""

    def test_construct_with_all_fields(self, make_execution):
        """Create an Execution with all fields."""
        execution = make_execution(
            id="exec-123",
            pipeline_config_id="config-123",
            input_text="Sample input text",
            output_text="Generated output",
            provider="openai",
            model="gpt-4",
            tokens_in=45,
            tokens_out=120,
            duration_ms=523,
            status="success",
        )

        assert execution.id == "exec-123"
        assert execution.pipeline_config_id == "config-123"
        assert execution.input_text == "Sample input text"
        assert execution.output_text == "Generated output"
        assert execution.provider == "openai"
        assert execution.model == "gpt-4"
        assert execution.tokens_in == 45
        assert execution.tokens_out == 120
        assert execution.duration_ms == 523
        assert execution.status == "success"
        assert execution.error_message is None

    def test_execution_with_error_status(self, make_execution):
        """Create an Execution with error status."""
        execution = make_execution(
            status="error",
            error_message="LLM service unavailable",
            output_text="",
            tokens_in=0,
            tokens_out=0,
        )

        assert execution.status == "error"
        assert execution.error_message == "LLM service unavailable"
        assert execution.output_text == ""

    def test_execution_with_timeout_status(self, make_execution):
        """Create an Execution with timeout status."""
        execution = make_execution(
            status="timeout",
            error_message="Execution exceeded timeout of 30 seconds",
            output_text="",
            duration_ms=30000,
        )

        assert execution.status == "timeout"
        assert "exceeded timeout" in execution.error_message

    def test_execution_different_providers(self, make_execution):
        """Execution supports different provider/model combinations."""
        openai_exec = make_execution(
            provider="openai",
            model="gpt-4",
        )

        anthropic_exec = make_execution(
            provider="anthropic",
            model="claude-opus",
        )

        assert openai_exec.provider == "openai"
        assert openai_exec.model == "gpt-4"
        assert anthropic_exec.provider == "anthropic"
        assert anthropic_exec.model == "claude-opus"

    def test_execution_invalid_status(self, make_execution):
        """Execution raises ValueError for invalid status."""
        with pytest.raises(ValueError, match="status must be"):
            make_execution(status="invalid_status")

    def test_execution_invalid_status_failed(self, make_execution):
        """Execution raises ValueError for 'failed' status."""
        with pytest.raises(ValueError, match="status must be"):
            make_execution(status="failed")

    def test_execution_valid_status_success(self, make_execution):
        """Execution accepts status='success'."""
        execution = make_execution(status="success")
        assert execution.status == "success"

    def test_execution_valid_status_error(self, make_execution):
        """Execution accepts status='error'."""
        execution = make_execution(status="error", error_message="Test error")
        assert execution.status == "error"

    def test_execution_valid_status_timeout(self, make_execution):
        """Execution accepts status='timeout'."""
        execution = make_execution(status="timeout", error_message="Timed out")
        assert execution.status == "timeout"

    def test_execution_error_status_without_message_raises(self, make_execution):
        """Execution raises ValueError if status='error' but error_message is None."""
        with pytest.raises(ValueError, match="error_message must be set when status is 'error'"):
            make_execution(status="error", error_message=None)

    def test_execution_error_status_with_empty_message_raises(self, make_execution):
        """Execution raises ValueError if status='error' with empty error_message."""
        with pytest.raises(ValueError, match="error_message must be set when status is 'error'"):
            make_execution(status="error", error_message="")

    def test_execution_timeout_status_without_message_allowed(self, make_execution):
        """Execution allows status='timeout' without error_message."""
        execution = make_execution(status="timeout", error_message=None)
        assert execution.status == "timeout"
        assert execution.error_message is None

    def test_execution_success_status_with_message_allowed(self, make_execution):
        """Execution allows error_message for status='success' (just ignored)."""
        execution = make_execution(status="success", error_message="Not used")
        assert execution.status == "success"

    def test_execution_invalid_negative_tokens_in(self, make_execution):
        """Execution raises ValueError if tokens_in is negative."""
        with pytest.raises(ValueError, match="tokens_in must be non-negative"):
            make_execution(tokens_in=-1)

    def test_execution_invalid_negative_tokens_out(self, make_execution):
        """Execution raises ValueError if tokens_out is negative."""
        with pytest.raises(ValueError, match="tokens_out must be non-negative"):
            make_execution(tokens_out=-1)

    def test_execution_invalid_negative_duration(self, make_execution):
        """Execution raises ValueError if duration_ms is negative."""
        with pytest.raises(ValueError, match="duration_ms must be non-negative"):
            make_execution(duration_ms=-1)

    def test_execution_valid_zero_tokens_and_duration(self, make_execution):
        """Execution accepts zero tokens and duration."""
        execution = make_execution(tokens_in=0, tokens_out=0, duration_ms=0)
        assert execution.tokens_in == 0
        assert execution.tokens_out == 0
        assert execution.duration_ms == 0

    def test_execution_valid_positive_tokens_and_duration(self, make_execution):
        """Execution accepts positive tokens and duration."""
        execution = make_execution(tokens_in=100, tokens_out=200, duration_ms=5000)
        assert execution.tokens_in == 100
        assert execution.tokens_out == 200
        assert execution.duration_ms == 5000
