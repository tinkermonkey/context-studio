/**
 * Change Events Type Definitions
 *
 * Types for the change tracking system that monitors modifications to entities
 */

export { NodeType } from "./ontology";

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
  STRUCTURE_NODE = "ontologyClass",
  STRUCTURE_NODE_LINK = "ontologyClass_link",
  PREDICATE = "predicate",
}

/**
 * A change event representing a modification to an entity
 */
export interface ChangeEvent {
  id: string;
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
export function isOntologyClassEvent(event: ChangeEvent): boolean {
  return event.record_type === RecordType.STRUCTURE_NODE;
}

/**
 * Type guard to check if an event is a structure node link event
 */
export function isOntologyClassLinkEvent(event: ChangeEvent): boolean {
  return event.record_type === RecordType.STRUCTURE_NODE_LINK;
}

/**
 * Type guard to check if an event is a predicate event
 */
export function isPredicateEvent(event: ChangeEvent): boolean {
  return event.record_type === RecordType.PREDICATE;
}
