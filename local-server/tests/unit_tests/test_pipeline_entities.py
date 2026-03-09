"""
Unit tests for pipeline domain entities.

Tests validate invariant enforcement, enum usage, and immutability of
pipeline configuration and execution entities.
"""

import sys
import os

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import types
import pytest

from domain.pipeline.entities import PipelineConfiguration, Execution
from domain.pipeline.enums import PipelineType, ExecutionStatus


class TestPipelineType:
    """Tests for PipelineType enum."""

    def test_pipeline_type_values(self):
        """Test that PipelineType has all expected values."""
        assert PipelineType.EXTRACTION.value == "extraction"
        assert PipelineType.CLASSIFICATION.value == "classification"
        assert PipelineType.SUMMARIZATION.value == "summarization"
        assert PipelineType.TRANSLATION.value == "translation"
        assert PipelineType.CUSTOM.value == "custom"

    def test_pipeline_type_from_string(self):
        """Test creating PipelineType from string value."""
        assert PipelineType("extraction") == PipelineType.EXTRACTION
        assert PipelineType("classification") == PipelineType.CLASSIFICATION

    def test_invalid_pipeline_type(self):
        """Test that invalid pipeline type raises ValueError."""
        with pytest.raises(ValueError):
            PipelineType("invalid_type")


class TestExecutionStatus:
    """Tests for ExecutionStatus enum."""

    def test_execution_status_values(self):
        """Test that ExecutionStatus has all expected values."""
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.RUNNING.value == "running"
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"

    def test_execution_status_from_string(self):
        """Test creating ExecutionStatus from string value."""
        assert ExecutionStatus("pending") == ExecutionStatus.PENDING
        assert ExecutionStatus("running") == ExecutionStatus.RUNNING


class TestPipelineConfiguration:
    """Tests for PipelineConfiguration entity."""

    def test_valid_pipeline_configuration(self):
        """Test creating a valid pipeline configuration."""
        config = PipelineConfiguration(
            id="test-pipeline-1",
            name="Test Pipeline",
            description="A test pipeline",
            pipeline_type=PipelineType.EXTRACTION,
            model_name="gpt-4",
            prompt_template="Extract entities from: {text}",
            parameters=types.MappingProxyType({"max_tokens": 100}),
            created_at="2025-03-06T00:00:00Z",
            updated_at="2025-03-06T00:00:00Z",
        )
        assert config.id == "test-pipeline-1"
        assert config.name == "Test Pipeline"
        assert config.pipeline_type == PipelineType.EXTRACTION
        assert config.model_name == "gpt-4"

    def test_pipeline_configuration_with_dict_parameters_raises_error(self):
        """Test that plain dict parameters raises TypeError."""
        with pytest.raises(TypeError, match="parameters must be a MappingProxyType"):
            PipelineConfiguration(
                id="test-pipeline-1",
                name="Test Pipeline",
                description="A test pipeline",
                pipeline_type=PipelineType.EXTRACTION,
                model_name="gpt-4",
                prompt_template="Extract entities from: {text}",
                parameters={"max_tokens": 100},
                created_at="2025-03-06T00:00:00Z",
                updated_at="2025-03-06T00:00:00Z",
            )

    def test_pipeline_configuration_parameters_immutable(self):
        """Test that parameters are immutable."""
        config = PipelineConfiguration(
            id="test-pipeline-1",
            name="Test Pipeline",
            description="A test pipeline",
            pipeline_type=PipelineType.EXTRACTION,
            model_name="gpt-4",
            prompt_template="Extract entities from: {text}",
            parameters=types.MappingProxyType({"max_tokens": 100}),
            created_at="2025-03-06T00:00:00Z",
            updated_at="2025-03-06T00:00:00Z",
        )
        with pytest.raises(TypeError):
            config.parameters["max_tokens"] = 200

    def test_pipeline_configuration_invalid_id(self):
        """Test that empty id raises ValueError."""
        with pytest.raises(ValueError, match="id must be a non-empty string"):
            PipelineConfiguration(
                id="",
                name="Test Pipeline",
                description="A test pipeline",
                pipeline_type=PipelineType.EXTRACTION,
                model_name="gpt-4",
                prompt_template="Extract entities from: {text}",
            )

    def test_pipeline_configuration_invalid_name(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="name must be a non-empty string"):
            PipelineConfiguration(
                id="test-pipeline-1",
                name="",
                description="A test pipeline",
                pipeline_type=PipelineType.EXTRACTION,
                model_name="gpt-4",
                prompt_template="Extract entities from: {text}",
            )

    def test_pipeline_configuration_invalid_pipeline_type(self):
        """Test that non-enum pipeline_type raises TypeError."""
        with pytest.raises(
            TypeError, match="pipeline_type must be a PipelineType enum"
        ):
            PipelineConfiguration(
                id="test-pipeline-1",
                name="Test Pipeline",
                description="A test pipeline",
                pipeline_type="extraction",  # String instead of enum
                model_name="gpt-4",
                prompt_template="Extract entities from: {text}",
            )

    def test_pipeline_configuration_invalid_model_name(self):
        """Test that empty model_name raises ValueError."""
        with pytest.raises(ValueError, match="model_name must be a non-empty string"):
            PipelineConfiguration(
                id="test-pipeline-1",
                name="Test Pipeline",
                description="A test pipeline",
                pipeline_type=PipelineType.EXTRACTION,
                model_name="",
                prompt_template="Extract entities from: {text}",
            )

    def test_pipeline_configuration_invalid_prompt_template(self):
        """Test that empty prompt_template raises ValueError."""
        with pytest.raises(
            ValueError, match="prompt_template must be a non-empty string"
        ):
            PipelineConfiguration(
                id="test-pipeline-1",
                name="Test Pipeline",
                description="A test pipeline",
                pipeline_type=PipelineType.EXTRACTION,
                model_name="gpt-4",
                prompt_template="",
            )


class TestExecution:
    """Tests for Execution entity."""

    def test_valid_execution(self):
        """Test creating a valid execution."""
        execution = Execution(
            id="execution-1",
            pipeline_id="pipeline-1",
            status=ExecutionStatus.PENDING,
            input_data=types.MappingProxyType({"text": "Sample text"}),
            output_data=None,
            error_message=None,
            created_at="2025-03-06T00:00:00Z",
            completed_at=None,
        )
        assert execution.id == "execution-1"
        assert execution.pipeline_id == "pipeline-1"
        assert execution.status == ExecutionStatus.PENDING

    def test_execution_with_dict_input_data(self):
        """Test that dict input_data must be wrapped in MappingProxyType."""
        with pytest.raises(TypeError, match="input_data must be a MappingProxyType"):
            Execution(
                id="execution-1",
                pipeline_id="pipeline-1",
                status=ExecutionStatus.PENDING,
                input_data={"text": "Sample text"},  # Dict instead of MappingProxyType
                output_data=None,
                error_message=None,
                created_at="2025-03-06T00:00:00Z",
                completed_at=None,
            )

    def test_execution_with_output_data(self):
        """Test execution with output data."""
        execution = Execution(
            id="execution-1",
            pipeline_id="pipeline-1",
            status=ExecutionStatus.COMPLETED,
            input_data=types.MappingProxyType({"text": "Sample text"}),
            output_data=types.MappingProxyType({"entities": []}),
            error_message=None,
            created_at="2025-03-06T00:00:00Z",
            completed_at="2025-03-06T00:01:00Z",
        )
        assert execution.output_data["entities"] == []

    def test_execution_output_data_immutable(self):
        """Test that output_data is immutable."""
        execution = Execution(
            id="execution-1",
            pipeline_id="pipeline-1",
            status=ExecutionStatus.COMPLETED,
            input_data=types.MappingProxyType({"text": "Sample text"}),
            output_data=types.MappingProxyType({"entities": []}),
            error_message=None,
            created_at="2025-03-06T00:00:00Z",
            completed_at="2025-03-06T00:01:00Z",
        )
        with pytest.raises(TypeError):
            execution.output_data["entities"] = ["new_entity"]

    def test_execution_invalid_id(self):
        """Test that empty id raises ValueError."""
        with pytest.raises(ValueError, match="Execution id must be a non-empty string"):
            Execution(
                id="",
                pipeline_id="pipeline-1",
                status=ExecutionStatus.PENDING,
                input_data=types.MappingProxyType({}),
                output_data=None,
                error_message=None,
                created_at="2025-03-06T00:00:00Z",
                completed_at=None,
            )

    def test_execution_invalid_pipeline_id(self):
        """Test that empty pipeline_id raises ValueError."""
        with pytest.raises(
            ValueError, match="Execution pipeline_id must be a non-empty string"
        ):
            Execution(
                id="execution-1",
                pipeline_id="",
                status=ExecutionStatus.PENDING,
                input_data=types.MappingProxyType({}),
                output_data=None,
                error_message=None,
                created_at="2025-03-06T00:00:00Z",
                completed_at=None,
            )

    def test_execution_invalid_status(self):
        """Test that non-enum status raises TypeError."""
        with pytest.raises(TypeError, match="status must be an ExecutionStatus enum"):
            Execution(
                id="execution-1",
                pipeline_id="pipeline-1",
                status="pending",  # String instead of enum
                input_data=types.MappingProxyType({}),
                output_data=None,
                error_message=None,
                created_at="2025-03-06T00:00:00Z",
                completed_at=None,
            )

    def test_execution_invalid_created_at(self):
        """Test that empty created_at raises ValueError."""
        with pytest.raises(
            ValueError,
            match="Execution created_at must be a non-empty timestamp string",
        ):
            Execution(
                id="execution-1",
                pipeline_id="pipeline-1",
                status=ExecutionStatus.PENDING,
                input_data=types.MappingProxyType({}),
                output_data=None,
                error_message=None,
                created_at="",
                completed_at=None,
            )

    def test_execution_invalid_output_data_type(self):
        """Test that invalid output_data type raises TypeError."""
        with pytest.raises(
            TypeError, match="output_data must be None or MappingProxyType"
        ):
            Execution(
                id="execution-1",
                pipeline_id="pipeline-1",
                status=ExecutionStatus.COMPLETED,
                input_data=types.MappingProxyType({}),
                output_data={"entities": []},  # Dict instead of MappingProxyType
                error_message=None,
                created_at="2025-03-06T00:00:00Z",
                completed_at="2025-03-06T00:01:00Z",
            )

    def test_execution_invalid_error_message(self):
        """Test that non-string error_message raises TypeError."""
        with pytest.raises(TypeError, match="error_message must be None or a string"):
            Execution(
                id="execution-1",
                pipeline_id="pipeline-1",
                status=ExecutionStatus.FAILED,
                input_data=types.MappingProxyType({}),
                output_data=None,
                error_message=123,  # Integer instead of string
                created_at="2025-03-06T00:00:00Z",
                completed_at="2025-03-06T00:01:00Z",
            )
