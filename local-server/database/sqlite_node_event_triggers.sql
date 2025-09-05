-- SQLite triggers for node_events table (normalized schema)

-- Node triggers
CREATE TRIGGER IF NOT EXISTS trg_node_insert AFTER INSERT ON nodes
BEGIN
  INSERT INTO node_events (event_type, node_type, old_data, new_data, timestamp, processed)
  VALUES ('create', NEW.node_type, NULL, json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_node_id', NEW.parent_node_id, 'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id, 'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified), CURRENT_TIMESTAMP, 0);
END;

CREATE TRIGGER IF NOT EXISTS trg_node_update AFTER UPDATE ON nodes
BEGIN
  INSERT INTO node_events (event_type, node_type, old_data, new_data, timestamp, processed)
  VALUES ('update', NEW.node_type, json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_node_id', OLD.parent_node_id, 'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id, 'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified), json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_node_id', NEW.parent_node_id, 'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id, 'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified), CURRENT_TIMESTAMP, 0);
END;

CREATE TRIGGER IF NOT EXISTS trg_node_delete AFTER DELETE ON nodes
BEGIN
  INSERT INTO node_events (event_type, node_type, old_data, new_data, timestamp, processed)
  VALUES ('delete', OLD.node_type, json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_node_id', OLD.parent_node_id, 'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id, 'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified), NULL, CURRENT_TIMESTAMP, 0);
END;

-- NodeLink triggers
CREATE TRIGGER IF NOT EXISTS trg_node_link_insert AFTER INSERT ON node_links
BEGIN
  INSERT INTO node_events (event_type, node_type, old_data, new_data, timestamp, processed)
  VALUES ('create', 'node_link', NULL, json_object('id', NEW.id, 'source_node_id', NEW.source_node_id, 'target_node_id', NEW.target_node_id, 'predicate', NEW.predicate, 'predicate_id', NEW.predicate_id, 'created_at', NEW.created_at), CURRENT_TIMESTAMP, 0);
END;

CREATE TRIGGER IF NOT EXISTS trg_node_link_update AFTER UPDATE ON node_links
BEGIN
  INSERT INTO node_events (event_type, node_type, old_data, new_data, timestamp, processed)
  VALUES ('update', 'node_link', json_object('id', OLD.id, 'source_node_id', OLD.source_node_id, 'target_node_id', OLD.target_node_id, 'predicate', OLD.predicate, 'predicate_id', OLD.predicate_id, 'created_at', OLD.created_at), json_object('id', NEW.id, 'source_node_id', NEW.source_node_id, 'target_node_id', NEW.target_node_id, 'predicate', NEW.predicate, 'predicate_id', NEW.predicate_id, 'created_at', NEW.created_at), CURRENT_TIMESTAMP, 0);
END;

CREATE TRIGGER IF NOT EXISTS trg_node_link_delete AFTER DELETE ON node_links
BEGIN
  INSERT INTO node_events (event_type, node_type, old_data, new_data, timestamp, processed)
  VALUES ('delete', 'node_link', json_object('id', OLD.id, 'source_node_id', OLD.source_node_id, 'target_node_id', OLD.target_node_id, 'predicate', OLD.predicate, 'predicate_id', OLD.predicate_id, 'created_at', OLD.created_at), NULL, CURRENT_TIMESTAMP, 0);
END;
