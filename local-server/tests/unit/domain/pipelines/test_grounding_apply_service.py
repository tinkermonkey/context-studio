"""
Unit tests for SchemaGroundingApplyService.

Tests cover URI deduplication, confidence thresholds, edge cases,
and correct ApplyResult tracking.
"""

from unittest.mock import Mock

import pytest

from domain.ontology.entities import Class
from domain.ontology.value_objects import ExternalReference
from domain.pipelines.entities import PipelineRun, PipelineRunStatus
from domain.pipelines.schema_node_grounding.apply_service import (
    SchemaGroundingApplyService,
)


@pytest.fixture
def mock_ontology_repo():
    """Create a mock ontology repository."""
    return Mock()


@pytest.fixture
def sample_class():
    """Create a sample Class entity for testing."""
    return Class(
        id="class-123",
        concept_scheme_id="scheme-1",
        taxonomy_id="tax-1",
        title="Microservice",
        description="A service architecture pattern",
        external_references=[
            ExternalReference(
                source="wikidata",
                identifier="https://www.wikidata.org/wiki/Q12345",
                uri="https://www.wikidata.org/wiki/Q12345",
            )
        ],
    )


@pytest.fixture
def sample_pipeline_run():
    """Create a sample completed grounding PipelineRun."""
    return PipelineRun(
        id="run-123",
        batch_run_id="batch-123",
        implementation_id="default",
        configuration_slug="grounding-default",
        configuration_version=1,
        status=PipelineRunStatus.COMPLETED,
        output_summary={
            "groundings": [
                {
                    "uri": "https://www.wikidata.org/wiki/Q123",
                    "source": "wikidata",
                    "match_confidence": 0.95,
                },
                {
                    "uri": "https://dbpedia.org/resource/Service",
                    "source": "dbpedia",
                    "match_confidence": 0.85,
                },
                {
                    "uri": "https://schema.org/Service",
                    "source": "schema.org",
                    "match_confidence": 0.75,
                },
            ]
        },
    )


class TestSchemaGroundingApplyServiceBasic:
    """Basic functionality tests for grounding apply service."""

    def test_apply_with_valid_groundings(
        self, mock_ontology_repo, sample_class, sample_pipeline_run
    ):
        """Applying groundings creates new external references."""
        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaGroundingApplyService(mock_ontology_repo)

        result = service.apply(sample_pipeline_run, sample_class.id)

        # Should have created 3 new external references (Q123, dbpedia, schema.org)
        # The sample class has Q12345 which doesn't match any run groundings
        assert result.external_references_created == 3
        assert result.external_references_skipped == 0
        assert len(result.created_external_reference_ids) == 3

        # Verify repository was called to save the class
        mock_ontology_repo.save_class.assert_called_once()

    def test_uri_deduplication(self, mock_ontology_repo):
        """Duplicate URIs are not added twice."""
        # Create a class with one existing reference
        # Note: the service sets identifier=uri, so they should match
        cls = Class(
            id="class-dup",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Microservice",
            description="A service architecture pattern",
            external_references=[
                ExternalReference(
                    source="wikidata",
                    identifier="https://www.wikidata.org/wiki/Q12345",
                    uri="https://www.wikidata.org/wiki/Q12345",
                )
            ],
        )

        # Create a fresh run with a duplicate URI
        run = PipelineRun(
            id="run-dup",
            batch_run_id="batch-dup",
            implementation_id="default",
            configuration_slug="grounding-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "groundings": [
                    {
                        "uri": "https://www.wikidata.org/wiki/Q123",
                        "source": "wikidata",
                        "match_confidence": 0.95,
                    },
                    {
                        "uri": "https://dbpedia.org/resource/Service",
                        "source": "dbpedia",
                        "match_confidence": 0.85,
                    },
                    {
                        "uri": "https://schema.org/Service",
                        "source": "schema.org",
                        "match_confidence": 0.75,
                    },
                    {
                        "uri": "https://www.wikidata.org/wiki/Q12345",
                        "source": "wikidata",
                        "match_confidence": 0.95,
                    },
                ]
            },
        )

        mock_ontology_repo.get_class.return_value = cls
        service = SchemaGroundingApplyService(mock_ontology_repo)

        result = service.apply(run, cls.id)

        # Should skip the duplicate URI
        assert result.external_references_created == 3
        assert result.external_references_skipped == 1

    def test_confidence_threshold_filtering(
        self, mock_ontology_repo, sample_class, sample_pipeline_run
    ):
        """Groundings below confidence threshold are skipped."""
        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaGroundingApplyService(mock_ontology_repo)

        result = service.apply(
            sample_pipeline_run, sample_class.id, confidence_threshold=0.90
        )

        # Only groundings with confidence >= 0.90 should be created (first and second)
        assert result.external_references_created == 1
        assert result.external_references_skipped == 2

    def test_empty_groundings_list(self, mock_ontology_repo, sample_class):
        """Applying with no groundings results in no changes."""
        run = PipelineRun(
            id="run-456",
            batch_run_id="batch-456",
            implementation_id="default",
            configuration_slug="grounding-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={"groundings": []},
        )

        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaGroundingApplyService(mock_ontology_repo)

        result = service.apply(run, sample_class.id)

        assert result.external_references_created == 0
        assert result.external_references_skipped == 0
        # Should not save if nothing created
        mock_ontology_repo.save_class.assert_not_called()

    def test_missing_node_id_raises_error(self, mock_ontology_repo):
        """Missing node_id raises ValueError."""
        service = SchemaGroundingApplyService(mock_ontology_repo)
        run = PipelineRun(
            id="run-789",
            batch_run_id="batch-789",
            implementation_id="default",
            configuration_slug="grounding-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={"groundings": []},
        )

        with pytest.raises(ValueError, match="node_id is required"):
            service.apply(run, "")

    def test_class_not_found_raises_error(self, mock_ontology_repo):
        """Non-existent class raises ValueError."""
        mock_ontology_repo.get_class.return_value = None
        service = SchemaGroundingApplyService(mock_ontology_repo)
        run = PipelineRun(
            id="run-999",
            batch_run_id="batch-999",
            implementation_id="default",
            configuration_slug="grounding-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={"groundings": []},
        )

        with pytest.raises(ValueError, match="not found"):
            service.apply(run, "nonexistent-id")


class TestSchemaGroundingApplyServiceEdgeCases:
    """Edge case tests for grounding apply service."""

    def test_whitespace_only_uri_is_skipped(self, mock_ontology_repo, sample_class):
        """URIs with only whitespace are treated as empty."""
        run = PipelineRun(
            id="run-ws",
            batch_run_id="batch-ws",
            implementation_id="default",
            configuration_slug="grounding-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "groundings": [
                    {"uri": "   ", "source": "test", "match_confidence": 0.95},
                ]
            },
        )

        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaGroundingApplyService(mock_ontology_repo)

        result = service.apply(run, sample_class.id)

        assert result.external_references_created == 0
        assert result.external_references_skipped == 1

    def test_missing_uri_field_is_skipped(self, mock_ontology_repo, sample_class):
        """Groundings without a URI field are skipped."""
        run = PipelineRun(
            id="run-no-uri",
            batch_run_id="batch-no-uri",
            implementation_id="default",
            configuration_slug="grounding-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "groundings": [
                    {"source": "test", "match_confidence": 0.95},  # no uri
                ]
            },
        )

        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaGroundingApplyService(mock_ontology_repo)

        result = service.apply(run, sample_class.id)

        assert result.external_references_created == 0
        assert result.external_references_skipped == 1

    def test_missing_confidence_defaults_to_zero(
        self, mock_ontology_repo, sample_class
    ):
        """Missing confidence field defaults to 0.0."""
        run = PipelineRun(
            id="run-no-conf",
            batch_run_id="batch-no-conf",
            implementation_id="default",
            configuration_slug="grounding-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "groundings": [
                    {
                        "uri": "https://example.org/test",
                        "source": "test",
                        # no match_confidence
                    },
                ]
            },
        )

        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaGroundingApplyService(mock_ontology_repo)

        result = service.apply(run, sample_class.id, confidence_threshold=0.1)

        assert result.external_references_created == 0
        assert result.external_references_skipped == 1

    def test_zero_confidence_accepted_with_default_threshold(
        self, mock_ontology_repo, sample_class
    ):
        """Zero confidence is accepted when threshold is 0.0."""
        run = PipelineRun(
            id="run-zero-conf",
            batch_run_id="batch-zero-conf",
            implementation_id="default",
            configuration_slug="grounding-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "groundings": [
                    {
                        "uri": "https://example.org/test",
                        "source": "test",
                        "match_confidence": 0.0,
                    },
                ]
            },
        )

        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaGroundingApplyService(mock_ontology_repo)

        result = service.apply(run, sample_class.id, confidence_threshold=0.0)

        assert result.external_references_created == 1
        assert result.external_references_skipped == 0

    def test_missing_source_field_defaults_to_unknown(
        self, mock_ontology_repo, sample_class
    ):
        """Missing source field defaults to 'unknown'."""
        run = PipelineRun(
            id="run-no-source",
            batch_run_id="batch-no-source",
            implementation_id="default",
            configuration_slug="grounding-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "groundings": [
                    {
                        "uri": "https://example.org/test",
                        # no source
                        "match_confidence": 0.95,
                    },
                ]
            },
        )

        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaGroundingApplyService(mock_ontology_repo)

        result = service.apply(run, sample_class.id)

        assert result.external_references_created == 1
        # Verify the created reference has the default source
        saved_class = mock_ontology_repo.save_class.call_args[0][0]
        new_refs = [
            ref for ref in saved_class.external_references if ref.source == "unknown"
        ]
        assert len(new_refs) > 0

    def test_apply_result_created_ids_tracking(
        self, mock_ontology_repo, sample_class, sample_pipeline_run
    ):
        """ApplyResult correctly tracks created_external_reference_ids."""
        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaGroundingApplyService(mock_ontology_repo)

        result = service.apply(sample_pipeline_run, sample_class.id)

        assert len(result.created_external_reference_ids) == 3
        assert (
            "https://www.wikidata.org/wiki/Q123"
            in result.created_external_reference_ids
        )
        assert (
            "https://dbpedia.org/resource/Service"
            in result.created_external_reference_ids
        )
        assert "https://schema.org/Service" in result.created_external_reference_ids

    def test_threshold_exact_boundary(
        self, mock_ontology_repo, sample_class, sample_pipeline_run
    ):
        """Threshold exact boundary: >= threshold included, < threshold excluded."""
        mock_ontology_repo.get_class.return_value = sample_class
        service = SchemaGroundingApplyService(mock_ontology_repo)

        result = service.apply(
            sample_pipeline_run, sample_class.id, confidence_threshold=0.85
        )

        # confidence 0.95 (included), 0.85 (included), 0.75 (excluded)
        assert result.external_references_created == 2
        assert result.external_references_skipped == 1
