"""
Integration tests for ImportRun correlation context with ChangeEventRecorder.

Verifies that change events produced inside an import operation are
automatically linked to the import run via the correlation context.
"""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.models import Base
from domain.interchange.services import (
    ImportRunService,
    get_current_batch_run_id,
    set_import_run_context,
)
from domain.interchange.value_objects import (
    SerializationFormat,
    SerializationScope,
    SerializationScopeType,
)
from domain.ontology.services import OntologyService
from domain.versioning.value_objects import ChangeOperation
from tests.fakes.fake_embedding_service import FakeEmbeddingService


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_factory(db_engine):
    """Create a session factory."""
    return sessionmaker(bind=db_engine)


@pytest.fixture
def change_repo(session_factory):
    """Create a change repository."""
    return SQLiteChangeRepository(session_factory)


@pytest.fixture
def ontology_repo(session_factory):
    """Create an ontology repository."""
    from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository

    return SQLiteOntologyRepository(session_factory)


@pytest.fixture
def embedding_service():
    """Create a fake embedding service."""
    return FakeEmbeddingService()


@pytest.fixture
def event_publisher():
    """Create an in-process event publisher."""
    return InProcessEventPublisher()


@pytest.fixture
def change_recorder(change_repo):
    """Create a change event recorder."""
    return ChangeEventRecorder(change_repo)


@pytest.fixture
def ontology_service(ontology_repo, embedding_service, event_publisher):
    """Create an ontology service."""
    return OntologyService(ontology_repo, embedding_service, event_publisher)


def test_change_events_outside_import_have_null_batch_run_id(change_repo):
    """Change events outside an import have NULL batch_run_id."""
    # Ensure no import context is active
    assert get_current_batch_run_id() is None

    # Directly record a change event without import context
    change_repo.record_change(
        entity_id="test-entity-1",
        entity_type="taxonomy",
        operation=ChangeOperation.CREATE,
        new_state={"title": "Test"},
        change_reason="test change",
    )

    # Verify the change event was recorded with NULL batch_run_id
    retrieved_event = (
        change_repo.get_changes(limit=1).events[0]
        if change_repo.get_changes(limit=1).events
        else None
    )
    assert retrieved_event is not None
    assert retrieved_event.batch_run_id is None


def test_change_events_inside_import_have_batch_run_id(change_repo):
    """Change events inside an import have the batch_run_id set."""
    # Create an import run and set context
    import_service = ImportRunService()
    scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
    import_run = import_service.start_run(
        format=SerializationFormat.SKOS,
        source_hash="test-hash",
        scope=scope,
        source_uri="test.skos",
        created_by="test-user",
    )

    # Set the correlation context
    set_import_run_context(import_run.id)

    try:
        # Verify context is set
        assert get_current_batch_run_id() == import_run.id

        # Record a change event within the import context
        change_repo.record_change(
            entity_id="test-entity-1",
            entity_type="taxonomy",
            operation=ChangeOperation.CREATE,
            new_state={"title": "Test"},
            change_reason="test change",
            batch_run_id=get_current_batch_run_id(),
        )

        # Verify the change event was recorded with the batch_run_id
        retrieved_events = change_repo.get_changes(limit=10).events
        assert len(retrieved_events) > 0
        # Check that at least one event has the batch_run_id
        events_with_import_run = [e for e in retrieved_events if e.batch_run_id == import_run.id]
        assert len(events_with_import_run) > 0
    finally:
        # Clear the context
        set_import_run_context(None)


def test_context_cleared_after_import(session_factory):
    """Context is cleared after import operation ends."""
    # Set context
    test_id = str(uuid4())
    set_import_run_context(test_id)
    assert get_current_batch_run_id() == test_id

    # Clear context
    set_import_run_context(None)
    assert get_current_batch_run_id() is None


def test_multiple_events_in_same_import_linked_to_same_run(change_repo):
    """Multiple operations in the same import are linked to the same run."""
    # Create an import run and set context
    import_service = ImportRunService()
    scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
    import_run = import_service.start_run(
        format=SerializationFormat.SKOS,
        source_hash="test-hash",
        scope=scope,
        source_uri="test.skos",
    )

    set_import_run_context(import_run.id)

    try:
        # Record multiple change events within the import context
        current_batch_run_id = get_current_batch_run_id()

        change_repo.record_change(
            entity_id="entity-1",
            entity_type="taxonomy",
            operation=ChangeOperation.CREATE,
            new_state={"title": "Taxonomy 1"},
            batch_run_id=current_batch_run_id,
        )

        change_repo.record_change(
            entity_id="entity-2",
            entity_type="concept_scheme",
            operation=ChangeOperation.CREATE,
            new_state={"title": "Scheme 1"},
            batch_run_id=current_batch_run_id,
        )

        change_repo.record_change(
            entity_id="entity-3",
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={"title": "Class 1"},
            batch_run_id=current_batch_run_id,
        )

        # Verify all change events have the same batch_run_id
        retrieved_events = change_repo.get_changes(limit=10).events

        # Should have at least 3 events
        assert len(retrieved_events) >= 3

        # All events should have the same batch_run_id
        for event in retrieved_events:
            if event.batch_run_id is not None:
                assert event.batch_run_id == import_run.id
    finally:
        set_import_run_context(None)


def test_change_event_recorder_auto_correlation_from_context(
    change_recorder, db_engine, change_repo
):
    """ChangeEventRecorder automatically reads batch_run_id from context."""
    # Create an import run and set context
    import_service = ImportRunService()
    scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
    import_run = import_service.start_run(
        format=SerializationFormat.SKOS,
        source_hash="test-hash",
        scope=scope,
        source_uri="test.skos",
    )

    # Set the correlation context
    set_import_run_context(import_run.id)

    try:
        # Verify context is set
        assert get_current_batch_run_id() == import_run.id

        # Call the _record() method directly to exercise the automatic correlation path
        # This simulates what happens when a domain event triggers the recorder
        change_recorder._record(
            entity_id="test-entity-auto",
            entity_type="taxonomy",
            operation=ChangeOperation.CREATE,
            new_state={"title": "Auto-correlated Taxonomy"},
            change_reason="Created during import",
        )

        # Verify the change event was recorded with the batch_run_id automatically
        retrieved_events = change_repo.get_changes(limit=10).events
        assert len(retrieved_events) > 0

        # Find the event we just recorded
        auto_correlated_events = [
            e
            for e in retrieved_events
            if e.entity_id == "test-entity-auto" and e.batch_run_id == import_run.id
        ]

        # Verify at least one event was auto-correlated
        assert len(auto_correlated_events) > 0
        assert auto_correlated_events[0].entity_type == "taxonomy"
        assert auto_correlated_events[0].operation == ChangeOperation.CREATE.value
    finally:
        # Clear the context
        set_import_run_context(None)
