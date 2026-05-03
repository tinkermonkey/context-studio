"""
Integration tests for SQLitePipelineRepository.

Tests the repository implementation against an in-memory SQLite database,
verifying CRUD operations, querying, and data round-tripping.
"""

import sys
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure local-server root is in path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from domain.pipeline.entities import PipelineConfiguration, Execution
from adapters.persistence.sqlite.operations.models import (
    OperationsBase,
)
from adapters.persistence.sqlite.pipeline_repo import SQLitePipelineRepository


@pytest.fixture
def session_factory():
    """Create an in-memory SQLite database with schema for testing."""
    engine = create_engine("sqlite:///:memory:")
    OperationsBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    return factory


@pytest.fixture
def repo(session_factory):
    """Create a SQLitePipelineRepository instance for testing."""
    return SQLitePipelineRepository(session_factory)


@pytest.fixture
def sample_config():
    """Create a sample PipelineConfiguration for testing."""
    config_id = str(uuid4())
    return PipelineConfiguration(
        id=config_id,
        pipeline="summarization",
        title="Abstractive Summarizer",
        provider="openai",
        model="gpt-4",
        config={"temperature": 0.5, "max_tokens": 2000},
        system_prompt="You are a professional summarizer.",
        user_prompt="Summarize the following text:\n{text}",
        version=1,
        enabled=True,
        created_at=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_execution(sample_config):
    """Create a sample Execution for testing."""
    return Execution(
        id=str(uuid4()),
        pipeline_config_id=sample_config.id,
        input_text="This is a long document that needs summarization.",
        output_text="A concise summary of the document.",
        provider="openai",
        model="gpt-4",
        tokens_in=15,
        tokens_out=8,
        duration_ms=1250,
        status="success",
        error_message=None,
        timestamp=datetime.now(timezone.utc),
    )


class TestPipelineRepositoryConfigCRUD:
    """Test CRUD operations for pipeline configurations."""

    def test_save_config_creates_new_record(self, repo, sample_config):
        """Test that save_config creates a new configuration record."""
        result = repo.save_config(sample_config)

        assert result.id == sample_config.id
        assert result.title == sample_config.title

        # Verify it was persisted
        retrieved = repo.get_config(sample_config.id)
        assert retrieved is not None
        assert retrieved.id == sample_config.id

    def test_get_config_returns_all_fields(self, repo, sample_config):
        """Test that get_config returns a configuration with all fields intact."""
        repo.save_config(sample_config)
        retrieved = repo.get_config(sample_config.id)

        assert retrieved is not None
        assert retrieved.id == sample_config.id
        assert retrieved.pipeline == sample_config.pipeline
        assert retrieved.title == sample_config.title
        assert retrieved.provider == sample_config.provider
        assert retrieved.model == sample_config.model
        assert retrieved.config == sample_config.config
        assert retrieved.system_prompt == sample_config.system_prompt
        assert retrieved.user_prompt == sample_config.user_prompt
        assert retrieved.version == sample_config.version
        assert retrieved.enabled == sample_config.enabled
        # Compare timestamps without timezone (SQLite doesn't preserve tz info)
        assert retrieved.created_at.replace(
            tzinfo=None
        ) == sample_config.created_at.replace(tzinfo=None)
        assert retrieved.last_updated.replace(
            tzinfo=None
        ) == sample_config.last_updated.replace(tzinfo=None)

    def test_get_config_returns_none_for_missing_id(self, repo):
        """Test that get_config returns None for non-existent ID."""
        result = repo.get_config("non-existent-id")
        assert result is None

    def test_save_config_updates_existing_record(self, repo, sample_config):
        """Test that save_config updates an existing configuration."""
        repo.save_config(sample_config)

        # Modify and save again
        sample_config.title = "Updated Summarizer"
        sample_config.version = 2
        sample_config.enabled = False
        repo.save_config(sample_config)

        retrieved = repo.get_config(sample_config.id)
        assert retrieved is not None
        assert retrieved.title == "Updated Summarizer"
        assert retrieved.version == 2
        assert retrieved.enabled is False

    def test_delete_config_removes_record(self, repo, sample_config):
        """Test that delete_config removes a configuration."""
        repo.save_config(sample_config)
        assert repo.get_config(sample_config.id) is not None

        result = repo.delete_config(sample_config.id)
        assert result is True
        assert repo.get_config(sample_config.id) is None

    def test_delete_config_returns_false_for_missing_id(self, repo):
        """Test that delete_config returns False for non-existent ID."""
        result = repo.delete_config("non-existent-id")
        assert result is False

    def test_list_configs_returns_all_configurations(self, repo, sample_config):
        """Test that list_configs returns all saved configurations."""
        config1 = sample_config
        config2 = PipelineConfiguration(
            id=str(uuid4()),
            pipeline="translation",
            title="English to Spanish Translator",
            provider="anthropic",
            model="claude-opus",
            config={"temperature": 0.2},
            system_prompt="You are a translator.",
            user_prompt="Translate to Spanish:\n{text}",
            version=1,
            enabled=True,
            created_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )

        repo.save_config(config1)
        repo.save_config(config2)

        configs = repo.list_configs()
        assert len(configs) == 2
        ids = {c.id for c in configs}
        assert config1.id in ids
        assert config2.id in ids

    def test_list_configs_with_enabled_only_filter(self, repo, sample_config):
        """Test that list_configs(enabled_only=True) excludes disabled configs."""
        config1 = sample_config  # enabled=True
        config2 = PipelineConfiguration(
            id=str(uuid4()),
            pipeline="disabled_pipeline",
            title="Disabled Config",
            provider="openai",
            model="gpt-3.5-turbo",
            config={},
            system_prompt="System prompt",
            user_prompt="User prompt {text}",
            version=1,
            enabled=False,
            created_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )

        repo.save_config(config1)
        repo.save_config(config2)

        all_configs = repo.list_configs(enabled_only=False)
        enabled_configs = repo.list_configs(enabled_only=True)

        assert len(all_configs) == 2
        assert len(enabled_configs) == 1
        assert enabled_configs[0].id == config1.id
        assert enabled_configs[0].enabled is True


class TestPipelineRepositoryExecutionTracking:
    """Test execution recording and retrieval."""

    def test_record_execution_creates_record(self, repo, sample_execution):
        """Test that record_execution creates a new execution record."""
        result = repo.record_execution(sample_execution)

        assert result.id == sample_execution.id
        assert result.status == "success"

    def test_get_executions_returns_ordered_results(self, repo, sample_config):
        """Test that get_executions returns results in reverse chronological order."""
        from datetime import timedelta

        # Create multiple executions with different timestamps
        base_time = datetime.now(timezone.utc)

        exec1 = Execution(
            id=str(uuid4()),
            pipeline_config_id=sample_config.id,
            input_text="Input 1",
            output_text="Output 1",
            provider="openai",
            model="gpt-4",
            tokens_in=10,
            tokens_out=5,
            duration_ms=1000,
            status="success",
            error_message=None,
            timestamp=base_time,
        )

        exec2 = Execution(
            id=str(uuid4()),
            pipeline_config_id=sample_config.id,
            input_text="Input 2",
            output_text="Output 2",
            provider="openai",
            model="gpt-4",
            tokens_in=15,
            tokens_out=8,
            duration_ms=1500,
            status="success",
            error_message=None,
            timestamp=base_time + timedelta(seconds=10),
        )

        repo.record_execution(exec1)
        repo.record_execution(exec2)

        executions = repo.get_executions(sample_config.id)

        assert len(executions) == 2
        # Most recent first
        assert executions[0].id == exec2.id
        assert executions[1].id == exec1.id

    def test_get_executions_respects_limit(self, repo, sample_config):
        """Test that get_executions respects the limit parameter."""
        from datetime import timedelta

        base_time = datetime.now(timezone.utc)

        # Create 15 executions
        for i in range(15):
            exec_record = Execution(
                id=str(uuid4()),
                pipeline_config_id=sample_config.id,
                input_text=f"Input {i}",
                output_text=f"Output {i}",
                provider="openai",
                model="gpt-4",
                tokens_in=10 + i,
                tokens_out=5 + i,
                duration_ms=1000 + i * 10,
                status="success",
                error_message=None,
                timestamp=base_time + timedelta(seconds=i),
            )
            repo.record_execution(exec_record)

        # Default limit (50) should return all
        executions = repo.get_executions(sample_config.id)
        assert len(executions) == 15

        # Custom limit should be respected
        limited_executions = repo.get_executions(sample_config.id, limit=10)
        assert len(limited_executions) == 10

    def test_get_executions_filters_by_config_id(self, repo):
        """Test that get_executions only returns executions for the specified config."""
        config1_id = str(uuid4())
        config2_id = str(uuid4())
        base_time = datetime.now(timezone.utc)

        exec1 = Execution(
            id=str(uuid4()),
            pipeline_config_id=config1_id,
            input_text="Config 1 input",
            output_text="Config 1 output",
            provider="openai",
            model="gpt-4",
            tokens_in=10,
            tokens_out=5,
            duration_ms=1000,
            status="success",
            error_message=None,
            timestamp=base_time,
        )

        exec2 = Execution(
            id=str(uuid4()),
            pipeline_config_id=config2_id,
            input_text="Config 2 input",
            output_text="Config 2 output",
            provider="openai",
            model="gpt-4",
            tokens_in=12,
            tokens_out=6,
            duration_ms=1200,
            status="success",
            error_message=None,
            timestamp=base_time,
        )

        repo.record_execution(exec1)
        repo.record_execution(exec2)

        config1_executions = repo.get_executions(config1_id)
        config2_executions = repo.get_executions(config2_id)

        assert len(config1_executions) == 1
        assert len(config2_executions) == 1
        assert config1_executions[0].pipeline_config_id == config1_id
        assert config2_executions[0].pipeline_config_id == config2_id

    def test_execution_with_error_stores_error_message(self, repo, sample_config):
        """Test that execution errors are properly recorded and retrieved."""
        exec_record = Execution(
            id=str(uuid4()),
            pipeline_config_id=sample_config.id,
            input_text="Input text",
            output_text="",
            provider="openai",
            model="gpt-4",
            tokens_in=10,
            tokens_out=0,
            duration_ms=5000,
            status="error",
            error_message="API rate limit exceeded",
            timestamp=datetime.now(timezone.utc),
        )

        repo.record_execution(exec_record)
        retrieved_executions = repo.get_executions(sample_config.id)

        assert len(retrieved_executions) == 1
        assert retrieved_executions[0].status == "error"
        assert retrieved_executions[0].error_message == "API rate limit exceeded"

    def test_execution_round_trip_preserves_all_fields(self, repo, sample_execution):
        """Test that all execution fields are preserved through save and retrieve."""
        repo.record_execution(sample_execution)
        executions = repo.get_executions(sample_execution.pipeline_config_id)

        assert len(executions) == 1
        retrieved = executions[0]

        assert retrieved.id == sample_execution.id
        assert retrieved.pipeline_config_id == sample_execution.pipeline_config_id
        assert retrieved.input_text == sample_execution.input_text
        assert retrieved.output_text == sample_execution.output_text
        assert retrieved.provider == sample_execution.provider
        assert retrieved.model == sample_execution.model
        assert retrieved.tokens_in == sample_execution.tokens_in
        assert retrieved.tokens_out == sample_execution.tokens_out
        assert retrieved.duration_ms == sample_execution.duration_ms
        assert retrieved.status == sample_execution.status
        assert retrieved.error_message == sample_execution.error_message
        # Compare timestamps without timezone (SQLite doesn't preserve tz info)
        assert retrieved.timestamp.replace(
            tzinfo=None
        ) == sample_execution.timestamp.replace(tzinfo=None)
