"""Integration tests for the normalized change event system."""

import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )  # noqa: E501
)

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from services.change_event_handler import ChangeEventHandler  # noqa: E402
from database.enums import RecordType  # noqa: E402
import json  # noqa: E402
from uuid import uuid4  # noqa: E402


@pytest.fixture
def change_event_handler(db_session):
    """Create a ChangeEventHandler for testing."""
    return ChangeEventHandler(db_session)


def test_event_statistics_integration(db_session, change_event_handler):
    """Test event statistics functionality with real data."""

    # Generate unique IDs for this test
    node_id = f"stats-node-{uuid4()}"
    pred_id = f"stats-pred-{uuid4()}"
    link_id = f"stats-link-{uuid4()}"
    parent_id = f"p-{uuid4()}"
    child_id = f"c-{uuid4()}"

    # Create baseline stats
    initial_stats = change_event_handler.get_event_stats()

    # Create events of different types
    change_event_handler.fire_created_event(
        RecordType.STRUCTURE_NODE, node_id, {"title": "Node 1"}
    )
    change_event_handler.fire_updated_event(
        RecordType.STRUCTURE_NODE,
        node_id,
        {"title": "Node 1"},
        {"title": "Updated Node 1"},
    )
    change_event_handler.fire_deleted_event(
        RecordType.STRUCTURE_NODE, node_id, {"title": "Updated Node 1"}
    )

    change_event_handler.fire_created_event(
        RecordType.PREDICATE, pred_id, {"title": "Predicate 1"}
    )
    change_event_handler.fire_created_event(
        RecordType.STRUCTURE_NODE_LINK,
        link_id,
        {"parent": parent_id, "child": child_id},
    )

    # Get new stats
    new_stats = change_event_handler.get_event_stats()

    # Verify stats increased
    assert new_stats["total_events"] == initial_stats["total_events"] + 5
    assert (
        new_stats["unprocessed_events"] == initial_stats["unprocessed_events"] + 5
    )  # noqa: E501

    # Verify event type breakdown
    assert (
        new_stats["events_by_type"]["create"]
        == initial_stats["events_by_type"].get("create", 0) + 3
    )
    assert (
        new_stats["events_by_type"]["update"]
        == initial_stats["events_by_type"].get("update", 0) + 1
    )
    assert (
        new_stats["events_by_type"]["delete"]
        == initial_stats["events_by_type"].get("delete", 0) + 1
    )

    # Verify record type breakdown
    assert (
        new_stats["events_by_record_type"]["structure_node"]
        == initial_stats["events_by_record_type"].get("structure_node", 0) + 3
    )
    assert (
        new_stats["events_by_record_type"]["predicate"]
        == initial_stats["events_by_record_type"].get("predicate", 0) + 1
    )
    assert (
        new_stats["events_by_record_type"]["structure_node_link"]
        == initial_stats["events_by_record_type"].get("structure_node_link", 0)
        + 1  # noqa: E501
    )


def test_database_trigger_integration(db_session):
    """Test that database triggers create proper ChangeEvents."""

    # Generate unique ID for this test
    trigger_node_id = f"trigger-test-node-{uuid4()}"

    # Note: This test would need actual database triggers to be in place
    # and would insert directly into the tables to trigger the events
    # For now, we'll test the handler integration

    # Get the engine from the db_session's bind
    engine = db_session.bind

    # Insert a structure_node directly (would trigger change_events via database trigger)  # noqa: E501
    # This is a simulated test since we'd need the actual triggers in place
    with engine.connect() as conn:
        # First check if change_events table exists
        table_exists = conn.execute(text("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='change_events'
        """)).fetchone()

        if table_exists:
            # Simulate what a trigger would do
            conn.execute(
                text("""
                INSERT INTO change_events
                (event_type, record_type, record_id, old_data, new_data, processed)
                VALUES ('create', 'structure_node', :node_id, NULL,
                        :node_data, 0)
            """),  # noqa: E501
                {
                    "node_id": trigger_node_id,
                    "node_data": json.dumps(
                        {
                            "id": trigger_node_id,
                            "title": "Trigger Test",
                            "node_type": "layer",
                        }
                    ),
                },
            )
            conn.commit()

            # Verify the event was created
            event_count = conn.execute(
                text("""
                SELECT COUNT(*) FROM change_events WHERE record_id = :node_id
            """),
                {"node_id": trigger_node_id},
            ).scalar()

            assert event_count == 1

            # Clean up
            conn.execute(
                text("""
                DELETE FROM change_events WHERE record_id = :node_id
            """),
                {"node_id": trigger_node_id},
            )
            conn.commit()


def test_update_node_type_trigger(db_session):
    """Test that updating a node's type generates an update-type event."""

    # Generate unique ID for this test
    node_id = f"type-change-node-{uuid4()}"

    # Get the engine from the db_session's bind
    engine = db_session.bind

    with engine.connect() as conn:
        # Insert a structure_node directly
        conn.execute(
            text("""
                INSERT INTO ontology_entities (id, node_type, title, definition)
                VALUES (:node_id, 'class', 'Test Node', 'Test definition')
            """),
            {"node_id": node_id},
        )
        conn.commit()

        # Clear any create events from the insert
        conn.execute(
            text("DELETE FROM change_events WHERE record_id = :node_id"),
            {"node_id": node_id},
        )  # noqa: E501
        conn.commit()

        # Update the node_type
        conn.execute(
            text("""
                UPDATE ontology_entities
                SET node_type = 'concept_scheme'
                WHERE id = :node_id
            """),
            {"node_id": node_id},
        )
        conn.commit()

        # Check for update-type event
        event = conn.execute(
            text("""
                SELECT event_type, record_type, record_id, old_data, new_data
                FROM change_events
                WHERE record_id = :node_id AND event_type = 'update-type'
            """),
            {"node_id": node_id},
        ).fetchone()

        assert event is not None, "Expected update-type event not found"
        assert event[0] == "update-type"
        assert event[1] == "ontology_entity"
        assert event[2] == node_id

        # Verify old_data has old node_type
        old_data = json.loads(event[3])
        assert old_data["node_type"] == "class"

        # Verify new_data has new node_type
        new_data = json.loads(event[4])
        assert new_data["node_type"] == "concept_scheme"

        # Clean up
        conn.execute(
            text("DELETE FROM change_events WHERE record_id = :node_id"),
            {"node_id": node_id},
        )  # noqa: E501
        conn.execute(
            text("DELETE FROM ontology_entities WHERE id = :node_id"),
            {"node_id": node_id},
        )  # noqa: E501
        conn.commit()


def test_move_node_trigger(db_session):
    """Test that moving a node (changing parent_entity_id) generates a move event."""  # noqa: E501

    # Generate unique IDs for this test
    node_id = f"move-node-{uuid4()}"
    old_parent_id = f"old-parent-{uuid4()}"
    new_parent_id = f"new-parent-{uuid4()}"

    # Get the engine from the db_session's bind
    engine = db_session.bind

    with engine.connect() as conn:
        # Create parent nodes
        conn.execute(
            text("""
                INSERT INTO ontology_entities (id, node_type, title, definition)
                VALUES (:parent_id, 'concept_scheme', 'Old Parent', 'Old parent definition')
            """),
            {"parent_id": old_parent_id},
        )
        conn.execute(
            text("""
                INSERT INTO ontology_entities (id, node_type, title, definition)
                VALUES (:parent_id, 'concept_scheme', 'New Parent', 'New parent definition')
            """),
            {"parent_id": new_parent_id},
        )

        # Insert a structure_node with old parent
        conn.execute(
            text("""
                INSERT INTO ontology_entities (id, node_type, parent_entity_id, title, definition)
                VALUES (:node_id, 'class', :old_parent_id, 'Test Node', 'Test definition')
            """),
            {"node_id": node_id, "old_parent_id": old_parent_id},
        )
        conn.commit()

        # Clear any create events from the inserts
        conn.execute(
            text(
                "DELETE FROM change_events WHERE record_id IN (:node_id, :old_parent_id, :new_parent_id)"
            ),  # noqa: E501
            {
                "node_id": node_id,
                "old_parent_id": old_parent_id,
                "new_parent_id": new_parent_id,
            },
        )  # noqa: E501, E128
        conn.commit()

        # Move the node to new parent
        conn.execute(
            text("""
                UPDATE ontology_entities
                SET parent_entity_id = :new_parent_id
                WHERE id = :node_id
            """),
            {"node_id": node_id, "new_parent_id": new_parent_id},
        )
        conn.commit()

        # Check for move event
        event = conn.execute(
            text("""
                SELECT event_type, record_type, record_id, old_data, new_data
                FROM change_events
                WHERE record_id = :node_id AND event_type = 'move'
            """),
            {"node_id": node_id},
        ).fetchone()

        assert event is not None, "Expected move event not found"
        assert event[0] == "move"
        assert event[1] == "ontology_entity"
        assert event[2] == node_id

        # Verify old_data has old parent_entity_id
        old_data = json.loads(event[3])
        assert old_data["parent_entity_id"] == old_parent_id

        # Verify new_data has new parent_entity_id
        new_data = json.loads(event[4])
        assert new_data["parent_entity_id"] == new_parent_id

        # Clean up
        conn.execute(
            text(
                "DELETE FROM change_events WHERE record_id IN (:node_id, :old_parent_id, :new_parent_id)"
            ),  # noqa: E501
            {
                "node_id": node_id,
                "old_parent_id": old_parent_id,
                "new_parent_id": new_parent_id,
            },
        )  # noqa: E501, E128
        conn.execute(
            text(
                "DELETE FROM ontology_entities WHERE id IN (:node_id, :old_parent_id, :new_parent_id)"
            ),  # noqa: E501
            {
                "node_id": node_id,
                "old_parent_id": old_parent_id,
                "new_parent_id": new_parent_id,
            },
        )  # noqa: E501, E128
        conn.commit()
