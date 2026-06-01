"""
Unit tests for ApplyResult ID tracking across all five apply services.

Tests that:
1. ApplyResult populates created_*_ids lists correctly
2. Each created entity is tracked with its ID
3. Counts match list lengths
"""

import os
import sys
from unittest.mock import MagicMock

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )))
)

import pytest

from domain.ontology.entities import Class, ConceptScheme, PropertyDefinition, Taxonomy
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.individual_extraction.apply_service import (
    IndividualExtractionApplyService,
)
from domain.pipelines.schema_extraction.apply_service import SchemaExtractionApplyService
from domain.pipelines.schema_node_connection_refinement.apply_service import (
    SchemaConnectionRefinementApplyService,
)
from domain.pipelines.schema_node_definition_refinement.apply_service import (
    SchemaDefinitionRefinementApplyService,
)
from domain.pipelines.schema_node_grounding.apply_service import (
    SchemaGroundingApplyService,
)
from tests.fakes.fake_ontology_repository import FakeOntologyRepository

# ============================================================================
# Fixtures
# ============================================================================


TAXONOMY_ID = "tx-1"
SCHEME_ID = "cs-1"
CLASS_ID = "cls-person"


@pytest.fixture()
def repo():
    r = FakeOntologyRepository()
    r.save_taxonomy(Taxonomy(id=TAXONOMY_ID, identifier="test_tax", title="Test Taxonomy"))
    r.save_concept_scheme(
        ConceptScheme(
            id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            identifier="test_scheme",
            title="Test Scheme",
        )
    )
    r.save_class(
        Class(
            id=CLASS_ID,
            concept_scheme_id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            identifier="cls_test",
            title="Person",
        )
    )
    return r


# ============================================================================
# IndividualExtractionApplyService: ID tracking tests
# ============================================================================


def test_individual_extraction_tracks_created_individual_ids(repo):
    """Individual creation populates created_individual_ids list."""
    svc = IndividualExtractionApplyService(repo)
    run = MagicMock()
    run.id = "run-1"
    run.pipeline_type = PipelineType.INDIVIDUAL_EXTRACTION
    run.status = PipelineRunStatus.COMPLETED
    run.output_summary = {
        "triples": [
            {
                "subject": {
                    "kind": "individual",
                    "label": "Alice",
                    "class_ids": [CLASS_ID],
                },
                "confidence": 0.9,
            },
            {
                "subject": {
                    "kind": "individual",
                    "label": "Bob",
                    "class_ids": [CLASS_ID],
                },
                "confidence": 0.9,
            },
        ]
    }

    result = svc.apply(run)

    assert len(result.created_individual_ids) == 2
    assert result.individuals_created == 2
    assert len(result.created_individual_ids) == result.individuals_created
    # Verify IDs are valid
    for ind_id in result.created_individual_ids:
        individual = repo.get_individual(ind_id)
        assert individual is not None


def test_individual_extraction_tracks_created_relationship_ids(repo):
    """Relationship creation populates created_relationship_ids list."""
    prop = PropertyDefinition(
        id="prop-1",
        identifier="knows",
        title="Knows",
    )
    repo.save_property_definition(prop)

    svc = IndividualExtractionApplyService(repo)
    run = MagicMock()
    run.id = "run-1"
    run.pipeline_type = PipelineType.INDIVIDUAL_EXTRACTION
    run.status = PipelineRunStatus.COMPLETED
    run.output_summary = {
        "triples": [
            {
                "subject": {
                    "kind": "individual",
                    "label": "Alice",
                    "class_ids": [CLASS_ID],
                },
                "predicate": {"property_definition_id": "prop-1"},
                "object": {"kind": "individual", "id": "ind-bob"},
                "confidence": 0.9,
            }
        ]
    }

    # Pre-create the target individual
    from domain.ontology.entities import Individual

    bob = Individual(id="ind-bob", class_ids=[CLASS_ID], title="Bob")
    repo.save_individual(bob)

    result = svc.apply(run)

    assert len(result.created_relationship_ids) == 1
    assert result.relationships_created == 1
    rel_id = result.created_relationship_ids[0]
    rel = repo.get_relationship(rel_id)
    assert rel is not None


# ============================================================================
# SchemaExtractionApplyService: ID tracking tests
# ============================================================================


def test_schema_extraction_tracks_created_class_ids(repo):
    """Class creation populates created_class_ids list."""
    svc = SchemaExtractionApplyService(repo)
    run = MagicMock()
    run.id = "run-1"
    run.pipeline_type = PipelineType.SCHEMA_EXTRACTION
    run.status = PipelineRunStatus.COMPLETED
    run.output_summary = {
        "candidates": [
            {"kind": "class", "label": "Animal", "confidence": 0.9},
            {"kind": "class", "label": "Plant", "confidence": 0.9},
        ],
        "connections": [],
    }

    result = svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)

    assert len(result.created_class_ids) == 2
    assert result.classes_created == 2
    for cls_id in result.created_class_ids:
        cls = repo.get_class(cls_id)
        assert cls is not None


def test_schema_extraction_tracks_created_property_definition_ids(repo):
    """PropertyDefinition creation populates created_property_definition_ids list."""
    svc = SchemaExtractionApplyService(repo)
    run = MagicMock()
    run.id = "run-1"
    run.pipeline_type = PipelineType.SCHEMA_EXTRACTION
    run.status = PipelineRunStatus.COMPLETED
    run.output_summary = {
        "candidates": [
            {"kind": "property_definition", "label": "Has Color", "confidence": 0.9},
            {"kind": "property_definition", "label": "Defines", "confidence": 0.9},
        ],
        "connections": [],
    }

    result = svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)

    assert len(result.created_property_definition_ids) == 2
    assert result.properties_created == 2
    for prop_id in result.created_property_definition_ids:
        prop = repo.get_property_definition(prop_id)
        assert prop is not None


# ============================================================================
# SchemaGroundingApplyService: ID tracking tests
# ============================================================================


def test_schema_grounding_tracks_external_reference_ids(repo):
    """External reference creation populates created_external_reference_ids list."""
    svc = SchemaGroundingApplyService(repo)
    run = MagicMock()
    run.id = "run-1"
    run.pipeline_type = PipelineType.SCHEMA_NODE_GROUNDING
    run.status = PipelineRunStatus.COMPLETED
    run.output_summary = {
        "groundings": [
            {"uri": "http://example.com/person", "source": "test", "match_confidence": 0.95},
            {"uri": "http://example.com/homo-sapiens", "source": "test", "match_confidence": 0.90},
        ]
    }

    result = svc.apply(run, node_id=CLASS_ID)

    assert len(result.created_external_reference_ids) == 2
    assert result.external_references_created == 2
    # Verify URIs are tracked
    assert "http://example.com/person" in result.created_external_reference_ids
    assert "http://example.com/homo-sapiens" in result.created_external_reference_ids
    # Verify external references are on the class
    cls = repo.get_class(CLASS_ID)
    assert len(cls.external_references) == 2


# ============================================================================
# Accounting Tests (regression)
# ============================================================================


def test_schema_definition_refinement_increments_classes_updated_not_created(repo):
    """Updating a class increments classes_updated, not classes_created."""
    svc = SchemaDefinitionRefinementApplyService(repo)
    run = MagicMock()
    run.id = "run-1"
    run.pipeline_type = PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT
    run.status = PipelineRunStatus.COMPLETED
    run.output_summary = {
        "node_id": CLASS_ID,
        "candidates": [
            {"definition": "A human being", "confidence": 0.95}
        ]
    }

    result = svc.apply(run)

    assert result.classes_updated == 1
    assert result.classes_created == 0
    assert result.classes_skipped == 0
    # Verify the class was actually updated
    cls = repo.get_class(CLASS_ID)
    assert cls.description == "A human being"


def test_schema_connection_refinement_separates_operations(repo):
    """Connection refinement separates add/remove/modify into distinct fields."""
    # Create classes and property for testing
    cls1 = Class(
        id="cls-animal",
        concept_scheme_id=SCHEME_ID,
        taxonomy_id=TAXONOMY_ID,
        title="Animal",
    )
    cls2 = Class(
        id="cls-dog",
        concept_scheme_id=SCHEME_ID,
        taxonomy_id=TAXONOMY_ID,
        title="Dog",
    )
    repo.save_class(cls1)
    repo.save_class(cls2)

    prop_is = PropertyDefinition(id="prop-is", identifier="is_a", title="Is A")
    prop_likes = PropertyDefinition(id="prop-likes", identifier="likes", title="Likes")
    repo.save_property_definition(prop_is)
    repo.save_property_definition(prop_likes)

    from domain.ontology.entities import Relationship
    rel_is = Relationship(
        id="rel-1",
        source_id="cls-dog",
        target_id="cls-animal",
        property_definition_id="prop-is",
    )
    rel_likes = Relationship(
        id="rel-2",
        source_id="cls-dog",
        target_id="cls-animal",
        property_definition_id="prop-likes",
    )
    repo.save_relationship(rel_is)
    repo.save_relationship(rel_likes)

    svc = SchemaConnectionRefinementApplyService(repo)
    run = MagicMock()
    run.id = "run-1"
    run.pipeline_type = PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT
    run.status = PipelineRunStatus.COMPLETED
    run.output_summary = {
        "scope_id": SCHEME_ID,
        "deltas": [
            {
                "operation": "add",
                "subject": "Dog",
                "predicate": "knows",
                "object": "Animal",
                "confidence": 0.9,
            },
            {
                "operation": "remove",
                "subject": "Dog",
                "predicate": "is_a",
                "object": "Animal",
                "confidence": 0.9,
            },
            {
                "operation": "modify",
                "subject": "Dog",
                "predicate": "likes",
                "object": "Animal",
                "confidence": 0.9,
            },
        ]
    }

    result = svc.apply(run)

    # Note: add fails because "knows" property doesn't exist, remove succeeds, modify succeeds
    assert result.relationships_removed == 1
    assert result.relationships_modified == 1
    assert result.relationships_skipped == 1


def test_schema_grounding_uses_external_references_created(repo):
    """Grounding uses external_references_created, not relationships_created."""
    svc = SchemaGroundingApplyService(repo)
    run = MagicMock()
    run.id = "run-1"
    run.pipeline_type = PipelineType.SCHEMA_NODE_GROUNDING
    run.status = PipelineRunStatus.COMPLETED
    run.output_summary = {
        "groundings": [
            {"uri": "http://example.com/test", "source": "test", "match_confidence": 0.95}
        ]
    }

    result = svc.apply(run, node_id=CLASS_ID)

    assert result.external_references_created == 1
    assert result.relationships_created == 0
    assert result.external_references_skipped == 0


# ============================================================================
# ApplyResult Validation Tests
# ============================================================================


class TestApplyResultValidation:
    """Tests for ApplyResult count/ID consistency validation."""

    def test_apply_result_rejects_classes_created_without_ids(self):
        """ApplyResult rejects classes_created > 0 with empty created_class_ids."""
        from domain.pipelines.apply_result import ApplyResult

        with pytest.raises(ValueError, match="classes_created.*created_class_ids.*must be consistent"):
            ApplyResult(
                classes_created=5,
                created_class_ids=[],  # Inconsistent
            )

    def test_apply_result_rejects_classes_ids_without_count(self):
        """ApplyResult rejects created_class_ids with classes_created = 0."""
        from domain.pipelines.apply_result import ApplyResult

        with pytest.raises(ValueError, match="classes_created.*created_class_ids.*must be consistent"):
            ApplyResult(
                classes_created=0,
                created_class_ids=["cls-1", "cls-2"],  # Inconsistent
            )

    def test_apply_result_accepts_matching_classes(self):
        """ApplyResult accepts consistent classes_created and created_class_ids."""
        from domain.pipelines.apply_result import ApplyResult

        result = ApplyResult(
            classes_created=2,
            created_class_ids=["cls-1", "cls-2"],
        )
        assert result.classes_created == 2
        assert len(result.created_class_ids) == 2

    def test_apply_result_accepts_zero_classes(self):
        """ApplyResult accepts classes_created = 0 with empty created_class_ids."""
        from domain.pipelines.apply_result import ApplyResult

        result = ApplyResult(
            classes_created=0,
            created_class_ids=[],
        )
        assert result.classes_created == 0
        assert len(result.created_class_ids) == 0

    def test_apply_result_rejects_individuals_created_without_ids(self):
        """ApplyResult rejects individuals_created > 0 with empty created_individual_ids."""
        from domain.pipelines.apply_result import ApplyResult

        with pytest.raises(ValueError, match="individuals_created.*created_individual_ids.*must be consistent"):
            ApplyResult(
                individuals_created=3,
                created_individual_ids=[],  # Inconsistent
            )

    def test_apply_result_rejects_relationships_created_without_ids(self):
        """ApplyResult rejects relationships_created > 0 with empty created_relationship_ids."""
        from domain.pipelines.apply_result import ApplyResult

        with pytest.raises(ValueError, match="relationships_created.*created_relationship_ids.*must be consistent"):
            ApplyResult(
                relationships_created=2,
                created_relationship_ids=[],  # Inconsistent
            )

    def test_apply_result_rejects_properties_created_without_ids(self):
        """ApplyResult rejects properties_created > 0 with empty created_property_definition_ids."""
        from domain.pipelines.apply_result import ApplyResult

        with pytest.raises(ValueError, match="properties_created.*created_property_definition_ids.*must be consistent"):
            ApplyResult(
                properties_created=1,
                created_property_definition_ids=[],  # Inconsistent
            )

    def test_apply_result_rejects_external_references_without_ids(self):
        """ApplyResult rejects external_references_created > 0 with empty created_external_reference_ids."""
        from domain.pipelines.apply_result import ApplyResult

        with pytest.raises(ValueError, match="external_references_created.*created_external_reference_ids.*must be consistent"):
            ApplyResult(
                external_references_created=1,
                created_external_reference_ids=[],  # Inconsistent
            )

    def test_apply_result_allows_other_counts_without_id_lists(self):
        """ApplyResult allows other counts (skipped, updated, removed) without restrictions."""
        from domain.pipelines.apply_result import ApplyResult

        # These should all be fine - skipped/updated/removed don't require ID lists
        result = ApplyResult(
            classes_skipped=5,
            classes_updated=3,
            relationships_removed=2,
            individuals_skipped=4,
        )
        assert result.classes_skipped == 5
        assert result.classes_updated == 3
