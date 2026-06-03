"""
Unit tests for SchemaConnectionRefinementApplyService.

Tests cover class resolution (by ID and label), self-loop prevention,
three-way operation handling (add/remove/modify), confidence thresholds,
and property definition resolution via slugification.
"""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from domain.ontology.entities import Class, PropertyDefinition, Relationship
from domain.pipelines.entities import PipelineRun, PipelineRunStatus
from domain.pipelines.schema_node_connection_refinement.apply_service import (
    SchemaConnectionRefinementApplyService,
)


@pytest.fixture
def mock_ontology_repo():
    """Create a mock ontology repository."""
    repo = Mock()
    # Default behavior: no relationships exist
    repo.list_relationships.return_value = []
    # Default behavior: no classes in scope
    repo.list_classes.return_value = []
    return repo


@pytest.fixture
def sample_classes():
    """Create sample Class entities for testing."""
    return {
        "microservice": Class(
            id="class-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Microservice",
            description="",
        ),
        "service": Class(
            id="class-2",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Service",
            description="",
        ),
        "api": Class(
            id="class-3",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="API",
            description="",
        ),
    }


@pytest.fixture
def sample_property_definition():
    """Create a sample PropertyDefinition."""
    return PropertyDefinition(
        id="prop-1",
        identifier="depends_on",
        title="depends on",
        description="indicates a dependency",
    )


@pytest.fixture
def sample_scope_id():
    """Create a scope ID."""
    return str(uuid4())


class TestSchemaConnectionRefinementApplyServiceBasic:
    """Basic functionality tests for connection refinement apply service."""

    def test_add_operation_creates_new_relationship(
        self,
        mock_ontology_repo,
        sample_classes,
        sample_property_definition,
        sample_scope_id,
    ):
        """Add operation creates a new relationship."""

        # Setup mocks
        def get_class_side_effect(ref):
            return sample_classes.get(ref.lower()) if ref.lower() in sample_classes else None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.list_relationships.return_value = []
        mock_ontology_repo.get_property_definition_by_identifier.return_value = (
            sample_property_definition
        )
        mock_ontology_repo.list_classes.return_value = list(sample_classes.values())

        run = PipelineRun(
            id="run-add",
            batch_run_id="batch-add",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "add",
                        "subject": "Microservice",
                        "predicate": "depends on",
                        "object": "Service",
                        "confidence": 0.95,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run)

        assert result.relationships_created == 1
        assert result.relationships_skipped == 0
        mock_ontology_repo.save_relationship.assert_called_once()

    def test_remove_operation_deletes_existing_relationship(
        self,
        mock_ontology_repo,
        sample_classes,
        sample_property_definition,
        sample_scope_id,
    ):
        """Remove operation deletes an existing relationship."""
        existing_rel = Relationship(
            id="rel-1",
            source_id="class-1",
            target_id="class-2",
            property_definition_id="prop-1",
            source_run_id="run-orig",
        )

        def get_class_side_effect(ref):
            return sample_classes.get(ref.lower()) if ref.lower() in sample_classes else None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.list_relationships.return_value = [existing_rel]
        mock_ontology_repo.get_property_definition_by_identifier.return_value = (
            sample_property_definition
        )
        mock_ontology_repo.list_classes.return_value = list(sample_classes.values())

        run = PipelineRun(
            id="run-remove",
            batch_run_id="batch-remove",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "remove",
                        "subject": "Microservice",
                        "predicate": "depends on",
                        "object": "Service",
                        "confidence": 0.95,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run)

        assert result.relationships_removed == 1
        assert result.relationships_skipped == 0
        mock_ontology_repo.delete_relationship.assert_called_once_with("rel-1")

    def test_modify_operation_tracks_without_applying(
        self,
        mock_ontology_repo,
        sample_classes,
        sample_property_definition,
        sample_scope_id,
    ):
        """Modify operation tracks count but doesn't apply (structure incomplete)."""
        existing_rel = Relationship(
            id="rel-1",
            source_id="class-1",
            target_id="class-2",
            property_definition_id="prop-1",
            source_run_id="run-orig",
        )

        def get_class_side_effect(ref):
            return sample_classes.get(ref.lower()) if ref.lower() in sample_classes else None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.list_relationships.return_value = [existing_rel]
        mock_ontology_repo.get_property_definition_by_identifier.return_value = (
            sample_property_definition
        )
        mock_ontology_repo.list_classes.return_value = list(sample_classes.values())

        run = PipelineRun(
            id="run-modify",
            batch_run_id="batch-modify",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "modify",
                        "subject": "Microservice",
                        "predicate": "depends on",
                        "object": "Service",
                        "confidence": 0.95,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run)

        assert result.relationships_modified == 1
        assert result.relationships_skipped == 0
        # Modify should not save or delete
        mock_ontology_repo.save_relationship.assert_not_called()
        mock_ontology_repo.delete_relationship.assert_not_called()

    def test_self_loop_prevention(
        self,
        mock_ontology_repo,
        sample_classes,
        sample_property_definition,
        sample_scope_id,
    ):
        """Self-loops are prevented (source == target)."""

        def get_class_side_effect(ref):
            if ref.lower() == "microservice":
                return sample_classes["microservice"]
            return None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.get_property_definition_by_identifier.return_value = (
            sample_property_definition
        )

        run = PipelineRun(
            id="run-self-loop",
            batch_run_id="batch-self-loop",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "add",
                        "subject": "Microservice",
                        "predicate": "depends on",
                        "object": "Microservice",
                        "confidence": 0.95,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run)

        assert result.relationships_created == 0
        assert result.relationships_skipped == 1
        mock_ontology_repo.save_relationship.assert_not_called()

    def test_confidence_threshold_filtering(
        self,
        mock_ontology_repo,
        sample_classes,
        sample_property_definition,
        sample_scope_id,
    ):
        """Deltas below confidence threshold are skipped."""

        def get_class_side_effect(ref):
            return sample_classes.get(ref.lower()) if ref.lower() in sample_classes else None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.list_relationships.return_value = []
        mock_ontology_repo.get_property_definition_by_identifier.return_value = (
            sample_property_definition
        )

        run = PipelineRun(
            id="run-threshold",
            batch_run_id="batch-threshold",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "add",
                        "subject": "Microservice",
                        "predicate": "depends on",
                        "object": "Service",
                        "confidence": 0.75,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run, confidence_threshold=0.90)

        assert result.relationships_created == 0
        assert result.relationships_skipped == 1
        mock_ontology_repo.save_relationship.assert_not_called()


class TestSchemaConnectionRefinementApplyServiceResolution:
    """Tests for class and property resolution."""

    def test_class_resolution_by_id(
        self,
        mock_ontology_repo,
        sample_classes,
        sample_property_definition,
        sample_scope_id,
    ):
        """Class references resolved by ID take precedence."""

        def get_class_side_effect(ref):
            if ref == "class-1":
                return sample_classes["microservice"]
            elif ref.lower() == "service":
                return sample_classes["service"]
            return None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.list_relationships.return_value = []
        mock_ontology_repo.get_property_definition_by_identifier.return_value = (
            sample_property_definition
        )

        run = PipelineRun(
            id="run-by-id",
            batch_run_id="batch-by-id",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "add",
                        "subject": "class-1",  # ID, not label
                        "predicate": "depends on",
                        "object": "Service",
                        "confidence": 0.95,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run)

        # Should create because resolution by ID succeeds
        assert result.relationships_created == 1

    def test_class_resolution_by_label(
        self,
        mock_ontology_repo,
        sample_classes,
        sample_property_definition,
        sample_scope_id,
    ):
        """Class references resolved by label when ID lookup fails."""

        def get_class_side_effect(ref):
            # First attempt (direct ID) fails
            return None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.list_relationships.return_value = []
        mock_ontology_repo.get_property_definition_by_identifier.return_value = (
            sample_property_definition
        )
        mock_ontology_repo.list_classes.return_value = list(sample_classes.values())

        run = PipelineRun(
            id="run-by-label",
            batch_run_id="batch-by-label",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "add",
                        "subject": "Microservice",  # Label, not ID
                        "predicate": "depends on",
                        "object": "Service",  # Label
                        "confidence": 0.95,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run)

        # Should create because resolution by label succeeds
        assert result.relationships_created == 1

    def test_property_definition_resolution_via_slugification(
        self,
        mock_ontology_repo,
        sample_classes,
        sample_property_definition,
        sample_scope_id,
    ):
        """Property definition resolved via slugification of predicate label."""

        def get_class_side_effect(ref):
            return sample_classes.get(ref.lower()) if ref.lower() in sample_classes else None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.list_relationships.return_value = []
        # Should be called with slugified predicate
        mock_ontology_repo.get_property_definition_by_identifier.return_value = (
            sample_property_definition
        )

        run = PipelineRun(
            id="run-slug",
            batch_run_id="batch-slug",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "add",
                        "subject": "Microservice",
                        "predicate": "Depends On",  # Should be slugified to "depends_on"
                        "object": "Service",
                        "confidence": 0.95,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run)

        assert result.relationships_created == 1
        # Verify slugification was used
        mock_ontology_repo.get_property_definition_by_identifier.assert_called_with("depends_on")

    def test_unresolvable_class_skips_delta(
        self, mock_ontology_repo, sample_property_definition, sample_scope_id
    ):
        """Delta skipped if class cannot be resolved."""
        mock_ontology_repo.get_class.return_value = None
        mock_ontology_repo.list_classes.return_value = []

        run = PipelineRun(
            id="run-unresolvable",
            batch_run_id="batch-unresolvable",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "add",
                        "subject": "UnknownClass",
                        "predicate": "depends on",
                        "object": "AnotherUnknown",
                        "confidence": 0.95,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run)

        assert result.relationships_created == 0
        assert result.relationships_skipped == 1

    def test_unresolvable_property_skips_delta(
        self, mock_ontology_repo, sample_classes, sample_scope_id
    ):
        """Delta skipped if property definition cannot be resolved."""

        def get_class_side_effect(ref):
            return sample_classes.get(ref.lower()) if ref.lower() in sample_classes else None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.get_property_definition_by_identifier.return_value = None

        run = PipelineRun(
            id="run-no-prop",
            batch_run_id="batch-no-prop",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "add",
                        "subject": "Microservice",
                        "predicate": "unknown_predicate",
                        "object": "Service",
                        "confidence": 0.95,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run)

        assert result.relationships_created == 0
        assert result.relationships_skipped == 1


class TestSchemaConnectionRefinementApplyServiceScoping:
    """Tests for scope-based class resolution."""

    def test_scoped_class_lookup_prevents_title_collision(
        self,
        mock_ontology_repo,
        sample_property_definition,
        sample_scope_id,
    ):
        """Classes with same title in different schemes resolve to correct scheme."""
        # Create the scope class (this is the node being refined)
        scheme_id = "concept-scheme-1"
        scope_class = Class(
            id=sample_scope_id,
            concept_scheme_id=scheme_id,
            taxonomy_id="tax-1",
            title="Scope",
            description="The scope class being refined",
        )

        # Create two classes with the same title in different concept schemes
        class_in_scope = Class(
            id="class-scope-1",
            concept_scheme_id=scheme_id,
            taxonomy_id="tax-1",
            title="Service",
            description="Service in the target scheme",
        )
        class_in_other_scheme = Class(
            id="class-other-1",
            concept_scheme_id="other-scheme-id",
            taxonomy_id="tax-1",
            title="Service",  # Same title, different scheme
            description="Service in a different scheme",
        )
        class_in_scope_2 = Class(
            id="class-scope-2",
            concept_scheme_id=scheme_id,
            taxonomy_id="tax-1",
            title="API",
            description="API in the target scheme",
        )

        def get_class_side_effect(ref):
            # ID-based lookup
            if ref == sample_scope_id:
                return scope_class
            elif ref == "class-scope-1":
                return class_in_scope
            elif ref == "class-scope-2":
                return class_in_scope_2
            # Label-based lookup would need a different mechanism
            return None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.list_relationships.return_value = []
        mock_ontology_repo.get_property_definition_by_identifier.return_value = (
            sample_property_definition
        )

        # When filtering by concept_scheme_id, return only classes in that scheme
        def list_classes_side_effect(concept_scheme_id=None, limit=None, **kwargs):
            if concept_scheme_id == scheme_id:
                return [scope_class, class_in_scope, class_in_scope_2]
            elif concept_scheme_id == "other-scheme-id":
                return [class_in_other_scheme]
            return [scope_class, class_in_scope, class_in_scope_2, class_in_other_scheme]

        mock_ontology_repo.list_classes.side_effect = list_classes_side_effect

        run = PipelineRun(
            id="run-scope-collision",
            batch_run_id="batch-scope-collision",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "add",
                        "subject": "Service",  # Same title in both schemes
                        "predicate": "depends on",
                        "object": "API",
                        "confidence": 0.95,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run)

        # Should create relationship using class_in_scope (not class_in_other_scheme)
        assert result.relationships_created == 1
        assert result.relationships_skipped == 0
        # Verify list_classes was called with the scope's concept_scheme_id
        mock_ontology_repo.list_classes.assert_called_with(concept_scheme_id=scheme_id, limit=None)
        # Verify the relationship was created with the correct classes
        saved_rel_call = mock_ontology_repo.save_relationship.call_args
        saved_rel = saved_rel_call[0][0]
        assert saved_rel.source_id == class_in_scope.id
        assert saved_rel.target_id == class_in_scope_2.id

    def test_unscoped_lookup_without_scope_id(
        self,
        mock_ontology_repo,
        sample_classes,
        sample_property_definition,
    ):
        """When scope_id is missing, list_classes is called without scope filter."""

        def get_class_side_effect(ref):
            return sample_classes.get(ref.lower()) if ref.lower() in sample_classes else None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.list_relationships.return_value = []
        mock_ontology_repo.get_property_definition_by_identifier.return_value = (
            sample_property_definition
        )
        mock_ontology_repo.list_classes.return_value = list(sample_classes.values())

        run = PipelineRun(
            id="run-no-scope",
            batch_run_id="batch-no-scope",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                # No scope_id provided
                "deltas": [
                    {
                        "operation": "add",
                        "subject": "Microservice",
                        "predicate": "depends on",
                        "object": "Service",
                        "confidence": 0.95,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run)

        # Should still work (backward compatible)
        assert result.relationships_created == 1
        # Verify list_classes was called with concept_scheme_id=None
        mock_ontology_repo.list_classes.assert_called_with(concept_scheme_id=None, limit=None)


class TestSchemaConnectionRefinementApplyServiceEdgeCases:
    """Edge case tests for connection refinement apply service."""

    def test_add_existing_relationship_skipped(
        self,
        mock_ontology_repo,
        sample_classes,
        sample_property_definition,
        sample_scope_id,
    ):
        """Adding an already-existing relationship is skipped (idempotent)."""
        existing_rel = Relationship(
            id="rel-existing",
            source_id="class-1",
            target_id="class-2",
            property_definition_id="prop-1",
            source_run_id="run-orig",
        )

        def get_class_side_effect(ref):
            return sample_classes.get(ref.lower()) if ref.lower() in sample_classes else None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.list_relationships.return_value = [existing_rel]
        mock_ontology_repo.get_property_definition_by_identifier.return_value = (
            sample_property_definition
        )

        run = PipelineRun(
            id="run-dup-add",
            batch_run_id="batch-dup-add",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "add",
                        "subject": "Microservice",
                        "predicate": "depends on",
                        "object": "Service",
                        "confidence": 0.95,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run)

        assert result.relationships_created == 0
        assert result.relationships_skipped == 1
        mock_ontology_repo.save_relationship.assert_not_called()

    def test_remove_nonexistent_relationship_skipped(
        self,
        mock_ontology_repo,
        sample_classes,
        sample_property_definition,
        sample_scope_id,
    ):
        """Removing a non-existent relationship is skipped (idempotent)."""

        def get_class_side_effect(ref):
            return sample_classes.get(ref.lower()) if ref.lower() in sample_classes else None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.list_relationships.return_value = []
        mock_ontology_repo.get_property_definition_by_identifier.return_value = (
            sample_property_definition
        )

        run = PipelineRun(
            id="run-remove-absent",
            batch_run_id="batch-remove-absent",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "remove",
                        "subject": "Microservice",
                        "predicate": "depends on",
                        "object": "Service",
                        "confidence": 0.95,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run)

        assert result.relationships_removed == 0
        assert result.relationships_skipped == 1
        mock_ontology_repo.delete_relationship.assert_not_called()

    def test_missing_confidence_defaults_to_zero(
        self,
        mock_ontology_repo,
        sample_classes,
        sample_property_definition,
        sample_scope_id,
    ):
        """Missing confidence field defaults to 0.0."""

        def get_class_side_effect(ref):
            return sample_classes.get(ref.lower()) if ref.lower() in sample_classes else None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.get_property_definition_by_identifier.return_value = (
            sample_property_definition
        )

        run = PipelineRun(
            id="run-no-conf",
            batch_run_id="batch-no-conf",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "add",
                        "subject": "Microservice",
                        "predicate": "depends on",
                        "object": "Service",
                        # no confidence
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run, confidence_threshold=0.1)

        assert result.relationships_created == 0
        assert result.relationships_skipped == 1

    def test_invalid_operation_type_skipped(
        self,
        mock_ontology_repo,
        sample_classes,
        sample_property_definition,
        sample_scope_id,
    ):
        """Unknown operation type is skipped."""

        def get_class_side_effect(ref):
            return sample_classes.get(ref.lower()) if ref.lower() in sample_classes else None

        mock_ontology_repo.get_class.side_effect = get_class_side_effect
        mock_ontology_repo.get_property_definition_by_identifier.return_value = (
            sample_property_definition
        )

        run = PipelineRun(
            id="run-bad-op",
            batch_run_id="batch-bad-op",
            implementation_id="default",
            configuration_slug="connection-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "scope_id": sample_scope_id,
                "deltas": [
                    {
                        "operation": "invalid_operation",
                        "subject": "Microservice",
                        "predicate": "depends on",
                        "object": "Service",
                        "confidence": 0.95,
                    },
                ],
            },
        )

        service = SchemaConnectionRefinementApplyService(mock_ontology_repo)
        result = service.apply(run)

        assert result.relationships_created == 0
        assert result.relationships_skipped == 1
