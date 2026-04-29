/**
 * Change Events Type Definitions
 *
 * Types for the change tracking system that monitors modifications to entities
 */

/**
 * Record types that can be tracked in change events
 */
export enum RecordType {
  TAXONOMY = "taxonomy",
  CONCEPT_SCHEME = "concept_scheme",
  ONTOLOGY_CLASS = "ontology_class",
  RELATIONSHIP = "relationship",
  PROPERTY_DEFINITION = "property_definition",
  // Legacy types for compatibility with existing change events
  STRUCTURE_NODE = "structure_node",
  STRUCTURE_NODE_LINK = "structure_node_link",
  PREDICATE = "predicate",
}

/**
 * Node types in the taxonomy (legacy, for backward compatibility with change events)
 */
export enum NodeType {
  LAYER = "LAYER",
  DOMAIN = "DOMAIN",
  TERM = "TERM",
}

/**
 * A change event representing a modification to an entity
 */
export interface ChangeEvent {
  id: number;
  record_type: RecordType;
  record_id: string;
  event_type: string;
  old_data?: Record<string, unknown> | null;
  new_data?: Record<string, unknown> | null;
  processed: boolean;
  created_at?: string | null;
  timestamp?: string | null;
}

/**
 * Type guard to check if an event is a structure node event
 */
export function isStructureNodeEvent(event: ChangeEvent): boolean {
  return event.record_type === RecordType.STRUCTURE_NODE;
}

/**
 * Type guard to check if an event is a structure node link event
 */
export function isStructureNodeLinkEvent(event: ChangeEvent): boolean {
  return event.record_type === RecordType.STRUCTURE_NODE_LINK;
}

/**
 * Type guard to check if an event is a predicate event
 */
export function isPredicateEvent(event: ChangeEvent): boolean {
  return event.record_type === RecordType.PREDICATE;
}
