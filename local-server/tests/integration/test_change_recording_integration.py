"""
Integration tests for ontology change recording.

Verifies that ontology operations produce change events end-to-end by:
1. Creating ontology entities through OntologyService
2. Verifying that domain events are published
3. Verifying that ChangeEventRecorder persists them to the change audit trail

Tests ensure the complete workflow: domain operation → event → recording.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.models import Base, ChangeEvent
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.extraction.events import ExtractionCompleted
from domain.ontology.events import (
    ClassCreated,
    ClassDeleted,
    ClassMoved,
    ClassUpdated,
    ConceptSchemeUpdated,
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
from domain.ontology.services import OntologyService
from domain.pipelines.events import PipelineExecuted
from domain.versioning.value_objects import ChangeOperation
from tests.fakes.fake_embedding_service import FakeEmbeddingService


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_factory(db_engine):
    """Create a session factory for testing."""
    return sessionmaker(bind=db_engine)


@pytest.fixture
def event_publisher():
    """Create an in-process event publisher - must be created first."""
    return InProcessEventPublisher()


@pytest.fixture
def ontology_repo(session_factory):
    """Create an ontology repository instance."""
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture
def change_repo(session_factory):
    """Create a change repository instance."""
    return SQLiteChangeRepository(session_factory)


@pytest.fixture
def embedding_service():
    """Create a lightweight fake embedding service for testing."""
    return FakeEmbeddingService()


@pytest.fixture
def change_recorder(change_repo, event_publisher):
    """Create and wire up the change event recorder.

    Note: This fixture manually subscribes to events for testing the recorder's
    ability to handle these events. This wiring duplicates the application's
    composition root in app.py. These tests verify the recorder + repo integration,
    not the application's event wiring setup.
    """
    recorder = ChangeEventRecorder(change_repo)

    # Subscribe to all ontology events
    event_publisher.subscribe(TaxonomyCreated, recorder.on_taxonomy_created)
    event_publisher.subscribe(SchemeCreated, recorder.on_scheme_created)
    event_publisher.subscribe(ClassCreated, recorder.on_class_created)
    event_publisher.subscribe(ClassUpdated, recorder.on_class_updated)
    event_publisher.subscribe(ClassDeleted, recorder.on_class_deleted)
    event_publisher.subscribe(ClassMoved, recorder.on_class_moved)
    event_publisher.subscribe(RelationshipCreated, recorder.on_relationship_created)
    event_publisher.subscribe(RelationshipDeleted, recorder.on_relationship_deleted)
    event_publisher.subscribe(PropertyDefinitionCreated, recorder.on_property_definition_created)
    event_publisher.subscribe(PropertyDefinitionUpdated, recorder.on_property_definition_updated)
    event_publisher.subscribe(PropertyDefinitionDeleted, recorder.on_property_definition_deleted)
    event_publisher.subscribe(TaxonomyUpdated, recorder.on_taxonomy_updated)
    event_publisher.subscribe(TaxonomyDeleted, recorder.on_taxonomy_deleted)
    event_publisher.subscribe(SchemeUpdated, recorder.on_scheme_updated)
    event_publisher.subscribe(SchemeDeleted, recorder.on_scheme_deleted)
    event_publisher.subscribe(ConceptSchemeUpdated, recorder.on_concept_scheme_updated)
    event_publisher.subscribe(ExtractionCompleted, recorder.on_extraction_completed)
    event_publisher.subscribe(PipelineExecuted, recorder.on_pipeline_executed)

    return recorder


@pytest.fixture
def ontology_service(change_recorder, ontology_repo, embedding_service, event_publisher):
    """
    Create the ontology service with all dependencies.

    Note: change_recorder is a dependency to ensure subscriptions are set up before
    the service is created and starts publishing events.
    """
    return OntologyService(ontology_repo, embedding_service, event_publisher)


@pytest.fixture
def session(session_factory):
    """Provide a session with automatic lifecycle management.

    Ensures the session is closed after the test, preventing resource leaks.
    """
    sess = session_factory()
    yield sess
    sess.close()


class TestChangeRecordingIntegration:
    """Integration tests for ontology change recording."""

    def test_taxonomy_creation_records_change(self, ontology_service, session):
        """Test that creating a taxonomy produces a change event."""
        # Create taxonomy
        taxonomy = ontology_service.create_taxonomy(
            title="Test Taxonomy",
            description="A test taxonomy",
        )

        # Verify change was recorded
        change_events = (
            session.query(ChangeEvent)
            .filter_by(
                entity_id=taxonomy.id,
                entity_type="taxonomy",
            )
            .all()
        )

        assert len(change_events) == 1
        change_event = change_events[0]
        assert change_event.operation == ChangeOperation.CREATE
        assert change_event.new_state["taxonomy_id"] == taxonomy.id
        assert change_event.new_state["title"] == "Test Taxonomy"
        assert change_event.change_reason == "Taxonomy created"

    def test_concept_scheme_creation_records_change(self, ontology_service, session):
        """Test that creating a concept scheme produces a change event."""
        # Create taxonomy first
        taxonomy = ontology_service.create_taxonomy("Biology")

        # Create concept scheme
        scheme = ontology_service.create_scheme(
            taxonomy_id=taxonomy.id,
            title="Organisms",
            description="Classification of living things",
        )

        # Verify change was recorded
        change_events = (
            session.query(ChangeEvent)
            .filter_by(
                entity_id=scheme.id,
                entity_type="concept_scheme",
            )
            .all()
        )

        assert len(change_events) == 1
        change_event = change_events[0]
        assert change_event.operation == ChangeOperation.CREATE
        assert change_event.new_state["concept_scheme_id"] == scheme.id
        assert change_event.new_state["title"] == "Organisms"
        assert change_event.new_state["taxonomy_id"] == taxonomy.id
        assert change_event.change_reason == "Concept scheme created"

    def test_class_creation_records_change(self, ontology_service, session):
        """Test that creating a class produces a change event."""
        # Create taxonomy and scheme first
        taxonomy = ontology_service.create_taxonomy("Biology")
        scheme = ontology_service.create_scheme(
            taxonomy_id=taxonomy.id,
            title="Organisms",
        )

        # Create class
        clazz = ontology_service.create_class(
            concept_scheme_id=scheme.id,
            title="Mammal",
            description="Warm-blooded animals",
        )

        # Verify change was recorded
        change_events = (
            session.query(ChangeEvent)
            .filter_by(
                entity_id=clazz.id,
                entity_type="class",
            )
            .all()
        )

        assert len(change_events) == 1
        change_event = change_events[0]
        assert change_event.operation == ChangeOperation.CREATE
        assert change_event.new_state["class_id"] == clazz.id
        assert change_event.new_state["title"] == "Mammal"
        assert change_event.change_reason == "Class created"

    def test_class_hierarchy_change_records_class_moved(self, ontology_service, session_factory):
        """Test that moving a class in the hierarchy records a ClassMoved event."""
        # Setup hierarchy
        taxonomy = ontology_service.create_taxonomy("Biology")
        scheme = ontology_service.create_scheme(
            taxonomy_id=taxonomy.id,
            title="Organisms",
        )

        parent1 = ontology_service.create_class(
            concept_scheme_id=scheme.id,
            title="Parent1",
        )
        parent2 = ontology_service.create_class(
            concept_scheme_id=scheme.id,
            title="Parent2",
        )
        child = ontology_service.create_class(
            concept_scheme_id=scheme.id,
            title="Child",
            parent_class_id=parent1.id,
        )

        # Clear any creation changes
        session = session_factory()
        try:
            session.query(ChangeEvent).delete()
            session.commit()
        finally:
            session.close()

        # Move the child from parent1 to parent2
        ontology_service.move_class(
            class_id=child.id,
            new_parent_id=parent2.id,
        )

        # Verify ClassMoved was recorded
        session = session_factory()
        try:
            change_events = (
                session.query(ChangeEvent)
                .filter_by(
                    entity_id=child.id,
                    entity_type="class",
                )
                .all()
            )

            # Should have an UPDATE operation for the parent change
            assert len(change_events) > 0
            # Find the parent change event
            parent_change = None
            for event in change_events:
                if (
                    event.operation == ChangeOperation.UPDATE
                    and event.new_state.get("parent_id") == parent2.id
                ):
                    parent_change = event
                    break

            assert parent_change is not None
            assert parent_change.previous_state["parent_id"] == parent1.id
            assert parent_change.new_state["parent_id"] == parent2.id
            # The change reason includes the actual parent IDs, not the names
            assert parent1.id in parent_change.change_reason
            assert parent2.id in parent_change.change_reason
        finally:
            session.close()

    def test_property_definition_creation_records_change(self, ontology_service, session):
        """Test that creating a property definition produces a change event."""
        # Create property definition
        prop_def = ontology_service.create_property_definition(
            identifier="hasChild",
            title="Has Child",
            description="Parent-child relationship",
        )

        # Verify change was recorded
        change_events = (
            session.query(ChangeEvent)
            .filter_by(
                entity_id=prop_def.id,
                entity_type="property_definition",
            )
            .all()
        )

        assert len(change_events) == 1
        change_event = change_events[0]
        assert change_event.operation == ChangeOperation.CREATE
        assert change_event.new_state["property_id"] == prop_def.id
        assert change_event.new_state["identifier"] == "hasChild"
        assert change_event.change_reason == "Property definition created"

    def test_relationship_creation_records_change(self, ontology_service, session_factory):
        """Test that creating a relationship produces a change event."""
        # Setup: create entities and property definition
        taxonomy = ontology_service.create_taxonomy("Biology")
        scheme = ontology_service.create_scheme(
            taxonomy_id=taxonomy.id,
            title="Organisms",
        )
        source_class = ontology_service.create_class(
            concept_scheme_id=scheme.id,
            title="Animal",
        )
        target_class = ontology_service.create_class(
            concept_scheme_id=scheme.id,
            title="Mammal",
        )
        prop_def = ontology_service.create_property_definition(
            identifier="hasSubclass",
            title="Has Subclass",
        )

        # Clear creation changes
        session = session_factory()
        try:
            session.query(ChangeEvent).delete()
            session.commit()
        finally:
            session.close()

        # Create relationship
        relationship = ontology_service.create_relationship(
            source_id=source_class.id,
            target_id=target_class.id,
            property_definition_id=prop_def.id,
        )

        # Verify change was recorded
        session = session_factory()
        try:
            change_events = (
                session.query(ChangeEvent)
                .filter_by(
                    entity_id=relationship.id,
                    entity_type="relationship",
                )
                .all()
            )

            assert len(change_events) == 1
            change_event = change_events[0]
            assert change_event.operation == ChangeOperation.CREATE
            assert change_event.new_state["relationship_id"] == relationship.id
            assert change_event.new_state["source_id"] == source_class.id
            assert change_event.new_state["target_id"] == target_class.id
            assert change_event.change_reason == "Relationship created"
        finally:
            session.close()

    def test_taxonomy_update_records_change(self, ontology_service, session_factory):
        """Test that updating a taxonomy produces a change event."""
        # Create taxonomy
        taxonomy = ontology_service.create_taxonomy(
            title="Original Title",
            description="Original description",
        )

        # Clear creation change
        session = session_factory()
        try:
            session.query(ChangeEvent).delete()
            session.commit()
        finally:
            session.close()

        # Update taxonomy
        ontology_service.update_taxonomy(
            taxonomy_id=taxonomy.id,
            title="Updated Title",
            description="Updated description",
        )

        # Verify change was recorded
        session = session_factory()
        try:
            change_events = (
                session.query(ChangeEvent)
                .filter_by(
                    entity_id=taxonomy.id,
                    entity_type="taxonomy",
                )
                .all()
            )

            assert len(change_events) == 1
            change_event = change_events[0]
            assert change_event.operation == ChangeOperation.UPDATE
            assert change_event.new_state["title"] == "Updated Title"
            assert change_event.previous_state["title"] == "Original Title"
            assert "title" in change_event.change_reason
        finally:
            session.close()

    def test_taxonomy_deletion_records_change(self, ontology_service, session_factory):
        """Test that deleting a taxonomy produces a change event."""
        # Create taxonomy
        taxonomy = ontology_service.create_taxonomy("Biology")
        taxonomy_id = taxonomy.id

        # Clear creation change
        session = session_factory()
        try:
            session.query(ChangeEvent).delete()
            session.commit()
        finally:
            session.close()

        # Delete taxonomy
        ontology_service.delete_taxonomy(taxonomy_id)

        # Verify change was recorded
        session = session_factory()
        try:
            change_events = (
                session.query(ChangeEvent)
                .filter_by(
                    entity_id=taxonomy_id,
                    entity_type="taxonomy",
                )
                .all()
            )

            assert len(change_events) == 1
            change_event = change_events[0]
            assert change_event.operation == ChangeOperation.DELETE
            assert change_event.previous_state["taxonomy_id"] == taxonomy_id
            assert change_event.previous_state["title"] == "Biology"
            assert change_event.change_reason == "Taxonomy deleted"
        finally:
            session.close()
