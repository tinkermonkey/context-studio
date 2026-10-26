"""Unit tests for ChangeEventRecorder."""

from unittest.mock import Mock

import pytest

from adapters.events.change_recorder import ChangeEventRecorder
from domain.extraction.events import ExtractionCompleted
from domain.interchange.services import set_batch_run_context
from domain.ontology.value_objects import DataType
from domain.ontology.events import (
    AttributeDefinitionCreated,
    AttributeDefinitionDeleted,
    AttributeDefinitionUpdated,
    ClassCreated,
    ClassDeleted,
    ClassMoved,
    ClassUpdated,
    IndividualCreated,
    IndividualDeleted,
    IndividualUpdated,
    PropertyDefinitionCreated,
    PropertyDefinitionDeleted,
    PropertyDefinitionUpdated,
    RelationshipCreated,
    RelationshipDeleted,
    SchemeCreated,
    SchemeDeleted,
    SchemeUpdated,
    TaxonomyCreated,
    TaxonomyDeleted,
    TaxonomyUpdated,
)


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
        # Reset context to ensure no batch_run_id is set
        set_batch_run_context(None)
        mock_change_repo.record_change.return_value = "change-123"
        event = ExtractionCompleted(
            result_id="result-456",
            entity_count=42,
            duration_ms=1250.5,
        )

        recorder.on_extraction_completed(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "result-456"
        assert call_args.kwargs["entity_type"] == "extraction_result"
        assert call_args.kwargs["operation"] == "create"
        assert call_args.kwargs["new_state"]["entity_count"] == 42
        assert call_args.kwargs["new_state"]["duration_ms"] == 1250.5
        assert call_args.kwargs["batch_run_id"] is None

    def test_on_extraction_completed_propagates_batch_run_id(self, recorder, mock_change_repo):
        """Test that batch_run_id is propagated from context to record_change."""
        batch_run_id = "batch-789"
        set_batch_run_context(batch_run_id)
        try:
            mock_change_repo.record_change.return_value = "change-123"
            event = ExtractionCompleted(
                result_id="result-456",
                entity_count=42,
                duration_ms=1250.5,
            )

            recorder.on_extraction_completed(event)

            mock_change_repo.record_change.assert_called_once()
            call_args = mock_change_repo.record_change.call_args
            assert call_args.kwargs["batch_run_id"] == batch_run_id
        finally:
            set_batch_run_context(None)

    def test_on_extraction_completed_propagates_exception(self, recorder, mock_change_repo):
        """Test that repo exceptions propagate to the event publisher."""
        set_batch_run_context(None)
        mock_change_repo.record_change.side_effect = RuntimeError("DB error")
        event = ExtractionCompleted(
            result_id="result-456",
            entity_count=42,
            duration_ms=1250.5,
        )

        with pytest.raises(RuntimeError, match="DB error"):
            recorder.on_extraction_completed(event)

        mock_change_repo.record_change.assert_called_once()


class TestOntologyHandlers:
    """Tests for ontology event handlers."""

    def test_record_helper_calls_repo_with_correct_args(self, recorder, mock_change_repo):
        """Test that _record helper passes arguments correctly to repo."""
        # Reset context to ensure no batch_run_id is set
        set_batch_run_context(None)
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
        assert call_args.kwargs["entity_id"] == "entity-1"
        assert call_args.kwargs["entity_type"] == "test_entity"
        assert call_args.kwargs["operation"] == "create"
        assert call_args.kwargs["new_state"] == {"field": "value"}
        assert call_args.kwargs["change_reason"] == "Test change"
        assert call_args.kwargs["batch_run_id"] is None

    def test_record_helper_propagates_batch_run_id(self, recorder, mock_change_repo):
        """Test that _record helper propagates batch_run_id from context."""
        batch_run_id = "batch-555"
        set_batch_run_context(batch_run_id)
        try:
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
            call_args = mock_change_repo.record_change.call_args
            assert call_args.kwargs["batch_run_id"] == batch_run_id
        finally:
            set_batch_run_context(None)

    def test_record_helper_converts_none_new_state_to_empty_dict(self, recorder, mock_change_repo):
        """Test that _record helper converts None new_state to empty dict."""
        set_batch_run_context(None)
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
        assert call_args.kwargs["new_state"] == {}

    def test_record_helper_propagates_exception(self, recorder, mock_change_repo):
        """Test that _record helper propagates repo exceptions."""
        set_batch_run_context(None)
        mock_change_repo.record_change.side_effect = RuntimeError("DB error")

        with pytest.raises(RuntimeError, match="DB error"):
            recorder._record(
                entity_id="entity-1",
                entity_type="test_entity",
                operation="create",
                new_state={},
            )

    # --- CREATE Pattern Tests ---

    def test_on_scheme_created(self, recorder, mock_change_repo):
        """Test SchemeCreated event recording."""
        mock_change_repo.record_change.return_value = "change-123"
        event = SchemeCreated(
            concept_scheme_id="scheme-1",
            title="My Concept Scheme",
            taxonomy_id="tax-1",
        )

        recorder.on_scheme_created(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "scheme-1"
        assert call_args.kwargs["entity_type"] == "concept_scheme"
        assert call_args.kwargs["operation"] == "create"
        assert call_args.kwargs["new_state"]["concept_scheme_id"] == "scheme-1"
        assert call_args.kwargs["new_state"]["title"] == "My Concept Scheme"
        assert call_args.kwargs["new_state"]["taxonomy_id"] == "tax-1"

    def test_on_relationship_created(self, recorder, mock_change_repo):
        """Test RelationshipCreated event recording."""
        mock_change_repo.record_change.return_value = "change-789"
        event = RelationshipCreated(
            relationship_id="rel-1",
            source_id="source-1",
            target_id="target-1",
            property_definition_id="prop-1",
        )

        recorder.on_relationship_created(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "rel-1"
        assert call_args.kwargs["entity_type"] == "relationship"
        assert call_args.kwargs["operation"] == "create"
        assert call_args.kwargs["new_state"]["relationship_id"] == "rel-1"
        assert call_args.kwargs["new_state"]["source_id"] == "source-1"
        assert call_args.kwargs["new_state"]["target_id"] == "target-1"
        assert call_args.kwargs["new_state"]["property_definition_id"] == "prop-1"

    def test_on_taxonomy_created(self, recorder, mock_change_repo):
        """Test TaxonomyCreated event recording."""
        mock_change_repo.record_change.return_value = "change-123"
        event = TaxonomyCreated(taxonomy_id="tax-1", title="My Taxonomy")

        recorder.on_taxonomy_created(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "tax-1"
        assert call_args.kwargs["entity_type"] == "taxonomy"
        assert call_args.kwargs["operation"] == "create"
        assert call_args.kwargs["new_state"]["taxonomy_id"] == "tax-1"
        assert call_args.kwargs["new_state"]["title"] == "My Taxonomy"

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
        assert call_args.kwargs["entity_id"] == "class-1"
        assert call_args.kwargs["entity_type"] == "class"
        assert call_args.kwargs["operation"] == "create"
        assert call_args.kwargs["new_state"]["class_id"] == "class-1"

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
        assert call_args.kwargs["entity_id"] == "prop-1"
        assert call_args.kwargs["entity_type"] == "property_definition"
        assert call_args.kwargs["operation"] == "create"
        assert call_args.kwargs["new_state"]["identifier"] == "hasChild"

    def test_on_individual_created(self, recorder, mock_change_repo):
        """Test IndividualCreated event recording."""
        mock_change_repo.record_change.return_value = "change-111"
        event = IndividualCreated(
            individual_id="individual-1",
            title="John Doe",
            class_ids=["class-1", "class-2"],
            external_references=[{"source": "dr", "identifier": "a.b.c", "uri": None}],
        )

        recorder.on_individual_created(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "individual-1"
        assert call_args.kwargs["entity_type"] == "individual"
        assert call_args.kwargs["operation"] == "create"
        assert call_args.kwargs["new_state"]["individual_id"] == "individual-1"
        assert call_args.kwargs["new_state"]["title"] == "John Doe"
        assert call_args.kwargs["new_state"]["class_ids"] == ["class-1", "class-2"]
        assert call_args.kwargs["new_state"]["external_references"] == [
            {"source": "dr", "identifier": "a.b.c", "uri": None}
        ]

    # --- UPDATE Pattern Tests ---

    def test_on_scheme_updated(self, recorder, mock_change_repo):
        """Test SchemeUpdated event recording with change tracking."""
        mock_change_repo.record_change.return_value = "change-123"
        event = SchemeUpdated(
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            changed_fields=("title", "description"),
            old_values={"title": "Old Scheme", "description": "Old Desc"},
            new_values={"title": "New Scheme", "description": "New Desc"},
        )

        recorder.on_scheme_updated(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "scheme-1"
        assert call_args.kwargs["entity_type"] == "concept_scheme"
        assert call_args.kwargs["operation"] == "update"
        assert call_args.kwargs["new_state"] == event.new_values
        assert call_args.kwargs["previous_state"] == event.old_values
        assert "title" in call_args.kwargs["change_reason"]
        assert "description" in call_args.kwargs["change_reason"]

    def test_on_class_moved(self, recorder, mock_change_repo):
        """Test ClassMoved event recording with parent mapping logic."""
        mock_change_repo.record_change.return_value = "change-456"
        event = ClassMoved(
            class_id="class-1",
            old_parent_id="parent-1",
            new_parent_id="parent-2",
        )

        recorder.on_class_moved(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "class-1"
        assert call_args.kwargs["entity_type"] == "class"
        assert call_args.kwargs["operation"] == "update"
        # Verify the unique mapping logic: parent IDs are captured in state
        assert call_args.kwargs["new_state"]["parent_id"] == "parent-2"
        assert call_args.kwargs["previous_state"]["parent_id"] == "parent-1"
        # Verify the change reason mentions both old and new parent
        assert "parent-1" in call_args.kwargs["change_reason"]
        assert "parent-2" in call_args.kwargs["change_reason"]

    def test_on_class_moved_with_none_parents(self, recorder, mock_change_repo):
        """Test ClassMoved event with None parent IDs (root movements)."""
        mock_change_repo.record_change.return_value = "change-456"
        event = ClassMoved(
            class_id="class-1",
            old_parent_id=None,
            new_parent_id="parent-2",
        )

        recorder.on_class_moved(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["new_state"]["parent_id"] == "parent-2"
        assert call_args.kwargs["previous_state"]["parent_id"] is None

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
        assert call_args.kwargs["entity_id"] == "tax-1"
        assert call_args.kwargs["entity_type"] == "taxonomy"
        assert call_args.kwargs["operation"] == "update"
        assert call_args.kwargs["new_state"] == event.new_values
        assert call_args.kwargs["previous_state"] == event.old_values
        assert "title" in call_args.kwargs["change_reason"]
        assert "description" in call_args.kwargs["change_reason"]

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
        assert call_args.kwargs["entity_id"] == "class-1"
        assert call_args.kwargs["operation"] == "update"
        assert call_args.kwargs["previous_state"] == event.old_values

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
        assert call_args.kwargs["entity_id"] == "prop-1"
        assert call_args.kwargs["entity_type"] == "property_definition"
        assert call_args.kwargs["operation"] == "update"
        assert call_args.kwargs["new_state"]["title"] == "Updated Title"
        assert "title" in call_args.kwargs["change_reason"]

    def test_on_individual_updated(self, recorder, mock_change_repo):
        """Test IndividualUpdated event recording with change tracking."""
        mock_change_repo.record_change.return_value = "change-111"
        event = IndividualUpdated(
            individual_id="individual-1",
            changed_fields=("title", "description"),
            old_values={"title": "John Doe", "description": "Old Description"},
            new_values={"title": "Jane Doe", "description": "New Description"},
        )

        recorder.on_individual_updated(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "individual-1"
        assert call_args.kwargs["entity_type"] == "individual"
        assert call_args.kwargs["operation"] == "update"
        assert call_args.kwargs["new_state"] == event.new_values
        assert call_args.kwargs["previous_state"] == event.old_values
        assert "title" in call_args.kwargs["change_reason"]
        assert "description" in call_args.kwargs["change_reason"]

    # --- DELETE Pattern Tests ---

    def test_on_scheme_deleted(self, recorder, mock_change_repo):
        """Test SchemeDeleted event recording."""
        mock_change_repo.record_change.return_value = "change-123"
        event = SchemeDeleted(
            concept_scheme_id="scheme-1",
            title="My Concept Scheme",
            taxonomy_id="tax-1",
            snapshot={"id": "scheme-1", "taxonomy_id": "tax-1", "title": "My Concept Scheme"},
        )

        recorder.on_scheme_deleted(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "scheme-1"
        assert call_args.kwargs["entity_type"] == "concept_scheme"
        assert call_args.kwargs["operation"] == "delete"
        assert call_args.kwargs["previous_state"] == event.snapshot

    def test_on_taxonomy_deleted(self, recorder, mock_change_repo):
        """Test TaxonomyDeleted event recording."""
        mock_change_repo.record_change.return_value = "change-123"
        event = TaxonomyDeleted(
            taxonomy_id="tax-1",
            title="My Taxonomy",
            snapshot={"id": "tax-1", "title": "My Taxonomy"},
        )

        recorder.on_taxonomy_deleted(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "tax-1"
        assert call_args.kwargs["entity_type"] == "taxonomy"
        assert call_args.kwargs["operation"] == "delete"
        assert call_args.kwargs["previous_state"] == event.snapshot

    def test_on_class_deleted(self, recorder, mock_change_repo):
        """Test ClassDeleted event recording."""
        mock_change_repo.record_change.return_value = "change-456"
        event = ClassDeleted(
            class_id="class-1", title="My Class", snapshot={"id": "class-1", "title": "My Class"}
        )

        recorder.on_class_deleted(event)

        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "class-1"
        assert call_args.kwargs["operation"] == "delete"
        assert call_args.kwargs["previous_state"] == event.snapshot

    def test_on_relationship_deleted(self, recorder, mock_change_repo):
        """Test RelationshipDeleted event recording."""
        mock_change_repo.record_change.return_value = "change-789"
        event = RelationshipDeleted(
            relationship_id="rel-1",
            source_id="source-1",
            target_id="target-1",
            property_definition_id="prop-1",
            snapshot={
                "id": "rel-1",
                "source_id": "source-1",
                "target_id": "target-1",
                "property_definition_id": "prop-1",
            },
        )

        recorder.on_relationship_deleted(event)

        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "rel-1"
        assert call_args.kwargs["operation"] == "delete"
        assert call_args.kwargs["previous_state"] == event.snapshot

    def test_on_property_definition_deleted(self, recorder, mock_change_repo):
        """Test PropertyDefinitionDeleted event recording."""
        mock_change_repo.record_change.return_value = "change-999"
        event = PropertyDefinitionDeleted(
            property_id="prop-1",
            identifier="hasChild",
            title="Has Child",
            snapshot={"id": "prop-1", "identifier": "hasChild", "title": "Has Child"},
        )

        recorder.on_property_definition_deleted(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "prop-1"
        assert call_args.kwargs["entity_type"] == "property_definition"
        assert call_args.kwargs["operation"] == "delete"
        assert call_args.kwargs["previous_state"] == event.snapshot
        assert call_args.kwargs["previous_state"]["title"] == "Has Child"

    def test_on_attribute_definition_created(self, recorder, mock_change_repo):
        """AttributeDefinitionCreated is recorded as a create of the attribute."""
        mock_change_repo.record_change.return_value = "change-220"
        event = AttributeDefinitionCreated(
            attribute_definition_id="attr-1",
            class_id="class-1",
            identifier="estimate_minutes",
            title="Estimate (minutes)",
        )

        recorder.on_attribute_definition_created(event)

        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "attr-1"
        assert call_args.kwargs["entity_type"] == "attribute_definition"
        assert call_args.kwargs["operation"] == "create"
        assert call_args.kwargs["new_state"]["class_id"] == "class-1"

    def test_on_attribute_definition_updated_stores_plain_values(self, recorder, mock_change_repo):
        """Old and new values are recorded, with the DataType enum as its plain value."""
        mock_change_repo.record_change.return_value = "change-221"
        event = AttributeDefinitionUpdated(
            attribute_definition_id="attr-1",
            changed_fields=("datatype", "allowed_values"),
            old_values={"datatype": DataType.STRING, "allowed_values": None},
            new_values={"datatype": DataType.INTEGER, "allowed_values": ["5", "10"]},
        )

        recorder.on_attribute_definition_updated(event)

        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["operation"] == "update"
        assert call_args.kwargs["previous_state"] == {"datatype": "string", "allowed_values": None}
        assert call_args.kwargs["new_state"] == {
            "datatype": "integer",
            "allowed_values": ["5", "10"],
        }
        assert type(call_args.kwargs["new_state"]["datatype"]) is str
        assert "datatype, allowed_values" in call_args.kwargs["change_reason"]

    def test_on_attribute_definition_deleted(self, recorder, mock_change_repo):
        """Test AttributeDefinitionDeleted event recording."""
        mock_change_repo.record_change.return_value = "change-222"
        event = AttributeDefinitionDeleted(
            attribute_definition_id="attr-1",
            class_id="class-1",
            identifier="legs",
            title="Legs",
            snapshot={"id": "attr-1", "class_id": "class-1", "identifier": "legs"},
        )

        recorder.on_attribute_definition_deleted(event)

        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "attr-1"
        assert call_args.kwargs["entity_type"] == "attribute_definition"
        assert call_args.kwargs["operation"] == "delete"
        assert call_args.kwargs["previous_state"] == event.snapshot

    def test_on_individual_deleted(self, recorder, mock_change_repo):
        """Test IndividualDeleted event recording."""
        mock_change_repo.record_change.return_value = "change-111"
        event = IndividualDeleted(
            individual_id="individual-1",
            title="John Doe",
            snapshot={"id": "individual-1", "class_ids": ["class-1"], "title": "John Doe"},
        )

        recorder.on_individual_deleted(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs["entity_id"] == "individual-1"
        assert call_args.kwargs["entity_type"] == "individual"
        assert call_args.kwargs["operation"] == "delete"
        assert call_args.kwargs["previous_state"] == event.snapshot
