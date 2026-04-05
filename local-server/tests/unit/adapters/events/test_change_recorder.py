"""Unit tests for ChangeEventRecorder."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../'))

from unittest.mock import Mock
import pytest

from domain.extraction.events import ExtractionCompleted
from domain.pipeline.events import PipelineExecuted
from domain.ontology.events import (
    TaxonomyCreated,
    TaxonomyUpdated,
    TaxonomyDeleted,
    ClassCreated,
    ClassUpdated,
    ClassDeleted,
    RelationshipCreated,
    RelationshipDeleted,
    PropertyDefinitionCreated,
    PropertyDefinitionUpdated,
    PropertyDefinitionDeleted,
    SchemeCreated,
    SchemeUpdated,
    SchemeDeleted,
    ClassMoved,
    ConceptSchemeUpdated,
)
from adapters.events.change_recorder import ChangeEventRecorder


@pytest.fixture
def mock_change_repo():
    """Create a mock change repository."""
    return Mock()


@pytest.fixture
def recorder(mock_change_repo):
    """Create a ChangeEventRecorder with mock repo."""
    return ChangeEventRecorder(mock_change_repo)


class TestChangeEventRecorder:
    """Tests for ChangeEventRecorder."""

    def test_on_extraction_completed_records_change(self, recorder, mock_change_repo):
        """Test that ExtractionCompleted event is recorded."""
        mock_change_repo.record_change.return_value = "change-123"
        event = ExtractionCompleted(
            result_id="result-456",
            entity_count=42,
            duration_ms=1250.5,
        )

        recorder.on_extraction_completed(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "result-456"
        assert call_args.kwargs['entity_type'] == "extraction_result"
        assert call_args.kwargs['operation'] == "create"
        assert call_args.kwargs['new_state']['entity_count'] == 42
        assert call_args.kwargs['new_state']['duration_ms'] == 1250.5

    def test_on_extraction_completed_propagates_exception(self, recorder, mock_change_repo):
        """Test that repo exceptions propagate to the event publisher."""
        mock_change_repo.record_change.side_effect = RuntimeError("DB error")
        event = ExtractionCompleted(
            result_id="result-456",
            entity_count=42,
            duration_ms=1250.5,
        )

        with pytest.raises(RuntimeError, match="DB error"):
            recorder.on_extraction_completed(event)

        mock_change_repo.record_change.assert_called_once()

    def test_on_pipeline_executed_records_change(self, recorder, mock_change_repo):
        """Test that PipelineExecuted event is recorded."""
        mock_change_repo.record_change.return_value = "change-789"
        event = PipelineExecuted(
            execution_id="exec-123",
            pipeline_id="pipeline-456",
            status="success",
        )

        recorder.on_pipeline_executed(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "exec-123"
        assert call_args.kwargs['entity_type'] == "pipeline_execution"
        assert call_args.kwargs['operation'] == "create"
        assert call_args.kwargs['new_state']['pipeline_id'] == "pipeline-456"
        assert call_args.kwargs['new_state']['status'] == "success"

    def test_on_pipeline_executed_propagates_exception(self, recorder, mock_change_repo):
        """Test that repo exceptions propagate to the event publisher."""
        mock_change_repo.record_change.side_effect = RuntimeError("DB error")
        event = PipelineExecuted(
            execution_id="exec-123",
            pipeline_id="pipeline-456",
            status="success",
        )

        with pytest.raises(RuntimeError, match="DB error"):
            recorder.on_pipeline_executed(event)

        mock_change_repo.record_change.assert_called_once()


class TestOntologyHandlers:
    """Tests for ontology event handlers."""

    def test_record_helper_calls_repo_with_correct_args(self, recorder, mock_change_repo):
        """Test that _record helper passes arguments correctly to repo."""
        mock_change_repo.record_change.return_value = "change-123"

        change_id = recorder._record(
            entity_id="entity-1",
            entity_type="test_entity",
            operation="create",
            new_state={"field": "value"},
            previous_state=None,
            change_reason="Test change",
        )

        assert change_id == "change-123"
        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "entity-1"
        assert call_args.kwargs['entity_type'] == "test_entity"
        assert call_args.kwargs['operation'] == "create"
        assert call_args.kwargs['new_state'] == {"field": "value"}
        assert call_args.kwargs['change_reason'] == "Test change"

    def test_record_helper_converts_none_new_state_to_empty_dict(self, recorder, mock_change_repo):
        """Test that _record helper converts None new_state to empty dict."""
        mock_change_repo.record_change.return_value = "change-123"

        recorder._record(
            entity_id="entity-1",
            entity_type="test_entity",
            operation="delete",
            new_state=None,
            previous_state={"field": "value"},
            change_reason="Deleted",
        )

        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['new_state'] == {}

    def test_record_helper_propagates_exception(self, recorder, mock_change_repo):
        """Test that _record helper propagates repo exceptions."""
        mock_change_repo.record_change.side_effect = RuntimeError("DB error")

        with pytest.raises(RuntimeError, match="DB error"):
            recorder._record(
                entity_id="entity-1",
                entity_type="test_entity",
                operation="create",
                new_state={},
            )

    # --- CREATE Pattern Tests ---

    def test_on_taxonomy_created(self, recorder, mock_change_repo):
        """Test TaxonomyCreated event recording."""
        mock_change_repo.record_change.return_value = "change-123"
        event = TaxonomyCreated(taxonomy_id="tax-1", title="My Taxonomy")

        recorder.on_taxonomy_created(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "tax-1"
        assert call_args.kwargs['entity_type'] == "taxonomy"
        assert call_args.kwargs['operation'] == "create"
        assert call_args.kwargs['new_state']['taxonomy_id'] == "tax-1"
        assert call_args.kwargs['new_state']['title'] == "My Taxonomy"

    def test_on_class_created(self, recorder, mock_change_repo):
        """Test ClassCreated event recording."""
        mock_change_repo.record_change.return_value = "change-456"
        event = ClassCreated(
            class_id="class-1",
            title="My Class",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
        )

        recorder.on_class_created(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "class-1"
        assert call_args.kwargs['entity_type'] == "class"
        assert call_args.kwargs['operation'] == "create"
        assert call_args.kwargs['new_state']['class_id'] == "class-1"

    def test_on_property_definition_created(self, recorder, mock_change_repo):
        """Test PropertyDefinitionCreated event recording."""
        mock_change_repo.record_change.return_value = "change-789"
        event = PropertyDefinitionCreated(
            property_id="prop-1",
            identifier="hasChild",
            title="Has Child",
        )

        recorder.on_property_definition_created(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "prop-1"
        assert call_args.kwargs['entity_type'] == "property_definition"
        assert call_args.kwargs['operation'] == "create"
        assert call_args.kwargs['new_state']['identifier'] == "hasChild"

    # --- UPDATE Pattern Tests ---

    def test_on_taxonomy_updated(self, recorder, mock_change_repo):
        """Test TaxonomyUpdated event recording with change tracking."""
        mock_change_repo.record_change.return_value = "change-123"
        event = TaxonomyUpdated(
            taxonomy_id="tax-1",
            changed_fields=("title", "description"),
            old_values={"title": "Old Title", "description": "Old Desc"},
            new_values={"title": "New Title", "description": "New Desc"},
        )

        recorder.on_taxonomy_updated(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "tax-1"
        assert call_args.kwargs['entity_type'] == "taxonomy"
        assert call_args.kwargs['operation'] == "update"
        assert call_args.kwargs['new_state'] == event.new_values
        assert call_args.kwargs['previous_state'] == event.old_values
        assert "title" in call_args.kwargs['change_reason']
        assert "description" in call_args.kwargs['change_reason']

    def test_on_class_updated(self, recorder, mock_change_repo):
        """Test ClassUpdated event recording."""
        mock_change_repo.record_change.return_value = "change-456"
        event = ClassUpdated(
            class_id="class-1",
            changed_fields=("title",),
            old_values={"title": "Old Class"},
            new_values={"title": "New Class"},
        )

        recorder.on_class_updated(event)

        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "class-1"
        assert call_args.kwargs['operation'] == "update"
        assert call_args.kwargs['previous_state'] == event.old_values

    def test_on_property_definition_updated(self, recorder, mock_change_repo):
        """Test PropertyDefinitionUpdated event recording."""
        mock_change_repo.record_change.return_value = "change-789"
        event = PropertyDefinitionUpdated(
            property_id="prop-1",
            title="Updated Title",
            description="Updated Description",
        )

        recorder.on_property_definition_updated(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "prop-1"
        assert call_args.kwargs['entity_type'] == "property_definition"
        assert call_args.kwargs['operation'] == "update"
        assert call_args.kwargs['new_state']['title'] == "Updated Title"
        assert "title" in call_args.kwargs['change_reason']

    def test_on_concept_scheme_updated(self, recorder, mock_change_repo):
        """Test ConceptSchemeUpdated event recording."""
        mock_change_repo.record_change.return_value = "change-123"
        event = ConceptSchemeUpdated(
            concept_scheme_id="scheme-1",
            title="New Scheme Title",
        )

        recorder.on_concept_scheme_updated(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "scheme-1"
        assert call_args.kwargs['entity_type'] == "concept_scheme"
        assert call_args.kwargs['operation'] == "update"
        assert call_args.kwargs['new_state']['title'] == "New Scheme Title"
        assert "title" in call_args.kwargs['change_reason']

    # --- DELETE Pattern Tests ---

    def test_on_taxonomy_deleted(self, recorder, mock_change_repo):
        """Test TaxonomyDeleted event recording."""
        mock_change_repo.record_change.return_value = "change-123"
        event = TaxonomyDeleted(taxonomy_id="tax-1", title="My Taxonomy")

        recorder.on_taxonomy_deleted(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "tax-1"
        assert call_args.kwargs['entity_type'] == "taxonomy"
        assert call_args.kwargs['operation'] == "delete"
        assert call_args.kwargs['previous_state']['title'] == "My Taxonomy"

    def test_on_class_deleted(self, recorder, mock_change_repo):
        """Test ClassDeleted event recording."""
        mock_change_repo.record_change.return_value = "change-456"
        event = ClassDeleted(class_id="class-1", title="My Class")

        recorder.on_class_deleted(event)

        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "class-1"
        assert call_args.kwargs['operation'] == "delete"
        assert call_args.kwargs['previous_state']['title'] == "My Class"

    def test_on_relationship_deleted(self, recorder, mock_change_repo):
        """Test RelationshipDeleted event recording."""
        mock_change_repo.record_change.return_value = "change-789"
        event = RelationshipDeleted(
            relationship_id="rel-1",
            source_id="source-1",
            target_id="target-1",
            property_definition_id="prop-1",
        )

        recorder.on_relationship_deleted(event)

        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "rel-1"
        assert call_args.kwargs['operation'] == "delete"
        assert call_args.kwargs['previous_state']['source_id'] == "source-1"

    def test_on_property_definition_deleted(self, recorder, mock_change_repo):
        """Test PropertyDefinitionDeleted event recording."""
        mock_change_repo.record_change.return_value = "change-999"
        event = PropertyDefinitionDeleted(
            property_id="prop-1",
            identifier="hasChild",
            title="Has Child",
        )

        recorder.on_property_definition_deleted(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "prop-1"
        assert call_args.kwargs['entity_type'] == "property_definition"
        assert call_args.kwargs['operation'] == "delete"
        assert call_args.kwargs['previous_state']['identifier'] == "hasChild"
        assert call_args.kwargs['previous_state']['title'] == "Has Child"
