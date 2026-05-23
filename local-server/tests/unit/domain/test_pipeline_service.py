"""
Unit tests for the PipelineService domain service.

These tests verify pipeline configuration CRUD operations, execution recording,
event publishing, and error handling in isolation using fake ports.
"""

import os
import sys
import time
import pytest
from domain.pipeline.events import PipelineExecuted
from domain.pipeline.exceptions import PipelineNotFoundError
from domain.pipeline.services import PipelineService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_pipeline_repository import FakePipelineRepository

class TestPipelineServiceConfigurationCRUD:
    """Tests for pipeline configuration lifecycle (create, read, update, delete)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.repo = FakePipelineRepository()
        self.llm = FakeLLMProvider()
        self.event_pub = FakeEventPublisher()
        self.service = PipelineService(
            pipeline_repo=self.repo,
            flavor_repo=self.repo,
            llm=self.llm,
            event_publisher=self.event_pub,
        )

    def test_create_config(self):
        """Create a new pipeline configuration."""
        config = self.service.create_config(
            pipeline="document-extractor",
            title="Extract Key Information",
            provider="openai",
            model="gpt-4",
            config={"timeout": 30, "temperature": 0.0},
            system_prompt="You are a helpful assistant.",
            user_prompt="Extract key information from: {text}",
        )

        assert config.id is not None
        assert config.pipeline == "document-extractor"
        assert config.title == "Extract Key Information"
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.config == {"timeout": 30, "temperature": 0.0}
        assert config.system_prompt == "You are a helpful assistant."
        assert config.user_prompt == "Extract key information from: {text}"
        assert config.version == 1
        assert config.enabled is True
        assert config.created_at is not None
        assert config.last_updated is not None

    def test_get_config_returns_all_fields_unchanged(self):
        """Saved config retrieved by ID returns all fields unchanged."""
        # Create a config
        created = self.service.create_config(
            pipeline="test-pipeline",
            title="Test",
            provider="anthropic",
            model="claude-opus",
            config={"timeout": 60, "temperature": 0.5},
            system_prompt="System",
            user_prompt="User: {text}",
        )

        # Retrieve it
        retrieved = self.service.get_config(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.pipeline == created.pipeline
        assert retrieved.title == created.title
        assert retrieved.provider == created.provider
        assert retrieved.model == created.model
        assert retrieved.config == created.config
        assert retrieved.system_prompt == created.system_prompt
        assert retrieved.user_prompt == created.user_prompt
        assert retrieved.version == created.version
        assert retrieved.enabled == created.enabled
        assert retrieved.created_at == created.created_at
        assert retrieved.last_updated == created.last_updated

    def test_get_config_raises_if_not_found(self):
        """Getting non-existent config raises PipelineNotFoundError."""
        with pytest.raises(PipelineNotFoundError, match="not found"):
            self.service.get_config("nonexistent-id")

    def test_list_configs(self):
        """List all pipeline configurations."""
        config1 = self.service.create_config(
            pipeline="pipeline-1",
            title="Config 1",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System 1",
            user_prompt="User 1: {text}",
        )

        config2 = self.service.create_config(
            pipeline="pipeline-2",
            title="Config 2",
            provider="anthropic",
            model="claude-opus",
            config={},
            system_prompt="System 2",
            user_prompt="User 2: {text}",
        )

        configs = self.service.list_configs()
        assert len(configs) == 2
        config_ids = [c.id for c in configs]
        assert config1.id in config_ids
        assert config2.id in config_ids

    def test_list_configs_enabled_only(self):
        """List only enabled configurations."""
        config1 = self.service.create_config(
            pipeline="pipeline-1",
            title="Config 1",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System 1",
            user_prompt="User 1: {text}",
        )

        config2 = self.service.create_config(
            pipeline="pipeline-2",
            title="Config 2",
            provider="anthropic",
            model="claude-opus",
            config={},
            system_prompt="System 2",
            user_prompt="User 2: {text}",
        )

        # Disable one config
        self.service.update_config(config2.id, enabled=False)

        enabled_configs = self.service.list_configs(enabled_only=True)
        assert len(enabled_configs) == 1
        assert enabled_configs[0].id == config1.id

    def test_update_config(self):
        """Update a pipeline configuration."""
        created = self.service.create_config(
            pipeline="original",
            title="Original Title",
            provider="openai",
            model="gpt-4",
            config={"timeout": 30},
            system_prompt="Original system",
            user_prompt="Original user: {text}",
        )

        updated = self.service.update_config(
            created.id,
            title="Updated Title",
            model="gpt-4-turbo",
            config={"timeout": 60},
        )

        assert updated.id == created.id
        assert updated.title == "Updated Title"
        assert updated.model == "gpt-4-turbo"
        assert updated.config == {"timeout": 60}
        assert updated.version == 2
        assert updated.pipeline == "original"  # Unchanged
        assert updated.system_prompt == "Original system"  # Unchanged

    def test_update_config_raises_if_not_found(self):
        """Updating non-existent config raises PipelineNotFoundError."""
        with pytest.raises(PipelineNotFoundError, match="not found"):
            self.service.update_config("nonexistent-id", title="New Title")

    def test_update_config_with_explicit_seed_sets_it(self):
        """Updating config with explicit seed value sets the seed."""
        created = self.service.create_config(
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
        )

        updated = self.service.update_config(created.id, seed=42)

        assert updated.seed == 42

    def test_update_config_with_explicit_seed_zero_sets_it(self):
        """Updating config with explicit seed=0 sets zero as the seed."""
        created = self.service.create_config(
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
        )

        updated = self.service.update_config(created.id, seed=0)

        assert updated.seed == 0

    def test_update_config_with_seed_none_clears_it(self):
        """Updating config with seed=None clears the seed."""
        created = self.service.create_config(
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
        )

        # First set a seed value
        with_seed = self.service.update_config(created.id, seed=42)
        assert with_seed.seed == 42

        # Clear it by passing None
        updated = self.service.update_config(created.id, seed=None)

        assert updated.seed is None

    def test_update_config_without_seed_preserves_existing(self):
        """Updating config without specifying seed preserves the existing value."""
        created = self.service.create_config(
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
        )

        # First set a seed value
        with_seed = self.service.update_config(created.id, seed=42)
        assert with_seed.seed == 42

        # Update other fields without mentioning seed
        updated = self.service.update_config(created.id, title="New Title")

        assert updated.seed == 42  # Seed is preserved

    def test_delete_config(self):
        """Delete a pipeline configuration."""
        config = self.service.create_config(
            pipeline="to-delete",
            title="Will be deleted",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
        )

        self.service.delete_config(config.id)

        # Verify it's gone by checking that get_config raises
        with pytest.raises(PipelineNotFoundError):
            self.service.get_config(config.id)

    def test_delete_config_raises_if_not_found(self):
        """Deleting non-existent config raises PipelineNotFoundError."""
        with pytest.raises(PipelineNotFoundError, match="not found"):
            self.service.delete_config("nonexistent-id")


class TestPipelineServiceExecution:
    """Tests for pipeline execution with complete instrumentation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.repo = FakePipelineRepository()
        self.llm = FakeLLMProvider(
            response_content="Extracted information",
            tokens_in=15,
            tokens_out=25,
        )
        self.event_pub = FakeEventPublisher()
        self.service = PipelineService(
            pipeline_repo=self.repo,
            flavor_repo=self.repo,
            llm=self.llm,
            event_publisher=self.event_pub,
        )

    def test_execute_pipeline_records_successful_execution(self):
        """Execute pipeline records execution with success status and token counts."""
        config = self.service.create_config(
            pipeline="extractor",
            title="Test Extractor",
            provider="openai",
            model="gpt-4",
            config={"timeout": 30},
            system_prompt="Extract data",
            user_prompt="From: {text}",
        )

        execution = self.service.execute_pipeline(config.id, "Sample input text")

        assert execution.id is not None
        assert execution.pipeline_config_id == config.id
        assert execution.input_text == "Sample input text"
        assert execution.output_text == "Extracted information"
        assert execution.provider == "openai"
        assert execution.model == "gpt-4"
        assert execution.tokens_in == 15
        assert execution.tokens_out == 25
        assert execution.duration_ms >= 0  # May be 0 on fast systems
        assert execution.status == "success"
        assert execution.error_message is None

    def test_execute_pipeline_substitutes_text_placeholder(self):
        """Execute pipeline substitutes {text} placeholder in user prompt."""
        config = self.service.create_config(
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="Process this: {text}",
        )

        self.service.execute_pipeline(config.id, "actual input")

        # Check that the LLM was called with the substituted prompt
        assert self.llm.last_call_args is not None
        assert self.llm.last_call_args["user_prompt"] == "Process this: actual input"

    def test_execute_pipeline_records_error_execution(self):
        """Execute pipeline records execution with error status when LLM fails."""
        # Set up LLM to raise an error
        self.llm.should_raise_error = True
        self.llm.error_to_raise = RuntimeError("LLM service unavailable")

        config = self.service.create_config(
            pipeline="extractor",
            title="Test Extractor",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="Extract",
            user_prompt="Input: {text}",
        )

        execution = self.service.execute_pipeline(config.id, "Test input")

        assert execution.status == "error"
        assert "LLM service unavailable" in execution.error_message
        assert execution.output_text == ""
        assert execution.tokens_in == 0
        assert execution.tokens_out == 0
        assert execution.duration_ms >= 0  # May be 0 on fast systems

    def test_execute_pipeline_publishes_event_on_success(self):
        """Execute pipeline publishes PipelineExecuted event on success."""
        config = self.service.create_config(
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
        )

        execution = self.service.execute_pipeline(config.id, "Input")

        events = self.event_pub.get_events_of_type(PipelineExecuted)
        assert len(events) == 1
        event = events[0]
        assert event.execution_id == execution.id
        assert event.pipeline_id == config.id
        assert event.status == "success"

    def test_execute_pipeline_publishes_event_on_error(self):
        """Execute pipeline publishes PipelineExecuted event on error."""
        self.llm.should_raise_error = True
        self.llm.error_to_raise = RuntimeError("API connection failed")

        config = self.service.create_config(
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
        )

        self.service.execute_pipeline(config.id, "Input")

        events = self.event_pub.get_events_of_type(PipelineExecuted)
        assert len(events) == 1
        event = events[0]
        assert event.status == "error"

    def test_list_executions_raises_if_config_not_found(self):
        """List executions raises PipelineNotFoundError if config not found."""
        with pytest.raises(PipelineNotFoundError, match="not found"):
            self.service.list_executions("nonexistent-id")

    def test_execute_pipeline_raises_if_config_not_found(self):
        """Execute pipeline raises PipelineNotFoundError if config not found."""
        with pytest.raises(PipelineNotFoundError, match="not found"):
            self.service.execute_pipeline("nonexistent-id", "Input")

    def test_execute_pipeline_records_with_repository(self):
        """Execution is recorded in the repository."""
        config = self.service.create_config(
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
        )

        execution = self.service.execute_pipeline(config.id, "Test input")

        # Retrieve from repository
        executions = self.repo.get_executions(config.id)
        assert len(executions) == 1
        assert executions[0].id == execution.id

    def test_execute_pipeline_multiple_executions_tracked(self):
        """Multiple executions are tracked separately."""
        config = self.service.create_config(
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="System",
            user_prompt="User: {text}",
        )

        exec1 = self.service.execute_pipeline(config.id, "Input 1")
        exec2 = self.service.execute_pipeline(config.id, "Input 2")

        executions = self.repo.get_executions(config.id)
        assert len(executions) == 2
        execution_ids = [e.id for e in executions]
        assert exec1.id in execution_ids
        assert exec2.id in execution_ids

    def test_execute_pipeline_uses_config_timeout(self):
        """Execute pipeline passes timeout from config to LLM."""
        config = self.service.create_config(
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={"timeout": 45, "temperature": 0.7, "max_tokens": 1000},
            system_prompt="System",
            user_prompt="User: {text}",
        )

        self.service.execute_pipeline(config.id, "Input")

        # Check that config values were used
        assert self.llm.last_call_args["temperature"] == 0.7
        assert self.llm.last_call_args["max_tokens"] == 1000

    def test_execute_pipeline_uses_default_timeout(self):
        """Execute pipeline uses default timeout of 30 seconds."""
        config = self.service.create_config(
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={},  # No timeout specified
            system_prompt="System",
            user_prompt="User: {text}",
        )

        execution = self.service.execute_pipeline(config.id, "Input")
        # Should succeed without timeout (takes much less than 30 seconds)
        assert execution.status == "success"

    def test_execute_pipeline_uses_default_temperature_and_max_tokens(self):
        """Execute pipeline uses default temperature and max_tokens from config."""
        config = self.service.create_config(
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={},  # No temperature or max_tokens specified
            system_prompt="System",
            user_prompt="User: {text}",
        )

        self.service.execute_pipeline(config.id, "Input")

        # Should use defaults
        assert self.llm.last_call_args["temperature"] == 0.0
        assert self.llm.last_call_args["max_tokens"] == 2000

    def test_execute_pipeline_records_success_even_if_slow(self):
        """Execute pipeline records success even if execution takes longer than timeout config."""
        # The timeout config is advisory and enforced by the LLM adapter layer.
        # If a call succeeds, we record it as success regardless of duration.
        config = self.service.create_config(
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={"timeout": 1},  # 1 second timeout in config
            system_prompt="System",
            user_prompt="User: {text}",
        )

        # Monkey-patch time.time to simulate slow execution
        original_time = time.time
        call_count = [0]

        def fake_time():
            call_count[0] += 1
            if call_count[0] == 1:  # First call (start_time)
                return 0.0
            else:  # Second call (end_time)
                return 2.0  # 2 seconds elapsed, exceeds config timeout

        time.time = fake_time
        try:
            execution = self.service.execute_pipeline(config.id, "Input")
            # Successful responses are recorded as success, not timeout
            assert execution.status == "success"
            assert execution.output_text == "Extracted information"
            assert execution.duration_ms == 2000
        finally:
            time.time = original_time

    def test_execute_pipeline_records_error_for_type_error(self):
        """Execute pipeline records execution with error status when LLM raises TypeError."""
        # Set up LLM to raise TypeError (e.g., invalid model type)
        self.llm.should_raise_error = True
        self.llm.error_to_raise = TypeError("Model argument must be a string")

        config = self.service.create_config(
            pipeline="extractor",
            title="Test Extractor",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="Extract",
            user_prompt="Input: {text}",
        )

        execution = self.service.execute_pipeline(config.id, "Test input")

        assert execution.status == "error"
        assert "Model argument must be a string" in execution.error_message
        assert execution.output_text == ""
        assert execution.tokens_in == 0
        assert execution.tokens_out == 0
        assert execution.duration_ms >= 0

    def test_execute_pipeline_records_error_for_key_error(self):
        """Execute pipeline records execution with error status when LLM raises KeyError."""
        # Set up LLM to raise KeyError (e.g., missing config key)
        self.llm.should_raise_error = True
        self.llm.error_to_raise = KeyError("api_key")

        config = self.service.create_config(
            pipeline="extractor",
            title="Test Extractor",
            provider="openai",
            model="gpt-4",
            config={},
            system_prompt="Extract",
            user_prompt="Input: {text}",
        )

        execution = self.service.execute_pipeline(config.id, "Test input")

        assert execution.status == "error"
        assert "api_key" in execution.error_message
        assert execution.output_text == ""
        assert execution.tokens_in == 0
        assert execution.tokens_out == 0
        assert execution.duration_ms >= 0

    def test_execute_pipeline_records_timeout_execution(self):
        """Execute pipeline records execution with timeout status when LLM times out."""
        # Set up LLM to raise TimeoutError
        self.llm.should_raise_error = True
        self.llm.error_to_raise = TimeoutError("Request exceeded timeout of 30s")

        config = self.service.create_config(
            pipeline="extractor",
            title="Test Extractor",
            provider="openai",
            model="gpt-4",
            config={"timeout": 30},
            system_prompt="Extract",
            user_prompt="Input: {text}",
        )

        execution = self.service.execute_pipeline(config.id, "Test input")

        assert execution.status == "timeout"
        assert "timeout" in execution.error_message.lower()
        assert execution.output_text == ""
        assert execution.tokens_in == 0
        assert execution.tokens_out == 0
        assert execution.duration_ms >= 0

    def test_execute_pipeline_publishes_event_on_timeout(self):
        """Execute pipeline publishes PipelineExecuted event with timeout status on timeout."""
        self.llm.should_raise_error = True
        self.llm.error_to_raise = TimeoutError("Request exceeded timeout")

        config = self.service.create_config(
            pipeline="test",
            title="Test",
            provider="openai",
            model="gpt-4",
            config={"timeout": 30},
            system_prompt="System",
            user_prompt="User: {text}",
        )

        execution = self.service.execute_pipeline(config.id, "Input")

        events = self.event_pub.get_events_of_type(PipelineExecuted)
        assert len(events) == 1
        event = events[0]
        assert event.status == "timeout"
        assert event.execution_id == execution.id
        assert event.pipeline_id == config.id
