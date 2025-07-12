-- SQLite triggers for graph_events table

-- Layer triggers
CREATE TRIGGER IF NOT EXISTS trg_layer_insert AFTER INSERT ON layers
BEGIN
  INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
  VALUES ('create', 'layer', NULL, json_object('id', NEW.id, 'title', NEW.title, 'definition', NEW.definition, 'primary_predicate', NEW.primary_predicate, 'created_at', NEW.created_at), CURRENT_TIMESTAMP, 0);
END;

CREATE TRIGGER IF NOT EXISTS trg_layer_update AFTER UPDATE ON layers
BEGIN
  INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
  VALUES ('update', 'layer', json_object('id', OLD.id, 'title', OLD.title, 'definition', OLD.definition, 'primary_predicate', OLD.primary_predicate, 'created_at', OLD.created_at), json_object('id', NEW.id, 'title', NEW.title, 'definition', NEW.definition, 'primary_predicate', NEW.primary_predicate, 'created_at', NEW.created_at), CURRENT_TIMESTAMP, 0);
END;

CREATE TRIGGER IF NOT EXISTS trg_layer_delete AFTER DELETE ON layers
BEGIN
  INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
  VALUES ('delete', 'layer', json_object('id', OLD.id, 'title', OLD.title, 'definition', OLD.definition, 'primary_predicate', OLD.primary_predicate, 'created_at', OLD.created_at), NULL, CURRENT_TIMESTAMP, 0);
END;

-- Domain triggers
CREATE TRIGGER IF NOT EXISTS trg_domain_insert AFTER INSERT ON domains
BEGIN
  INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
  VALUES ('create', 'domain', NULL, json_object('id', NEW.id, 'title', NEW.title, 'definition', NEW.definition, 'layer_id', NEW.layer_id, 'created_at', NEW.created_at), CURRENT_TIMESTAMP, 0);
END;

CREATE TRIGGER IF NOT EXISTS trg_domain_update AFTER UPDATE ON domains
BEGIN
  INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
  VALUES ('update', 'domain', json_object('id', OLD.id, 'title', OLD.title, 'definition', OLD.definition, 'layer_id', OLD.layer_id, 'created_at', OLD.created_at), json_object('id', NEW.id, 'title', NEW.title, 'definition', NEW.definition, 'layer_id', NEW.layer_id, 'created_at', NEW.created_at), CURRENT_TIMESTAMP, 0);
END;

CREATE TRIGGER IF NOT EXISTS trg_domain_delete AFTER DELETE ON domains
BEGIN
  INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
  VALUES ('delete', 'domain', json_object('id', OLD.id, 'title', OLD.title, 'definition', OLD.definition, 'layer_id', OLD.layer_id, 'created_at', OLD.created_at), NULL, CURRENT_TIMESTAMP, 0);
END;

-- Term triggers
CREATE TRIGGER IF NOT EXISTS trg_term_insert AFTER INSERT ON terms
BEGIN
  INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
  VALUES ('create', 'term', NULL, json_object('id', NEW.id, 'title', NEW.title, 'definition', NEW.definition, 'domain_id', NEW.domain_id, 'layer_id', NEW.layer_id, 'parent_term_id', NEW.parent_term_id, 'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified), CURRENT_TIMESTAMP, 0);
END;

CREATE TRIGGER IF NOT EXISTS trg_term_update AFTER UPDATE ON terms
BEGIN
  INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
  VALUES ('update', 'term', json_object('id', OLD.id, 'title', OLD.title, 'definition', OLD.definition, 'domain_id', OLD.domain_id, 'layer_id', OLD.layer_id, 'parent_term_id', OLD.parent_term_id, 'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified), json_object('id', NEW.id, 'title', NEW.title, 'definition', NEW.definition, 'domain_id', NEW.domain_id, 'layer_id', NEW.layer_id, 'parent_term_id', NEW.parent_term_id, 'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified), CURRENT_TIMESTAMP, 0);
END;

CREATE TRIGGER IF NOT EXISTS trg_term_delete AFTER DELETE ON terms
BEGIN
  INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
  VALUES ('delete', 'term', json_object('id', OLD.id, 'title', OLD.title, 'definition', OLD.definition, 'domain_id', OLD.domain_id, 'layer_id', OLD.layer_id, 'parent_term_id', OLD.parent_term_id, 'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified), NULL, CURRENT_TIMESTAMP, 0);
END;

-- TermRelationship triggers
CREATE TRIGGER IF NOT EXISTS trg_termrel_insert AFTER INSERT ON term_relationships
BEGIN
  INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
  VALUES ('create', 'term_relationship', NULL, json_object('id', NEW.id, 'source_term_id', NEW.source_term_id, 'target_term_id', NEW.target_term_id, 'predicate', NEW.predicate, 'created_at', NEW.created_at), CURRENT_TIMESTAMP, 0);
END;

CREATE TRIGGER IF NOT EXISTS trg_termrel_update AFTER UPDATE ON term_relationships
BEGIN
  INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
  VALUES ('update', 'term_relationship', json_object('id', OLD.id, 'source_term_id', OLD.source_term_id, 'target_term_id', OLD.target_term_id, 'predicate', OLD.predicate, 'created_at', OLD.created_at), json_object('id', NEW.id, 'source_term_id', NEW.source_term_id, 'target_term_id', NEW.target_term_id, 'predicate', NEW.predicate, 'created_at', NEW.created_at), CURRENT_TIMESTAMP, 0);
END;

CREATE TRIGGER IF NOT EXISTS trg_termrel_delete AFTER DELETE ON term_relationships
BEGIN
  INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
  VALUES ('delete', 'term_relationship', json_object('id', OLD.id, 'source_term_id', OLD.source_term_id, 'target_term_id', OLD.target_term_id, 'predicate', OLD.predicate, 'created_at', OLD.created_at), NULL, CURRENT_TIMESTAMP, 0);
END;
