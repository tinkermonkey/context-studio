"""
Integration tests for BatchRun ORM inheritance and migration.

Tests verify:
- Existing ImportRun records survive the joined-table inheritance migration
- ExtractionRun records work correctly through polymorphic queries
- ChangeEvent FK references to batch_run_id migrate correctly
- Both run types are queryable from the base BatchRun table
"""

import sys
import os
from uuid import uuid4
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base, BatchRun, ImportRun, ExtractionRun, ChangeEvent
from domain.versioning.value_objects import ChangeOperation


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
def session(session_factory):
    """Create a database session."""
    return session_factory()


class TestBatchRunBaseTable:
    """Tests for the BatchRun base table structure."""

    def test_batch_runs_table_exists(self, db_engine):
        """The batch_runs table exists and has required columns."""
        inspector = inspect(db_engine)
        assert "batch_runs" in inspector.get_table_names()

        columns = {col["name"] for col in inspector.get_columns("batch_runs")}
        assert "id" in columns
        assert "created_at" in columns
        assert "created_by" in columns
        assert "status" in columns
        assert "affected_entity_ids" in columns
        assert "run_type" in columns

    def test_import_runs_table_joined_to_batch_runs(self, db_engine):
        """The import_runs table is joined to batch_runs via FK."""
        inspector = inspect(db_engine)
        fks = inspector.get_foreign_keys("import_runs")

        batch_run_fks = [fk for fk in fks if fk["referred_table"] == "batch_runs"]
        assert len(batch_run_fks) > 0
        assert batch_run_fks[0]["referred_columns"] == ["id"]

    def test_extraction_runs_table_joined_to_batch_runs(self, db_engine):
        """The extraction_runs table is joined to batch_runs via FK."""
        inspector = inspect(db_engine)
        fks = inspector.get_foreign_keys("extraction_runs")

        batch_run_fks = [fk for fk in fks if fk["referred_table"] == "batch_runs"]
        assert len(batch_run_fks) > 0
        assert batch_run_fks[0]["referred_columns"] == ["id"]

    def test_change_events_has_batch_run_id_fk(self, db_engine):
        """The change_events table has batch_run_id FK to batch_runs."""
        inspector = inspect(db_engine)
        fks = inspector.get_foreign_keys("change_events")

        batch_run_fks = [fk for fk in fks if fk["referred_table"] == "batch_runs"]
        assert len(batch_run_fks) > 0
        assert batch_run_fks[0]["referred_columns"] == ["id"]


class TestImportRunPersistence:
    """Tests for ImportRun persistence in the joined-table hierarchy."""

    def test_insert_import_run(self, session):
        """Can insert and retrieve an ImportRun via SQLAlchemy ORM."""
        run_id = str(uuid4())
        now = datetime.now(timezone.utc)

        import_run = ImportRun(
            id=run_id,
            created_at=now,
            created_by="test-user",
            status="committed",
            affected_entity_ids=["entity1", "entity2"],
            run_type="import",
            format="skos",
            source_uri="test.skos",
            source_hash="abc123",
            scope_type="whole_graph",
        )

        session.add(import_run)
        session.commit()

        retrieved = session.query(ImportRun).filter_by(id=run_id).first()
        assert retrieved is not None
        assert retrieved.id == run_id
        assert retrieved.format == "skos"
        assert retrieved.status == "committed"

    def test_import_run_visible_from_batch_run_query(self, session):
        """An ImportRun is visible when queried from the base BatchRun table."""
        run_id = str(uuid4())
        now = datetime.now(timezone.utc)

        import_run = ImportRun(
            id=run_id,
            created_at=now,
            created_by="test-user",
            status="committed",
            affected_entity_ids=["entity1"],
            run_type="import",
            format="owl",
            source_uri="test.owl",
            source_hash="hash123",
            scope_type="taxonomy",
        )

        session.add(import_run)
        session.commit()

        # Query from base BatchRun table
        batch_run = session.query(BatchRun).filter_by(id=run_id).first()
        assert batch_run is not None
        assert batch_run.id == run_id
        assert batch_run.run_type == "import"

        # Verify it's actually an ImportRun
        assert isinstance(batch_run, ImportRun)
        assert batch_run.format == "owl"

    def test_import_run_with_multiple_affected_entities(self, session):
        """ImportRun can track multiple affected entity IDs as JSON."""
        run_id = str(uuid4())
        now = datetime.now(timezone.utc)
        entity_ids = [str(uuid4()) for _ in range(5)]

        import_run = ImportRun(
            id=run_id,
            created_at=now,
            created_by=None,
            status="pending",
            affected_entity_ids=entity_ids,
            run_type="import",
            format="graphml",
            source_uri=None,
            source_hash="xyz789",
            scope_type="entity_set",
        )

        session.add(import_run)
        session.commit()

        retrieved = session.query(ImportRun).filter_by(id=run_id).first()
        assert retrieved is not None
        assert set(retrieved.affected_entity_ids) == set(entity_ids)


class TestExtractionRunPersistence:
    """Tests for ExtractionRun persistence in the joined-table hierarchy."""

    def test_insert_extraction_run(self, session):
        """Can insert and retrieve an ExtractionRun via SQLAlchemy ORM."""
        run_id = str(uuid4())
        now = datetime.now(timezone.utc)

        extraction_run = ExtractionRun(
            id=run_id,
            created_at=now,
            created_by="test-user",
            status="completed",
            affected_entity_ids=["class1", "class2"],
            run_type="extraction",
            source_document_uri="https://example.com/doc.txt",
            source_text_hash="hash123",
            pipeline_config_ref="extraction-default",
            model="claude-opus-4-7",
            temperature=0.7,
            tokens_used=1500,
            duration_ms=5000,
            triples_extracted=25,
            triples_committed=20,
        )

        session.add(extraction_run)
        session.commit()

        retrieved = session.query(ExtractionRun).filter_by(id=run_id).first()
        assert retrieved is not None
        assert retrieved.id == run_id
        assert retrieved.model == "claude-opus-4-7"
        assert retrieved.temperature == 0.7
        assert retrieved.triples_extracted == 25
        assert retrieved.triples_committed == 20

    def test_extraction_run_visible_from_batch_run_query(self, session):
        """An ExtractionRun is visible when queried from the base BatchRun table."""
        run_id = str(uuid4())
        now = datetime.now(timezone.utc)

        extraction_run = ExtractionRun(
            id=run_id,
            created_at=now,
            created_by="extractor",
            status="pending",
            affected_entity_ids=["entity1"],
            run_type="extraction",
            source_document_uri=None,
            source_text_hash="texthash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
        )

        session.add(extraction_run)
        session.commit()

        # Query from base BatchRun table
        batch_run = session.query(BatchRun).filter_by(id=run_id).first()
        assert batch_run is not None
        assert batch_run.id == run_id
        assert batch_run.run_type == "extraction"

        # Verify it's actually an ExtractionRun
        assert isinstance(batch_run, ExtractionRun)
        assert batch_run.model == "gpt-4"

    def test_extraction_run_with_zero_metrics(self, session):
        """ExtractionRun with all metrics at zero (PENDING state)."""
        run_id = str(uuid4())
        now = datetime.now(timezone.utc)

        extraction_run = ExtractionRun(
            id=run_id,
            created_at=now,
            created_by=None,
            status="pending",
            affected_entity_ids=[],
            run_type="extraction",
            source_document_uri="pending.txt",
            source_text_hash="pendinghash",
            pipeline_config_ref="default",
            model="gpt-4-turbo",
            temperature=1.0,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
        )

        session.add(extraction_run)
        session.commit()

        retrieved = session.query(ExtractionRun).filter_by(id=run_id).first()
        assert retrieved is not None
        assert retrieved.status == "pending"
        assert retrieved.tokens_used == 0
        assert retrieved.duration_ms == 0


class TestPolymorphicQueries:
    """Tests for polymorphic queries across run types."""

    def test_query_all_batch_runs(self, session):
        """Query all batch runs regardless of type."""
        import_id = str(uuid4())
        extraction_id = str(uuid4())
        now = datetime.now(timezone.utc)

        import_run = ImportRun(
            id=import_id,
            created_at=now,
            created_by="user1",
            status="committed",
            affected_entity_ids=[],
            run_type="import",
            format="skos",
            source_uri="test.skos",
            source_hash="hash1",
            scope_type="whole_graph",
        )

        extraction_run = ExtractionRun(
            id=extraction_id,
            created_at=now,
            created_by="user2",
            status="completed",
            affected_entity_ids=[],
            run_type="extraction",
            source_document_uri=None,
            source_text_hash="hash2",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
            tokens_used=100,
            duration_ms=1000,
            triples_extracted=5,
            triples_committed=5,
        )

        session.add(import_run)
        session.add(extraction_run)
        session.commit()

        # Query all runs
        all_runs = session.query(BatchRun).all()
        assert len(all_runs) == 2

        run_ids = {run.id for run in all_runs}
        assert import_id in run_ids
        assert extraction_id in run_ids

    def test_filter_batch_runs_by_type(self, session):
        """Filter batch runs by run_type discriminator."""
        import_id = str(uuid4())
        extraction_id = str(uuid4())
        now = datetime.now(timezone.utc)

        import_run = ImportRun(
            id=import_id,
            created_at=now,
            created_by=None,
            status="pending",
            affected_entity_ids=[],
            run_type="import",
            format="owl",
            source_uri=None,
            source_hash="h1",
            scope_type="whole_graph",
        )

        extraction_run = ExtractionRun(
            id=extraction_id,
            created_at=now,
            created_by=None,
            status="pending",
            affected_entity_ids=[],
            run_type="extraction",
            source_document_uri=None,
            source_text_hash="h2",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.0,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
        )

        session.add(import_run)
        session.add(extraction_run)
        session.commit()

        # Query only imports
        import_runs = session.query(BatchRun).filter_by(run_type="import").all()
        assert len(import_runs) == 1
        assert import_runs[0].id == import_id
        assert isinstance(import_runs[0], ImportRun)

        # Query only extractions
        extraction_runs = session.query(BatchRun).filter_by(run_type="extraction").all()
        assert len(extraction_runs) == 1
        assert extraction_runs[0].id == extraction_id
        assert isinstance(extraction_runs[0], ExtractionRun)

    def test_filter_batch_runs_by_status(self, session):
        """Filter batch runs by status across types."""
        now = datetime.now(timezone.utc)

        completed_import = ImportRun(
            id=str(uuid4()),
            created_at=now,
            created_by=None,
            status="committed",
            affected_entity_ids=[],
            run_type="import",
            format="skos",
            source_uri=None,
            source_hash="h1",
            scope_type="whole_graph",
        )

        completed_extraction = ExtractionRun(
            id=str(uuid4()),
            created_at=now,
            created_by=None,
            status="completed",
            affected_entity_ids=[],
            run_type="extraction",
            source_document_uri=None,
            source_text_hash="h2",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.0,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
        )

        pending_extraction = ExtractionRun(
            id=str(uuid4()),
            created_at=now,
            created_by=None,
            status="pending",
            affected_entity_ids=[],
            run_type="extraction",
            source_document_uri=None,
            source_text_hash="h3",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.0,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
        )

        session.add_all([completed_import, completed_extraction, pending_extraction])
        session.commit()

        # Query completed/pending runs
        completed_runs = session.query(BatchRun).filter(
            BatchRun.status.in_(["committed", "completed"])
        ).all()
        assert len(completed_runs) == 2

        pending_runs = session.query(BatchRun).filter_by(status="pending").all()
        assert len(pending_runs) == 1


class TestChangeEventBatchRunForeignKey:
    """Tests for ChangeEvent FK references to batch_run_id."""

    def test_change_event_linked_to_import_run(self, session):
        """ChangeEvent can reference an ImportRun via batch_run_id."""
        import_id = str(uuid4())
        event_id = str(uuid4())
        now = datetime.now(timezone.utc)

        import_run = ImportRun(
            id=import_id,
            created_at=now,
            created_by=None,
            status="pending",
            affected_entity_ids=[],
            run_type="import",
            format="skos",
            source_uri=None,
            source_hash="hash",
            scope_type="whole_graph",
        )

        change_event = ChangeEvent(
            id=event_id,
            entity_id="entity1",
            entity_type="taxonomy",
            operation="create",
            new_state={"title": "Test"},
            timestamp=now,
            batch_run_id=import_id,
        )

        session.add(import_run)
        session.add(change_event)
        session.commit()

        retrieved_event = session.query(ChangeEvent).filter_by(id=event_id).first()
        assert retrieved_event is not None
        assert retrieved_event.batch_run_id == import_id

    def test_change_event_linked_to_extraction_run(self, session):
        """ChangeEvent can reference an ExtractionRun via batch_run_id."""
        extraction_id = str(uuid4())
        event_id = str(uuid4())
        now = datetime.now(timezone.utc)

        extraction_run = ExtractionRun(
            id=extraction_id,
            created_at=now,
            created_by=None,
            status="pending",
            affected_entity_ids=[],
            run_type="extraction",
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.0,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
        )

        change_event = ChangeEvent(
            id=event_id,
            entity_id="class1",
            entity_type="class",
            operation="create",
            new_state={"title": "Extracted Class"},
            timestamp=now,
            batch_run_id=extraction_id,
        )

        session.add(extraction_run)
        session.add(change_event)
        session.commit()

        retrieved_event = session.query(ChangeEvent).filter_by(id=event_id).first()
        assert retrieved_event is not None
        assert retrieved_event.batch_run_id == extraction_id

    def test_change_event_without_batch_run(self, session):
        """ChangeEvent can exist without a batch_run_id (null)."""
        event_id = str(uuid4())
        now = datetime.now(timezone.utc)

        change_event = ChangeEvent(
            id=event_id,
            entity_id="entity1",
            entity_type="class",
            operation="update",
            previous_state={"title": "Old"},
            new_state={"title": "New"},
            timestamp=now,
            batch_run_id=None,
        )

        session.add(change_event)
        session.commit()

        retrieved_event = session.query(ChangeEvent).filter_by(id=event_id).first()
        assert retrieved_event is not None
        assert retrieved_event.batch_run_id is None

    def test_change_events_by_batch_run(self, session):
        """Query all change events linked to a specific batch run."""
        run_id = str(uuid4())
        now = datetime.now(timezone.utc)

        extraction_run = ExtractionRun(
            id=run_id,
            created_at=now,
            created_by=None,
            status="pending",
            affected_entity_ids=[],
            run_type="extraction",
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.0,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
        )

        # Create multiple change events linked to the run
        events = [
            ChangeEvent(
                id=str(uuid4()),
                entity_id=f"entity{i}",
                entity_type="class",
                operation="create",
                new_state={"title": f"Entity {i}"},
                timestamp=now,
                batch_run_id=run_id,
            )
            for i in range(3)
        ]

        session.add(extraction_run)
        session.add_all(events)
        session.commit()

        # Query events by batch_run_id
        run_events = session.query(ChangeEvent).filter_by(batch_run_id=run_id).all()
        assert len(run_events) == 3
        for event in run_events:
            assert event.batch_run_id == run_id



class TestMixedBatchRunScenarios:
    """Tests for realistic mixed scenarios with multiple run types."""

    def test_workspace_with_mixed_runs(self, session):
        """A workspace can contain both import and extraction runs."""
        now = datetime.now(timezone.utc)

        # Create multiple runs
        import_run = ImportRun(
            id=str(uuid4()),
            created_at=now,
            created_by="alice",
            status="committed",
            affected_entity_ids=["e1", "e2"],
            run_type="import",
            format="skos",
            source_uri="data.skos",
            source_hash="import_hash",
            scope_type="whole_graph",
        )

        extraction_run1 = ExtractionRun(
            id=str(uuid4()),
            created_at=now,
            created_by="bob",
            status="completed",
            affected_entity_ids=["e3", "e4"],
            run_type="extraction",
            source_document_uri="doc1.txt",
            source_text_hash="doc1_hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.7,
            tokens_used=1000,
            duration_ms=3000,
            triples_extracted=10,
            triples_committed=10,
        )

        extraction_run2 = ExtractionRun(
            id=str(uuid4()),
            created_at=now,
            created_by="bob",
            status="failed",
            affected_entity_ids=[],
            run_type="extraction",
            source_document_uri="doc2.txt",
            source_text_hash="doc2_hash",
            pipeline_config_ref="default",
            model="claude-opus",
            temperature=0.5,
            tokens_used=500,
            duration_ms=2000,
            triples_extracted=5,
            triples_committed=0,
        )

        session.add_all([import_run, extraction_run1, extraction_run2])
        session.commit()

        # Verify all runs exist
        all_runs = session.query(BatchRun).all()
        assert len(all_runs) == 3

        # Verify counts by type
        imports = session.query(BatchRun).filter_by(run_type="import").all()
        extractions = session.query(BatchRun).filter_by(run_type="extraction").all()
        assert len(imports) == 1
        assert len(extractions) == 2

        # Verify status filtering across types
        completed = session.query(BatchRun).filter(
            BatchRun.status.in_(["committed", "completed"])
        ).all()
        assert len(completed) == 2

        failed = session.query(BatchRun).filter_by(status="failed").all()
        assert len(failed) == 1
