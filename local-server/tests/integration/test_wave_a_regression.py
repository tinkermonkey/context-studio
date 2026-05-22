"""
Wave A regression tests for IndividualExtractionRun and change_event lineage.

Verifies that:
1. POST /api/extraction/extract continues to function (tested in test_extraction_routes.py)
2. IndividualExtractionRun (migrated from ExtractionRun) produces correct change_event lineage
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base, ChangeEvent
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from domain.pipelines.entities import PipelineRunStatus, PipelineType


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

        yield db_url


@pytest.fixture
def session_factory(temp_db):
    """Create a session factory for the temporary database."""
    engine = create_engine(temp_db)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


class TestWaveARegression:
    """Test Wave A extraction functionality and change_event lineage."""

    def test_individual_extraction_run_maintains_change_event_lineage(
        self, session_factory
    ):
        """
        Verify IndividualExtractionRun maintains change_event lineage through batch_run_id.

        This is a regression test for Wave A's extraction functionality, ensuring that
        the migration to the new pipeline framework doesn't break change_event tracking.
        """
        session = session_factory()
        pipeline_repo = PipelineRepository(session)

        # Create an IndividualExtractionRun (this is the migrated Wave A ExtractionRun)
        batch_run_id = str(uuid4())
        run = pipeline_repo.create(
            batch_run_id=batch_run_id,
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            implementation_id="impl-extraction",
            configuration_ref="extraction-v1",
            specific_data={
                "source_text_hash": "sha256_abcdef123456",
                "source_document_uri": "s3://bucket/document.txt",
            },
        )

        # Verify the run was created with correct type and status
        assert run.pipeline_type == PipelineType.INDIVIDUAL_EXTRACTION
        assert run.status == PipelineRunStatus.PENDING
        assert run.source_text_hash == "sha256_abcdef123456"
        assert run.source_document_uri == "s3://bucket/document.txt"

        # Create change events linked to this batch run
        # These represent entities created/modified during extraction
        event1 = ChangeEvent(
            id=str(uuid4()),
            entity_type="Class",
            entity_id=str(uuid4()),
            operation="create",
            timestamp=datetime.now(timezone.utc),
            batch_run_id=batch_run_id,
            new_state={
                "label": "ExtractedClass1",
                "uri": "http://example.org/ExtractedClass1"
            },
        )
        event2 = ChangeEvent(
            id=str(uuid4()),
            entity_type="Relationship",
            entity_id=str(uuid4()),
            operation="create",
            timestamp=datetime.now(timezone.utc),
            batch_run_id=batch_run_id,
            new_state={
                "source": "Class1",
                "target": "Class2",
                "type": "hasProperty"
            },
        )
        session.add(event1)
        session.add(event2)
        session.flush()

        # Retrieve the run and verify it's retrievable
        retrieved_run = pipeline_repo.get(run.id)
        assert retrieved_run is not None
        assert retrieved_run.batch_run_id == batch_run_id

        # Verify change_events are properly correlated with the pipeline run
        events = pipeline_repo.get_change_events_for_run(run.id)
        assert len(events) == 2

        # Verify event structure and batch_run_id correlation
        entity_ids = [e["entity_id"] for e in events]
        assert event1.entity_id in entity_ids
        assert event2.entity_id in entity_ids

        for event in events:
            assert event["batch_run_id"] == batch_run_id
            assert "operation" in event
            assert "timestamp" in event

        session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
