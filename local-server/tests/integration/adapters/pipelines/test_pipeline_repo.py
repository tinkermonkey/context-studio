"""
Integration tests for PipelineRepository

Tests persistence and retrieval of pipeline runs in SQLite.
Tests change_events correlation with batch_run_id.
"""

import os
import sys
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from adapters.persistence.sqlite.models import Base, ChangeEvent
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from domain.pipelines.entities import PipelineRunStatus, PipelineType

@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestPipelineRepositoryCreate:
    """Tests for PipelineRepository.create()"""

    def test_create_individual_extraction_run(self, db_session):
        """Test creating an individual extraction pipeline run."""
        repo = PipelineRepository(db_session)
        batch_id = str(uuid4())

        run = repo.create(
            batch_run_id=batch_id,
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="impl-default",
            configuration_ref="extraction-default",
            specific_data={
                "source_text_hash": "abc123def456",
                "source_document_uri": "s3://bucket/doc.txt",
            },
        )

        assert run.id == batch_id
        assert run.batch_run_id == batch_id
        assert run.pipeline_type == PipelineType.INDIVIDUAL_EXTRACTION
        assert run.status == PipelineRunStatus.PENDING
        assert run.source_text_hash == "abc123def456"
        assert run.source_document_uri == "s3://bucket/doc.txt"

    def test_create_schema_extraction_run(self, db_session):
        """Test creating a schema extraction pipeline run."""
        repo = PipelineRepository(db_session)
        batch_id = str(uuid4())

        run = repo.create(
            batch_run_id=batch_id,
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            implementation_id="impl-schema",
            configuration_ref="schema-default",
        )

        assert run.pipeline_type == PipelineType.SCHEMA_EXTRACTION
        assert run.status == PipelineRunStatus.PENDING


class TestPipelineRepositoryQuery:
    """Tests for PipelineRepository query methods."""

    def test_get_run_by_id(self, db_session):
        """Test retrieving a run by ID."""
        repo = PipelineRepository(db_session)
        batch_id = str(uuid4())

        created = repo.create(
            batch_run_id=batch_id,
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="impl-default",
            configuration_ref="extraction-default",
            specific_data={"source_text_hash": "abc123"},
        )

        retrieved = repo.get(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.pipeline_type == PipelineType.INDIVIDUAL_EXTRACTION

    def test_list_by_status(self, db_session):
        """Test listing runs by status."""
        repo = PipelineRepository(db_session)

        run1 = repo.create(
            batch_run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="impl-1",
            configuration_ref="config-1",
            specific_data={"source_text_hash": "hash1"},
        )

        run2 = repo.create(
            batch_run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            implementation_id="impl-2",
            configuration_ref="config-2",
        )

        # Both should be PENDING
        pending = repo.list_by_status(PipelineRunStatus.PENDING)
        assert len(pending) >= 2
        ids = [r.id for r in pending]
        assert run1.id in ids
        assert run2.id in ids

    def test_list_by_type(self, db_session):
        """Test listing runs by pipeline type."""
        repo = PipelineRepository(db_session)

        extraction_run = repo.create(
            batch_run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="impl-extraction",
            configuration_ref="config-extraction",
            specific_data={"source_text_hash": "hash1"},
        )

        schema_run = repo.create(
            batch_run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            implementation_id="impl-schema",
            configuration_ref="config-schema",
        )

        # List individual extraction runs
        extractions = repo.list_by_type(PipelineType.INDIVIDUAL_EXTRACTION)
        extraction_ids = [r.id for r in extractions]
        assert extraction_run.id in extraction_ids

        # List schema extraction runs
        schemas = repo.list_by_type(PipelineType.SCHEMA_EXTRACTION)
        schema_ids = [r.id for r in schemas]
        assert schema_run.id in schema_ids

    def test_list_all_runs(self, db_session):
        """Test listing all pipeline runs."""
        repo = PipelineRepository(db_session)

        run1 = repo.create(
            batch_run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="impl-1",
            configuration_ref="config-1",
            specific_data={"source_text_hash": "hash1"},
        )

        run2 = repo.create(
            batch_run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            implementation_id="impl-2",
            configuration_ref="config-2",
        )

        # List all runs
        all_runs = repo.list()
        assert len(all_runs) >= 2
        run_ids = [r.id for r in all_runs]
        assert run1.id in run_ids
        assert run2.id in run_ids


class TestPipelineRepositoryUpdate:
    """Tests for PipelineRepository update methods."""

    def test_update_status(self, db_session):
        """Test updating a run's status."""
        repo = PipelineRepository(db_session)
        batch_id = str(uuid4())

        run = repo.create(
            batch_run_id=batch_id,
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="impl-default",
            configuration_ref="config-default",
            specific_data={"source_text_hash": "hash123"},
        )

        success = repo.update_status(run.id, PipelineRunStatus.RUNNING)
        assert success

        updated = repo.get(run.id)
        assert updated.status == PipelineRunStatus.RUNNING

    def test_update_summaries(self, db_session):
        """Test updating input/output summaries."""
        repo = PipelineRepository(db_session)
        batch_id = str(uuid4())

        run = repo.create(
            batch_run_id=batch_id,
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="impl-default",
            configuration_ref="config-default",
            specific_data={"source_text_hash": "hash123"},
        )

        input_summary = {"text_length": 1000, "ontology_id": "onto-123"}
        output_summary = {"triples_extracted": 42, "triples_committed": 38}
        llm_metadata = {
            "model": "gpt-4",
            "tokens_used": 2000,
            "duration_ms": 5000,
        }

        success = repo.update_summaries(
            run.id,
            input_summary=input_summary,
            output_summary=output_summary,
            llm_metadata=llm_metadata,
        )
        assert success

        updated = repo.get(run.id)
        assert updated.input_summary == input_summary
        assert updated.output_summary == output_summary
        assert updated.llm_metadata == llm_metadata


class TestPipelineRepositoryChangeEvents:
    """Tests for change_events correlation."""

    def test_get_change_events_for_run(self, db_session):
        """Test retrieving change_events correlated with a pipeline run."""
        repo = PipelineRepository(db_session)
        batch_id = str(uuid4())

        # Create a pipeline run
        run = repo.create(
            batch_run_id=batch_id,
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="impl-default",
            configuration_ref="config-default",
            specific_data={"source_text_hash": "hash123"},
        )

        # Create change events linked to the batch run
        event1 = ChangeEvent(
            id="event-1",
            entity_type="Class",
            entity_id="class-123",
            operation="create",
            timestamp=datetime.now(timezone.utc),
            batch_run_id=batch_id,
            new_state={"label": "Class1", "uri": "http://example.org/Class1"},
        )
        event2 = ChangeEvent(
            id="event-2",
            entity_type="Class",
            entity_id="class-456",
            operation="create",
            timestamp=datetime.now(timezone.utc),
            batch_run_id=batch_id,
            new_state={"label": "Class2", "uri": "http://example.org/Class2"},
        )
        db_session.add(event1)
        db_session.add(event2)
        db_session.flush()

        # Retrieve events for the pipeline run
        events = repo.get_change_events_for_run(run.id)
        assert len(events) == 2
        event_ids = [e["entity_id"] for e in events]
        assert "class-123" in event_ids
        assert "class-456" in event_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
