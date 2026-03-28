"""
Unit tests for pipeline domain entities.

Tests cover entity construction, field initialization, and dataclass behavior
for PipelineConfiguration and Execution.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from datetime import datetime, timezone

from domain.pipeline.entities import PipelineConfiguration, Execution


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
    """Tests for PipelineConfiguration dataclass."""

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


class TestExecution:
    """Tests for Execution dataclass."""

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
