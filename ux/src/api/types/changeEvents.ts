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
}

/**
 * A change event representing a modification to an entity
 */
export interface ChangeEvent {
  id: string;
  entity_type: string;
  entity_id: string;
  operation: string;
  previous_state?: Record<string, unknown> | null;
  new_state?: Record<string, unknown> | null;
  processed: boolean;
  timestamp: string;
  user_id?: string | null;
}

/**
 * Type guard to check if an event is a taxonomy event
 */
export function isTaxonomyEvent(event: ChangeEvent): boolean {
  return event.entity_type === RecordType.TAXONOMY;
}

/**
 * Type guard to check if an event is a concept scheme event
 */
export function isConceptSchemeEvent(event: ChangeEvent): boolean {
  return event.entity_type === RecordType.CONCEPT_SCHEME;
}

/**
 * Type guard to check if an event is an ontology class event
 */
export function isOntologyClassEvent(event: ChangeEvent): boolean {
  return event.entity_type === RecordType.ONTOLOGY_CLASS;
}

/**
 * Type guard to check if an event is a relationship event
 */
export function isRelationshipEvent(event: ChangeEvent): boolean {
  return event.entity_type === RecordType.RELATIONSHIP;
}

/**
 * Type guard to check if an event is a property definition event
 */
export function isPropertyDefinitionEvent(event: ChangeEvent): boolean {
  return event.entity_type === RecordType.PROPERTY_DEFINITION;
}
