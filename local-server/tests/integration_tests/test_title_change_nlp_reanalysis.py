"""
Integration tests for automatic NLP re-analysis on title changes.

Tests the complete flow:
1. Structure node title is changed
2. EventProcessor detects the change
3. Async NLP re-analysis is triggered
4. Word senses are updated conservatively
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
import json
import asyncio
import time
from uuid import uuid4
from sqlalchemy import text

from database.utils import get_database_manager
from database.models import StructureNode
from database.enums import NodeType
from utils.event_processor import EventProcessor
from services.task_manager import TaskManager
from api.models.structure_nodes import WordSense


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    db_manager = get_database_manager()
    db_url = "sqlite:///test_title_change_nlp.db"

    # Create optimized engine
    engine_id = "test_title_change_nlp"
    db_manager.create_optimized_engine(db_url, engine_id)

    # Create tables
    from database.models import Base
    engine = db_manager._engines[engine_id]
    Base.metadata.create_all(engine)

    # Get session
    with db_manager.get_optimized_session(engine_id, db_url) as db:
        yield db

    # Cleanup
    db_manager.close_engine(engine_id)

    # Remove test database file
    try:
        os.remove("test_title_change_nlp.db")
    except:
        pass


@pytest.fixture
async def task_manager():
    """Create and start a task manager for tests."""
    tm = TaskManager(max_queue_size=50)
    await tm.start()
    yield tm
    await tm.shutdown()


@pytest.fixture
def event_processor(test_db, task_manager):
    """Create an EventProcessor instance."""
    db_url = "sqlite:///test_title_change_nlp.db"
    processor = EventProcessor(
        database_url=db_url,
        poll_interval=0.1,  # Fast polling for tests
        max_events=10
    )
    yield processor
    processor.stop()


@pytest.mark.asyncio
async def test_title_change_triggers_nlp_reanalysis(test_db, task_manager, event_processor):
    """Test that changing a structure node title triggers NLP re-analysis."""

    # Create a structure node with an initial title
    node_id = str(uuid4())
    node = StructureNode(
        id=node_id,
        node_type=NodeType.TERM,
        parent_node_id=str(uuid4()),  # Mock parent
        title="bank",
        definition="A financial institution",
        word_senses=json.dumps([
            {
                "term": "bank",
                "sense_type": "wordnet",
                "sense_id": "bank.n.01",
                "definition": "financial institution",
                "domain": "noun.group"
            },
            {
                "term": "bank",
                "sense_type": "wordnet",
                "sense_id": "bank.n.02",
                "definition": "sloping land beside water",
                "domain": "noun.object"
            }
        ]),
        version=1
    )
    test_db.add(node)
    test_db.commit()

    # Create a change event for title update
    old_data = {
        "id": node_id,
        "title": "bank",
        "definition": "A financial institution",
        "node_type": "term",
        "version": 1
    }

    new_data = {
        "id": node_id,
        "title": "river",  # Changed title
        "definition": "A financial institution",
        "node_type": "term",
        "version": 2
    }

    test_db.execute(text("""
        INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, processed, timestamp)
        VALUES (:event_type, :record_type, :record_id, :old_data, :new_data, 0, :timestamp)
    """), {
        "event_type": "update",
        "record_type": "structure_node",
        "record_id": node_id,
        "old_data": json.dumps(old_data),
        "new_data": json.dumps(new_data),
        "timestamp": "2025-01-01T00:00:00Z"
    })
    test_db.commit()

    # Start the event processor
    event_processor.start()

    # Wait for event to be processed and task to be queued
    await asyncio.sleep(0.5)

    # Check that the event was processed
    result = test_db.execute(text("SELECT processed FROM change_events WHERE record_id = :node_id"),
                            {"node_id": node_id}).fetchone()
    assert result is not None
    assert result[0] == 1, "Event should be marked as processed"

    # Check that a task was created
    stats = task_manager.get_stats()
    assert stats["total_tasks"] > 0, "At least one task should be created"

    # Wait for the task to complete (with timeout)
    max_wait = 10
    waited = 0
    task_completed = False

    while waited < max_wait:
        stats = task_manager.get_stats()
        if stats["status_counts"]["completed"] > 0:
            task_completed = True
            break
        await asyncio.sleep(0.5)
        waited += 0.5

    assert task_completed, "NLP re-analysis task should complete within timeout"

    # Verify word senses were updated
    # Note: This will depend on whether NLP pipeline is available in test environment
    # We're mainly testing the event detection and task queuing


@pytest.mark.asyncio
async def test_title_change_preserves_matching_senses(test_db):
    """Test that conservative filtering preserves word senses that still match."""
    from services.word_sense_service import WordSenseService

    # Create a structure node with word senses
    node_id = str(uuid4())
    initial_senses = [
        WordSense(
            term="run",
            sense_type="wordnet",
            sense_id="run.v.01",
            definition="move fast by using one's feet",
            domain="verb.motion"
        ),
        WordSense(
            term="run",
            sense_type="wordnet",
            sense_id="run.v.02",
            definition="operate or function",
            domain="verb.contact"
        ),
        WordSense(
            term="run",
            sense_type="wordnet",
            sense_id="run.v.03",
            definition="manage or control",
            domain="verb.social"
        )
    ]

    node = StructureNode(
        id=node_id,
        node_type=NodeType.TERM,
        parent_node_id=str(uuid4()),
        title="run fast",
        word_senses=json.dumps([sense.model_dump() for sense in initial_senses]),
        version=1
    )
    test_db.add(node)
    test_db.commit()

    # Simulate new NLP analysis that finds only 2 of the 3 senses
    new_senses = [
        WordSense(
            term="run",
            sense_type="wordnet",
            sense_id="run.v.01",  # Still present
            definition="move fast by using one's feet",
            domain="verb.motion"
        ),
        WordSense(
            term="run",
            sense_type="wordnet",
            sense_id="run.v.02",  # Still present
            definition="operate or function",
            domain="verb.contact"
        )
        # run.v.03 is not in new analysis - should be removed
    ]

    # Update word senses with conservative filtering
    word_sense_service = WordSenseService(test_db)
    updated_senses = word_sense_service.update_word_senses(
        node_id=node_id,
        new_senses=new_senses,
        conservative=True
    )

    # Verify results
    assert len(updated_senses) == 2, "Should have 2 senses after conservative update"

    sense_ids = {sense.sense_id for sense in updated_senses}
    assert "run.v.01" in sense_ids, "Matching sense should be preserved"
    assert "run.v.02" in sense_ids, "Matching sense should be preserved"
    assert "run.v.03" not in sense_ids, "Non-matching sense should be removed"


@pytest.mark.asyncio
async def test_title_change_handles_empty_senses(test_db):
    """Test handling of nodes with no existing word senses."""
    from services.word_sense_service import WordSenseService

    # Create a structure node without word senses
    node_id = str(uuid4())
    node = StructureNode(
        id=node_id,
        node_type=NodeType.TERM,
        parent_node_id=str(uuid4()),
        title="test",
        word_senses=None,  # No existing senses
        version=1
    )
    test_db.add(node)
    test_db.commit()

    # Simulate new NLP analysis with some senses
    new_senses = [
        WordSense(
            term="test",
            sense_type="wordnet",
            sense_id="test.n.01",
            definition="a trial or examination",
            domain="noun.act"
        )
    ]

    # Update word senses
    word_sense_service = WordSenseService(test_db)
    updated_senses = word_sense_service.update_word_senses(
        node_id=node_id,
        new_senses=new_senses,
        conservative=True
    )

    # Verify results
    assert len(updated_senses) == 1, "Should have 1 sense after update"
    assert updated_senses[0].sense_id == "test.n.01"


@pytest.mark.asyncio
async def test_title_change_handles_malformed_data(test_db, event_processor):
    """Test that malformed event data doesn't crash the processor."""

    # Create a change event with malformed JSON
    node_id = str(uuid4())

    test_db.execute(text("""
        INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, processed, timestamp)
        VALUES (:event_type, :record_type, :record_id, :old_data, :new_data, 0, :timestamp)
    """), {
        "event_type": "update",
        "record_type": "structure_node",
        "record_id": node_id,
        "old_data": "not valid json{",  # Malformed
        "new_data": json.dumps({"title": "test"}),
        "timestamp": "2025-01-01T00:00:00Z"
    })
    test_db.commit()

    # Start the event processor
    event_processor.start()

    # Wait for event processing
    await asyncio.sleep(0.5)

    # Event should still be processed (marked as processed even if title change handling failed)
    result = test_db.execute(text("SELECT processed FROM change_events WHERE record_id = :node_id"),
                            {"node_id": node_id}).fetchone()
    assert result is not None
    # The event should be marked as processed (we log errors but don't fail the entire event)
    assert result[0] == 1, "Event should be marked as processed despite malformed data"


@pytest.mark.asyncio
async def test_no_title_change_no_reanalysis(test_db, task_manager, event_processor):
    """Test that non-title changes don't trigger NLP re-analysis."""

    # Create a structure node
    node_id = str(uuid4())
    node = StructureNode(
        id=node_id,
        node_type=NodeType.TERM,
        parent_node_id=str(uuid4()),
        title="bank",
        definition="A financial institution",
        version=1
    )
    test_db.add(node)
    test_db.commit()

    # Create a change event that only changes definition (not title)
    old_data = {
        "id": node_id,
        "title": "bank",  # Same title
        "definition": "A financial institution",
        "version": 1
    }

    new_data = {
        "id": node_id,
        "title": "bank",  # Same title
        "definition": "A place where money is kept",  # Changed definition
        "version": 2
    }

    test_db.execute(text("""
        INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, processed, timestamp)
        VALUES (:event_type, :record_type, :record_id, :old_data, :new_data, 0, :timestamp)
    """), {
        "event_type": "update",
        "record_type": "structure_node",
        "record_id": node_id,
        "old_data": json.dumps(old_data),
        "new_data": json.dumps(new_data),
        "timestamp": "2025-01-01T00:00:00Z"
    })
    test_db.commit()

    # Get initial task count
    initial_task_count = task_manager.get_stats()["total_tasks"]

    # Start the event processor
    event_processor.start()

    # Wait for event processing
    await asyncio.sleep(0.5)

    # Verify no new tasks were created
    final_task_count = task_manager.get_stats()["total_tasks"]
    assert final_task_count == initial_task_count, "No tasks should be created for non-title changes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
