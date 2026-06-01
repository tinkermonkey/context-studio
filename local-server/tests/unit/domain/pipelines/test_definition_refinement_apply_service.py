"""
Unit tests for SchemaDefinitionRefinementApplyService.

Tests cover confidence thresholds, node_id handling, candidate selection,
and correct ApplyResult tracking.
"""

import pytest
from unittest.mock import Mock

from domain.ontology.entities import Class
from domain.pipelines.apply_result import ApplyResult
from domain.pipelines.entities import PipelineRun, PipelineRunStatus
from domain.pipelines.schema_node_definition_refinement.apply_service import (
    SchemaDefinitionRefinementApplyService,
)


@pytest.fixture
def mock_ontology_repo():
    """Create a mock ontology repository."""
    return Mock()


@pytest.fixture
def sample_class():
    """Create a sample Class entity for testing."""
    return Class(
        id="class-456",
        concept_scheme_id="scheme-1",
        taxonomy_id="tax-1",
        title="Service",
        description="Original description",
    )


@pytest.fixture
def sample_pipeline_run_with_candidates():
    """Create a pipeline run with multiple definition candidates."""
    return PipelineRun(
        id="run-def-123",
        batch_run_id="batch-def-123",
        implementation_id="default",
        configuration_slug="refinement-default",
        configuration_version=1,
        status=PipelineRunStatus.COMPLETED,
        output_summary={
            "node_id": "class-456",
            "candidates": [
                {
                    "definition": "A low-confidence definition",
                    "confidence": 0.6,
                },
                {
                    "definition": "A high-confidence refined definition",
                    "confidence": 0.95,
                },
                {
                    "definition": "A mid-confidence definition",
                    "confidence": 0.8,
                },
            ],
        },
    )


class TestSchemaDefinitionRefinementApplyServiceBasic:
    """Basic functionality tests for definition refinement apply service."""

    def test_apply_selects_highest_confidence_candidate(
        self, mock_ontology_repo, sample_class, sample_pipeline_run_with_candidates
    ):
        """Apply selects and applies the highest-confidence candidate."""
        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaDefinitionRefinementApplyService(mock_ontology_repo)

        result = service.apply(sample_pipeline_run_with_candidates)

        assert result.classes_updated == 1
        assert result.classes_skipped == 0

        # Verify the class was updated with the highest-confidence definition
        saved_class = mock_ontology_repo.save_class.call_args[0][0]
        assert saved_class.description == "A high-confidence refined definition"

    def test_confidence_threshold_filtering(
        self, mock_ontology_repo, sample_class, sample_pipeline_run_with_candidates
    ):
        """Candidates below confidence threshold are filtered out."""
        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaDefinitionRefinementApplyService(mock_ontology_repo)

        result = service.apply(sample_pipeline_run_with_candidates, confidence_threshold=0.9)

        assert result.classes_updated == 1
        assert result.classes_skipped == 0

        # Should use the 0.95 candidate, not 0.8
        saved_class = mock_ontology_repo.save_class.call_args[0][0]
        assert saved_class.description == "A high-confidence refined definition"

    def test_all_candidates_below_threshold(
        self, mock_ontology_repo, sample_class, sample_pipeline_run_with_candidates
    ):
        """No candidates above threshold results in skip."""
        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaDefinitionRefinementApplyService(mock_ontology_repo)

        result = service.apply(sample_pipeline_run_with_candidates, confidence_threshold=0.99)

        assert result.classes_updated == 0
        assert result.classes_skipped == 1
        mock_ontology_repo.save_class.assert_not_called()

    def test_missing_node_id_raises_error(self, mock_ontology_repo):
        """Missing node_id in output_summary raises ValueError."""
        run = PipelineRun(
            id="run-no-node",
            batch_run_id="batch-no-node",
            implementation_id="default",
            configuration_slug="refinement-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "candidates": [
                    {"definition": "Test", "confidence": 0.95},
                ]
            },
        )

        service = SchemaDefinitionRefinementApplyService(mock_ontology_repo)

        with pytest.raises(ValueError, match="node_id missing from output_summary"):
            service.apply(run)

    def test_class_not_found_raises_error(self, mock_ontology_repo):
        """Non-existent class raises ValueError."""
        mock_ontology_repo.get_class.return_value = None
        run = PipelineRun(
            id="run-no-class",
            batch_run_id="batch-no-class",
            implementation_id="default",
            configuration_slug="refinement-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "node_id": "nonexistent-id",
                "candidates": [
                    {"definition": "Test", "confidence": 0.95},
                ],
            },
        )

        service = SchemaDefinitionRefinementApplyService(mock_ontology_repo)

        with pytest.raises(ValueError, match="not found"):
            service.apply(run)

    def test_empty_candidates_list(self, mock_ontology_repo, sample_class):
        """Empty candidates list results in skip."""
        run = PipelineRun(
            id="run-empty-cand",
            batch_run_id="batch-empty-cand",
            implementation_id="default",
            configuration_slug="refinement-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "node_id": "class-456",
                "candidates": [],
            },
        )

        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaDefinitionRefinementApplyService(mock_ontology_repo)

        result = service.apply(run)

        assert result.classes_updated == 0
        assert result.classes_skipped == 1
        mock_ontology_repo.save_class.assert_not_called()


class TestSchemaDefinitionRefinementApplyServiceEdgeCases:
    """Edge case tests for definition refinement apply service."""

    def test_whitespace_only_definition_is_skipped(self, mock_ontology_repo, sample_class):
        """Definitions with only whitespace are treated as empty."""
        run = PipelineRun(
            id="run-ws-def",
            batch_run_id="batch-ws-def",
            implementation_id="default",
            configuration_slug="refinement-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "node_id": "class-456",
                "candidates": [
                    {
                        "definition": "   ",
                        "confidence": 0.95,
                    },
                ],
            },
        )

        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaDefinitionRefinementApplyService(mock_ontology_repo)

        result = service.apply(run)

        assert result.classes_updated == 0
        assert result.classes_skipped == 1

    def test_missing_definition_field_is_skipped(self, mock_ontology_repo, sample_class):
        """Candidates without definition field are skipped."""
        run = PipelineRun(
            id="run-no-def-field",
            batch_run_id="batch-no-def-field",
            implementation_id="default",
            configuration_slug="refinement-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "node_id": "class-456",
                "candidates": [
                    {
                        "confidence": 0.95,
                        # no definition
                    },
                ],
            },
        )

        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaDefinitionRefinementApplyService(mock_ontology_repo)

        result = service.apply(run)

        assert result.classes_updated == 0
        assert result.classes_skipped == 1

    def test_missing_confidence_field_defaults_to_zero(self, mock_ontology_repo, sample_class):
        """Missing confidence field defaults to 0.0."""
        run = PipelineRun(
            id="run-no-conf",
            batch_run_id="batch-no-conf",
            implementation_id="default",
            configuration_slug="refinement-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "node_id": "class-456",
                "candidates": [
                    {
                        "definition": "Test definition",
                        # no confidence
                    },
                ],
            },
        )

        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaDefinitionRefinementApplyService(mock_ontology_repo)

        result = service.apply(run, confidence_threshold=0.1)

        assert result.classes_updated == 0
        assert result.classes_skipped == 1

    def test_multiple_qualifying_candidates_uses_highest(
        self, mock_ontology_repo, sample_class
    ):
        """When multiple candidates qualify, highest confidence wins."""
        run = PipelineRun(
            id="run-multi-qual",
            batch_run_id="batch-multi-qual",
            implementation_id="default",
            configuration_slug="refinement-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "node_id": "class-456",
                "candidates": [
                    {"definition": "Definition A", "confidence": 0.92},
                    {"definition": "Definition B", "confidence": 0.95},
                    {"definition": "Definition C", "confidence": 0.88},
                ],
            },
        )

        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaDefinitionRefinementApplyService(mock_ontology_repo)

        result = service.apply(run, confidence_threshold=0.85)

        assert result.classes_updated == 1

        saved_class = mock_ontology_repo.save_class.call_args[0][0]
        assert saved_class.description == "Definition B"

    def test_exact_threshold_boundary(self, mock_ontology_repo, sample_class):
        """Threshold exact boundary: >= threshold included, < threshold excluded."""
        run = PipelineRun(
            id="run-boundary",
            batch_run_id="batch-boundary",
            implementation_id="default",
            configuration_slug="refinement-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "node_id": "class-456",
                "candidates": [
                    {"definition": "Definition A", "confidence": 0.8},
                    {"definition": "Definition B", "confidence": 0.85},
                ],
            },
        )

        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaDefinitionRefinementApplyService(mock_ontology_repo)

        result = service.apply(run, confidence_threshold=0.85)

        assert result.classes_updated == 1
        saved_class = mock_ontology_repo.save_class.call_args[0][0]
        assert saved_class.description == "Definition B"

    def test_idempotent_apply(self, mock_ontology_repo, sample_class):
        """Re-applying the same run overwrites with the same value (idempotent)."""
        run = PipelineRun(
            id="run-idem",
            batch_run_id="batch-idem",
            implementation_id="default",
            configuration_slug="refinement-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "node_id": "class-456",
                "candidates": [
                    {"definition": "New Definition", "confidence": 0.95},
                ],
            },
        )

        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaDefinitionRefinementApplyService(mock_ontology_repo)

        # First apply
        result1 = service.apply(run)
        assert result1.classes_updated == 1

        # Second apply with same run
        result2 = service.apply(run)
        assert result2.classes_updated == 1

    def test_zero_confidence_accepted_with_default_threshold(
        self, mock_ontology_repo, sample_class
    ):
        """Zero confidence is accepted when threshold is 0.0."""
        run = PipelineRun(
            id="run-zero-conf",
            batch_run_id="batch-zero-conf",
            implementation_id="default",
            configuration_slug="refinement-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "node_id": "class-456",
                "candidates": [
                    {"definition": "Zero confidence definition", "confidence": 0.0},
                ],
            },
        )

        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaDefinitionRefinementApplyService(mock_ontology_repo)

        result = service.apply(run, confidence_threshold=0.0)

        assert result.classes_updated == 1
