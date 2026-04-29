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
export type StructureNode = any; // eslint-disable-line @typescript-eslint/no-explicit-any

/**
 * @deprecated Use the new ontology entity types instead
 */
export enum NodeType {
  LAYER = "LAYER",
  DOMAIN = "DOMAIN",
  TERM = "TERM",
}

/**
 * @deprecated Use the new ontology entity types instead
 */
export type StructureNodeCreate = any; // eslint-disable-line @typescript-eslint/no-explicit-any

/**
 * @deprecated Use the new ontology entity types instead
 */
export type StructureNodeUpdate = any; // eslint-disable-line @typescript-eslint/no-explicit-any

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
  STRUCTURE_NODE = "structure_node",
  STRUCTURE_NODE_LINK = "structure_node_link",
  PREDICATE = "predicate",
}

/**
 * @deprecated
 */
export type WordSense = any; // eslint-disable-line @typescript-eslint/no-explicit-any

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
  [key: string]: unknown;
}

/**
 * @deprecated
 */
export function isStructureNodeEvent(event: ChangeEvent): boolean {
  return event.record_type === "structure_node";
}

/**
 * @deprecated
 */
export function isStructureNodeLinkEvent(event: ChangeEvent): boolean {
  return event.record_type === "structure_node_link";
}

/**
 * @deprecated
 */
export function isPredicateEvent(event: ChangeEvent): boolean {
  return event.record_type === "predicate";
}
