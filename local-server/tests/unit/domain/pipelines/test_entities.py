"""
Unit tests for domain.pipelines.entities

Tests immutability, status transitions, and invariants for PipelineRun
and its per-type subclasses.
"""

import pytest

from domain.pipelines.entities import (
    IndividualExtractionRun,
    PipelineRun,
    PipelineRunStatus,
    PipelineType,
    SchemaConnectionRefinementRun,
    SchemaDefinitionRefinementRun,
    SchemaExtractionRun,
    SchemaGroundingRun,
)


class TestPipelineRun:
    """Tests for PipelineRun entity."""

    def test_create_pending_run(self):
        """Test creating a new pipeline run with PENDING status."""
        run = PipelineRun(
            id="run-123",
            batch_run_id="batch-456",
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="impl-001",
            configuration_ref="config-default",
            status=PipelineRunStatus.PENDING,
        )

        assert run.id == "run-123"
        assert run.batch_run_id == "batch-456"
        assert run.pipeline_type == PipelineType.INDIVIDUAL_EXTRACTION
        assert run.implementation_id == "impl-001"
        assert run.configuration_ref == "config-default"
        assert run.status == PipelineRunStatus.PENDING
        assert run.input_summary == {}
        assert run.output_summary == {}
        assert run.llm_metadata == {}

    def test_immutability(self):
        """Test that PipelineRun is immutable (frozen dataclass)."""
        run = PipelineRun(
            id="run-123",
            batch_run_id="batch-456",
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="impl-001",
            configuration_ref="config-default",
            status=PipelineRunStatus.PENDING,
        )

        with pytest.raises(AttributeError):
            run.status = PipelineRunStatus.RUNNING


class TestIndividualExtractionRun:
    """Tests for IndividualExtractionRun entity."""

    def test_create_extraction_run(self):
        """Test creating an individual extraction run."""
        run = IndividualExtractionRun.create(
            id="run-123",
            batch_run_id="batch-456",
            implementation_id="impl-default",
            configuration_ref="extraction-default",
            configuration_slug="extraction-default",
            configuration_version=1,
            source_text_hash="abc123",
            source_document_uri="s3://bucket/doc.txt",
        )

        assert run.id == "run-123"
        assert run.batch_run_id == "batch-456"
        assert run.pipeline_type == PipelineType.INDIVIDUAL_EXTRACTION
        assert run.implementation_id == "impl-default"
        assert run.configuration_ref == "extraction-default"
        assert run.configuration_slug == "extraction-default"
        assert run.configuration_version == 1
        assert run.status == PipelineRunStatus.PENDING
        assert run.source_text_hash == "abc123"
        assert run.source_document_uri == "s3://bucket/doc.txt"

    def test_create_extraction_run_without_uri(self):
        """Test creating an extraction run without document URI."""
        run = IndividualExtractionRun.create(
            id="run-123",
            batch_run_id="batch-456",
            implementation_id="impl-default",
            configuration_ref="extraction-default",
            configuration_slug="extraction-default",
            configuration_version=1,
            source_text_hash="abc123",
        )

        assert run.source_document_uri is None
        assert run.source_text_hash == "abc123"


class TestSchemaExtractionRun:
    """Tests for SchemaExtractionRun entity."""

    def test_create_schema_extraction_run(self):
        """Test creating a schema extraction run."""
        run = SchemaExtractionRun.create(
            id="run-123",
            batch_run_id="batch-456",
            implementation_id="impl-schema",
            configuration_ref="schema-default",
            configuration_slug="schema-default",
            configuration_version=1,
        )

        assert run.id == "run-123"
        assert run.pipeline_type == PipelineType.SCHEMA_EXTRACTION
        assert run.status == PipelineRunStatus.PENDING
        assert run.configuration_slug == "schema-default"
        assert run.configuration_version == 1


class TestSchemaGroundingRun:
    """Tests for SchemaGroundingRun entity."""

    def test_create_grounding_run(self):
        """Test creating a schema grounding run."""
        run = SchemaGroundingRun.create(
            id="run-123",
            batch_run_id="batch-456",
            implementation_id="impl-grounding",
            configuration_ref="grounding-default",
            configuration_slug="grounding-default",
            configuration_version=1,
        )

        assert run.id == "run-123"
        assert run.pipeline_type == PipelineType.SCHEMA_NODE_GROUNDING
        assert run.status == PipelineRunStatus.PENDING
        assert run.configuration_slug == "grounding-default"
        assert run.configuration_version == 1


class TestSchemaDefinitionRefinementRun:
    """Tests for SchemaDefinitionRefinementRun entity."""

    def test_create_definition_refinement_run(self):
        """Test creating a schema definition refinement run."""
        run = SchemaDefinitionRefinementRun.create(
            id="run-123",
            batch_run_id="batch-456",
            implementation_id="impl-definition",
            configuration_ref="definition-default",
            configuration_slug="definition-default",
            configuration_version=1,
        )

        assert run.id == "run-123"
        assert run.pipeline_type == PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT
        assert run.status == PipelineRunStatus.PENDING
        assert run.configuration_slug == "definition-default"
        assert run.configuration_version == 1


class TestSchemaConnectionRefinementRun:
    """Tests for SchemaConnectionRefinementRun entity."""

    def test_create_connection_refinement_run(self):
        """Test creating a schema connection refinement run."""
        run = SchemaConnectionRefinementRun.create(
            id="run-123",
            batch_run_id="batch-456",
            implementation_id="impl-connection",
            configuration_ref="connection-default",
            configuration_slug="connection-default",
            configuration_version=1,
        )

        assert run.id == "run-123"
        assert run.pipeline_type == PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT
        assert run.status == PipelineRunStatus.PENDING
        assert run.configuration_slug == "connection-default"
        assert run.configuration_version == 1


class TestPipelineRunValidation:
    """Tests for PipelineRun construction-time validation."""

    def test_pipeline_run_rejects_empty_batch_run_id(self):
        """PipelineRun rejects empty batch_run_id."""
        with pytest.raises(ValueError, match="batch_run_id cannot be empty"):
            PipelineRun(
                id="run-123",
                batch_run_id="",  # Invalid: empty
                pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
                implementation_id="impl-001",
                configuration_ref="config-default",
            )

    def test_pipeline_run_rejects_zero_configuration_version(self):
        """PipelineRun rejects configuration_version <= 0."""
        with pytest.raises(
            ValueError, match="configuration_version must be greater than 0"
        ):
            PipelineRun(
                id="run-123",
                batch_run_id="batch-456",
                pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
                implementation_id="impl-001",
                configuration_ref="config-default",
                configuration_version=0,  # Invalid: must be > 0
            )

    def test_pipeline_run_rejects_pending_with_failure_reason(self):
        """PipelineRun rejects status=PENDING with failure_reason set."""
        with pytest.raises(
            ValueError,
            match="status=PENDING is incompatible with a set failure_reason",
        ):
            PipelineRun(
                id="run-123",
                batch_run_id="batch-456",
                pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
                implementation_id="impl-001",
                configuration_ref="config-default",
                status=PipelineRunStatus.PENDING,
                failure_reason="Some failure",  # Invalid: PENDING shouldn't have failure reason
            )

    def test_pipeline_run_accepts_failed_with_failure_reason(self):
        """PipelineRun accepts status=FAILED with failure_reason set."""
        run = PipelineRun(
            id="run-123",
            batch_run_id="batch-456",
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="impl-001",
            configuration_ref="config-default",
            status=PipelineRunStatus.FAILED,
            failure_reason="Extraction failed",  # Valid: FAILED with failure reason
        )
        assert run.status == PipelineRunStatus.FAILED
        assert run.failure_reason == "Extraction failed"

    def test_pipeline_run_accepts_valid_construction(self):
        """PipelineRun accepts valid construction parameters."""
        run = PipelineRun(
            id="run-123",
            batch_run_id="batch-456",
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="impl-001",
            configuration_ref="config-default",
            configuration_version=1,
            status=PipelineRunStatus.PENDING,
        )
        assert run.batch_run_id == "batch-456"
        assert run.configuration_version == 1


class TestPipelineRunStatus:
    """Tests for PipelineRunStatus enum."""

    def test_all_statuses_defined(self):
        """Test that all expected statuses are defined."""
        statuses = [
            PipelineRunStatus.PENDING,
            PipelineRunStatus.RUNNING,
            PipelineRunStatus.COMPLETED,
            PipelineRunStatus.FAILED,
        ]

        assert len(statuses) == 4
        assert all(isinstance(s, PipelineRunStatus) for s in statuses)

    def test_status_string_values(self):
        """Test status enum string representations."""
        assert PipelineRunStatus.PENDING.value == "pending"
        assert PipelineRunStatus.RUNNING.value == "running"
        assert PipelineRunStatus.COMPLETED.value == "completed"
        assert PipelineRunStatus.FAILED.value == "failed"


class TestPipelineType:
    """Tests for PipelineType enum."""

    def test_all_types_defined(self):
        """Test that all five pipeline types are defined."""
        types = [
            PipelineType.INDIVIDUAL_EXTRACTION,
            PipelineType.SCHEMA_EXTRACTION,
            PipelineType.SCHEMA_NODE_GROUNDING,
            PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
        ]

        assert len(types) == 5
        assert all(isinstance(t, PipelineType) for t in types)

    def test_type_string_values(self):
        """Test pipeline type enum string representations."""
        assert PipelineType.INDIVIDUAL_EXTRACTION.value == "individual_extraction"
        assert PipelineType.SCHEMA_EXTRACTION.value == "schema_extraction"
        assert PipelineType.SCHEMA_NODE_GROUNDING.value == "schema_node_grounding"
        assert (
            PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT.value
            == "schema_node_definition_refinement"
        )
        assert (
            PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT.value
            == "schema_node_connection_refinement"
        )
