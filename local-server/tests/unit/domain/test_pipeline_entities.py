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


class TestPipelineConfiguration:
    """Tests for PipelineConfiguration dataclass."""

    def test_construct_with_all_fields(self):
        """Create a PipelineConfiguration with all fields."""
        now = datetime.now(timezone.utc)

        config = PipelineConfiguration(
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
            created_at=now,
            last_updated=now,
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
        assert config.created_at == now
        assert config.last_updated == now

    def test_construct_with_minimal_fields(self):
        """Create a PipelineConfiguration with required fields only."""
        now = datetime.now(timezone.utc)

        config = PipelineConfiguration(
            id="config-456",
            pipeline="ner",
            title="Named Entity Recognition",
            provider="anthropic",
            model="claude-opus",
            config={},
            system_prompt="Extract entities.",
            user_prompt="Process: {text}",
            version=1,
            enabled=True,
            created_at=now,
            last_updated=now,
        )

        assert config.id == "config-456"
        assert config.pipeline == "ner"
        assert config.title == "Named Entity Recognition"

    def test_pipeline_configuration_config_is_mutable_dict(self):
        """PipelineConfiguration config dict can be modified."""
        now = datetime.now(timezone.utc)
        config = PipelineConfiguration(
            id="id",
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={"timeout": 30},
            system_prompt="System",
            user_prompt="User: {text}",
            version=1,
            enabled=True,
            created_at=now,
            last_updated=now,
        )

        config.config["temperature"] = 0.5
        assert config.config["temperature"] == 0.5

    def test_pipeline_configuration_with_empty_config(self):
        """PipelineConfiguration can have empty config dict."""
        now = datetime.now(timezone.utc)
        config = PipelineConfiguration(
            id="id",
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
            version=1,
            enabled=True,
            created_at=now,
            last_updated=now,
        )

        assert config.config == {}

    def test_pipeline_configuration_enabled_flag(self):
        """PipelineConfiguration tracks enabled/disabled state."""
        now = datetime.now(timezone.utc)
        enabled_config = PipelineConfiguration(
            id="id1",
            pipeline="test",
            title="Enabled",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
            version=1,
            enabled=True,
            created_at=now,
            last_updated=now,
        )

        disabled_config = PipelineConfiguration(
            id="id2",
            pipeline="test",
            title="Disabled",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
            version=1,
            enabled=False,
            created_at=now,
            last_updated=now,
        )

        assert enabled_config.enabled is True
        assert disabled_config.enabled is False

    def test_pipeline_configuration_version_tracking(self):
        """PipelineConfiguration tracks version number."""
        now = datetime.now(timezone.utc)
        v1 = PipelineConfiguration(
            id="id",
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
            version=1,
            enabled=True,
            created_at=now,
            last_updated=now,
        )

        v2 = PipelineConfiguration(
            id="id",
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4-turbo",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
            version=2,
            enabled=True,
            created_at=now,
            last_updated=now,
        )

        assert v1.version == 1
        assert v2.version == 2

    def test_pipeline_configuration_timestamps(self):
        """PipelineConfiguration tracks creation and update timestamps."""
        created = datetime.now(timezone.utc)
        updated = datetime.now(timezone.utc)

        config = PipelineConfiguration(
            id="id",
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
            version=1,
            enabled=True,
            created_at=created,
            last_updated=updated,
        )

        assert config.created_at == created
        assert config.last_updated == updated


class TestExecution:
    """Tests for Execution dataclass."""

    def test_construct_with_all_fields(self):
        """Create an Execution with all fields."""
        now = datetime.now(timezone.utc)

        execution = Execution(
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
            error_message=None,
            timestamp=now,
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
        assert execution.timestamp == now

    def test_execution_with_error_status(self):
        """Create an Execution with error status."""
        now = datetime.now(timezone.utc)

        execution = Execution(
            id="exec-456",
            pipeline_config_id="config-123",
            input_text="Input",
            output_text="",
            provider="openai",
            model="gpt-4",
            tokens_in=0,
            tokens_out=0,
            duration_ms=150,
            status="error",
            error_message="LLM service unavailable",
            timestamp=now,
        )

        assert execution.status == "error"
        assert execution.error_message == "LLM service unavailable"
        assert execution.output_text == ""

    def test_execution_with_timeout_status(self):
        """Create an Execution with timeout status."""
        now = datetime.now(timezone.utc)

        execution = Execution(
            id="exec-789",
            pipeline_config_id="config-123",
            input_text="Input",
            output_text="",
            provider="openai",
            model="gpt-4",
            tokens_in=0,
            tokens_out=0,
            duration_ms=30000,
            status="timeout",
            error_message="Execution exceeded timeout of 30 seconds",
            timestamp=now,
        )

        assert execution.status == "timeout"
        assert "exceeded timeout" in execution.error_message

    def test_execution_tracks_token_counts(self):
        """Execution tracks input and output token counts."""
        now = datetime.now(timezone.utc)

        # Low token count
        exec1 = Execution(
            id="e1",
            pipeline_config_id="c1",
            input_text="Hi",
            output_text="Hello",
            provider="openai",
            model="gpt-4",
            tokens_in=1,
            tokens_out=1,
            duration_ms=10,
            status="success",
            error_message=None,
            timestamp=now,
        )

        # High token count
        exec2 = Execution(
            id="e2",
            pipeline_config_id="c1",
            input_text="Long input " * 100,
            output_text="Long output " * 200,
            provider="openai",
            model="gpt-4",
            tokens_in=200,
            tokens_out=500,
            duration_ms=1500,
            status="success",
            error_message=None,
            timestamp=now,
        )

        assert exec1.tokens_in == 1
        assert exec1.tokens_out == 1
        assert exec2.tokens_in == 200
        assert exec2.tokens_out == 500

    def test_execution_duration_tracking(self):
        """Execution tracks execution duration in milliseconds."""
        now = datetime.now(timezone.utc)

        # Fast execution
        fast = Execution(
            id="fast",
            pipeline_config_id="config",
            input_text="Input",
            output_text="Output",
            provider="openai",
            model="gpt-4",
            tokens_in=10,
            tokens_out=10,
            duration_ms=50,
            status="success",
            error_message=None,
            timestamp=now,
        )

        # Slow execution
        slow = Execution(
            id="slow",
            pipeline_config_id="config",
            input_text="Input",
            output_text="Output",
            provider="openai",
            model="gpt-4",
            tokens_in=10,
            tokens_out=10,
            duration_ms=5000,
            status="success",
            error_message=None,
            timestamp=now,
        )

        assert fast.duration_ms == 50
        assert slow.duration_ms == 5000

    def test_execution_provider_and_model_fields(self):
        """Execution tracks provider and model information."""
        now = datetime.now(timezone.utc)

        openai_exec = Execution(
            id="e1",
            pipeline_config_id="c1",
            input_text="Input",
            output_text="Output",
            provider="openai",
            model="gpt-4",
            tokens_in=10,
            tokens_out=10,
            duration_ms=100,
            status="success",
            error_message=None,
            timestamp=now,
        )

        anthropic_exec = Execution(
            id="e2",
            pipeline_config_id="c1",
            input_text="Input",
            output_text="Output",
            provider="anthropic",
            model="claude-opus",
            tokens_in=10,
            tokens_out=10,
            duration_ms=100,
            status="success",
            error_message=None,
            timestamp=now,
        )

        assert openai_exec.provider == "openai"
        assert openai_exec.model == "gpt-4"
        assert anthropic_exec.provider == "anthropic"
        assert anthropic_exec.model == "claude-opus"

    def test_execution_timestamp(self):
        """Execution records execution timestamp."""
        now = datetime.now(timezone.utc)

        execution = Execution(
            id="id",
            pipeline_config_id="config",
            input_text="Input",
            output_text="Output",
            provider="openai",
            model="gpt-4",
            tokens_in=10,
            tokens_out=10,
            duration_ms=100,
            status="success",
            error_message=None,
            timestamp=now,
        )

        assert execution.timestamp == now
