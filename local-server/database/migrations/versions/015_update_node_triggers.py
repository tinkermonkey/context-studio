"""Migration 015: Update structure_node triggers to fire specific event types for node_type and parent_node_id changes."""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration
import logging

logger = logging.getLogger(__name__)

class Migration015(Migration):
    """Update structure_node triggers to generate update-type and move events."""
    version = 15
    description = "Update structure_node triggers for specific event types (update-type, move)"

    def up(self, connection: Connection) -> None:
        """Apply the migration - update the structure_node update trigger."""
        logger.info("Updating structure_node update trigger...")

        # Drop the existing trigger
        connection.execute(text("DROP TRIGGER IF EXISTS trg_structure_node_update;"))

        # Create the updated trigger with specific event type logic
        connection.execute(text("""
            CREATE TRIGGER trg_structure_node_update AFTER UPDATE ON structure_nodes
            BEGIN
              -- Generate update-type event if node_type changed
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              SELECT 'update-type', 'structure_node', NEW.id,
                     json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_node_id', OLD.parent_node_id,
                                'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id,
                                'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified),
                     json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_node_id', NEW.parent_node_id,
                                'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id,
                                'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified),
                     CURRENT_TIMESTAMP, 0
              WHERE OLD.node_type != NEW.node_type;

              -- Generate move event if parent_node_id changed
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              SELECT 'move', 'structure_node', NEW.id,
                     json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_node_id', OLD.parent_node_id,
                                'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id,
                                'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified),
                     json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_node_id', NEW.parent_node_id,
                                'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id,
                                'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified),
                     CURRENT_TIMESTAMP, 0
              WHERE (OLD.parent_node_id IS NULL AND NEW.parent_node_id IS NOT NULL)
                 OR (OLD.parent_node_id IS NOT NULL AND NEW.parent_node_id IS NULL)
                 OR (OLD.parent_node_id != NEW.parent_node_id);

              -- Generate generic update event for other field changes (if neither node_type nor parent_node_id changed)
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              SELECT 'update', 'structure_node', NEW.id,
                     json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_node_id', OLD.parent_node_id,
                                'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id,
                                'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified),
                     json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_node_id', NEW.parent_node_id,
                                'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id,
                                'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified),
                     CURRENT_TIMESTAMP, 0
              WHERE OLD.node_type = NEW.node_type
                AND (OLD.parent_node_id IS NEW.parent_node_id OR (OLD.parent_node_id = NEW.parent_node_id));
            END;
        """))

        logger.info("Structure_node update trigger updated successfully!")

    def down(self, connection: Connection) -> None:
        """Rollback the migration - restore the original trigger."""
        logger.info("Rolling back structure_node update trigger...")

        # Drop the updated trigger
        connection.execute(text("DROP TRIGGER IF EXISTS trg_structure_node_update;"))

        # Restore the original trigger with generic update event
        connection.execute(text("""
            CREATE TRIGGER trg_structure_node_update AFTER UPDATE ON structure_nodes
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('update', 'structure_node', NEW.id,
                      json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_node_id', OLD.parent_node_id,
                                 'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id,
                                 'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified),
                      json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_node_id', NEW.parent_node_id,
                                 'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id,
                                 'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified),
                      CURRENT_TIMESTAMP, 0);
            END;
        """))

        logger.info("Structure_node update trigger rollback completed!")
