/**
 * DEPRECATED: Legacy Structure Node Types
 *
 * This file exists for backward compatibility with legacy UI components.
 * These types and components should be migrated to use the new ontology entity types:
 * - Taxonomy, ConceptScheme, OntologyClass, Relationship, PropertyDefinition
 *
 * Do not use these types in new code.
 */

/**
 * @deprecated Use the new ontology entity types instead
 */
export type OntologyClass = any;  

/**
 * @deprecated Use the new ontology entity types instead
 */
export enum NodeType {
  TAXONOMY = "taxonomy",
  SCHEME = "scheme",
  CLASS = "class",
  // Deprecated aliases for backward compatibility
  DOMAIN = "domain",
  TERM = "term",
  LAYER = "layer",
}

/**
 * @deprecated Use the new ontology entity types instead
 */
export type OntologyClassCreate = any;  

/**
 * @deprecated Use the new ontology entity types instead
 */
export type OntologyClassUpdate = any;  

/**
 * @deprecated Use the new ontology entity types instead
 */
export interface ChangeEvent {
  id: number;
  record_type: string;
  record_id: string;
  event_type: string;
  old_data?: Record<string, unknown> | null;
  new_data?: Record<string, unknown> | null;
  processed: boolean;
  created_at?: string | null;
  timestamp?: string | null;
}

/**
 * @deprecated Use the new ontology entity types instead
 */
export enum RecordType {
  STRUCTURE_NODE = "ontologyClass",
  STRUCTURE_NODE_LINK = "ontologyClass_link",
  PREDICATE = "predicate",
}

/**
 * @deprecated
 */
export type WordSense = any;  

/**
 * @deprecated
 */
export type OntologyClassLink = any;  

/**
 * @deprecated
 */
export type OntologyClassLinkCreate = any;  

/**
 * @deprecated
 */
export interface NodeAttribute {
  [key: string]: unknown;
}

/**
 * @deprecated
 */
export interface ReferenceLink {
  source: string;
  external_id: string;
}

/**
 * @deprecated
 */
export type OntologyClassAttribute = any;  

/**
 * @deprecated
 */
export type AttributeValueType = any;  

/**
 * @deprecated
 */
export type ResolvedAttribute = any;  

/**
 * @deprecated
 */
export type FindOntologyClassResult = any;  

/**
 * @deprecated
 */
export type ExternalPredicateOut = any;  

/**
 * @deprecated
 */
export function isOntologyClassEvent(event: ChangeEvent): boolean {
  return event.record_type === "ontologyClass";
}

/**
 * @deprecated
 */
export function isOntologyClassLinkEvent(event: ChangeEvent): boolean {
  return event.record_type === "ontologyClass_link";
}

/**
 * @deprecated
 */
export function isPredicateEvent(event: ChangeEvent): boolean {
  return event.record_type === "predicate";
}
