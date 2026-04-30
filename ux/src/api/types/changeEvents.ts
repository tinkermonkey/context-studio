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
  operation: "create" | "update" | "delete";
  previous_state?: Record<string, unknown> | null;
  new_state: Record<string, unknown>;
  processed: boolean;
  timestamp: string;
  user_id?: string | null;
  change_reason?: string | null;
}

/**
 * Discriminated union types for specific change event types
 */
export interface TaxonomyEvent extends ChangeEvent {
  entity_type: RecordType.TAXONOMY;
}

export interface ConceptSchemeEvent extends ChangeEvent {
  entity_type: RecordType.CONCEPT_SCHEME;
}

export interface OntologyClassEvent extends ChangeEvent {
  entity_type: RecordType.ONTOLOGY_CLASS;
}

export interface RelationshipEvent extends ChangeEvent {
  entity_type: RecordType.RELATIONSHIP;
}

export interface PropertyDefinitionEvent extends ChangeEvent {
  entity_type: RecordType.PROPERTY_DEFINITION;
}

/**
 * Type guard to check if an event is a taxonomy event
 */
export function isTaxonomyEvent(event: ChangeEvent): event is TaxonomyEvent {
  return event.entity_type === RecordType.TAXONOMY;
}

/**
 * Type guard to check if an event is a concept scheme event
 */
export function isConceptSchemeEvent(
  event: ChangeEvent,
): event is ConceptSchemeEvent {
  return event.entity_type === RecordType.CONCEPT_SCHEME;
}

/**
 * Type guard to check if an event is an ontology class event
 */
export function isOntologyClassEvent(
  event: ChangeEvent,
): event is OntologyClassEvent {
  return event.entity_type === RecordType.ONTOLOGY_CLASS;
}

/**
 * Type guard to check if an event is a relationship event
 */
export function isRelationshipEvent(
  event: ChangeEvent,
): event is RelationshipEvent {
  return event.entity_type === RecordType.RELATIONSHIP;
}

/**
 * Type guard to check if an event is a property definition event
 */
export function isPropertyDefinitionEvent(
  event: ChangeEvent,
): event is PropertyDefinitionEvent {
  return event.entity_type === RecordType.PROPERTY_DEFINITION;
}
