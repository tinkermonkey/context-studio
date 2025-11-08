/**
 * Structure Nodes Type Definitions
 *
 * Unified type definitions for the Great Normalization migration
 * Consolidates layers, domains, and terms into a single structure_nodes model
 */

// Core enums for structure node system
export enum NodeType {
  LAYER = "layer",
  DOMAIN = "domain",
  TERM = "term",
}

export enum RecordType {
  STRUCTURE_NODE = "structure_node",
  STRUCTURE_NODE_LINK = "structure_node_link",
  PREDICATE = "predicate",
}

// Main unified structure node interface
export interface StructureNode {
  id: string;
  node_type: NodeType;
  parent_node_id?: string; // Replaces layer_id, domain_id, parent_term_id
  title: string;
  definition?: string;
  structural_predicate_id?: string; // Replaces primary_predicate_id
  title_embedding?: number[];
  definition_embedding?: number[];
  created_at: string;
  version: number;
  last_modified: string;
}

// Create structure node interface
export interface StructureNodeCreate {
  node_type: NodeType;
  parent_node_id?: string; // Required for domains and terms
  title: string;
  definition?: string;
  structural_predicate_id?: string;
}

// Update structure node interface
export interface StructureNodeUpdate {
  title?: string;
  definition?: string;
  parent_node_id?: string;
  structural_predicate_id?: string;
}

// Query parameters for listing structure nodes
export interface StructureNodeListParams {
  skip?: number;
  limit?: number;
  sort?: "title" | "created_at";
  node_type?: NodeType;
  parent_node_id?: string;
  [key: string]: unknown;
}

// Search parameters for structure nodes
export interface StructureNodeFindParams {
  query: string;
  limit?: number;
  threshold?: number;
  node_type?: NodeType;
  parent_node_id?: string;
  [key: string]: unknown;
}

// New event model for change tracking
export interface ChangeEvent {
  id: number;
  event_type: "create" | "update" | "delete";
  record_type: RecordType; // Replaces node_type
  record_id?: string; // Replaces node_id
  old_data?: any;
  new_data?: any;
  timestamp: string;
  processed: boolean;
}

// Word sense from NLP analysis
export interface WordSense {
  term: string;
  sense_type: string;
  sense_id: string;
  definition: string;
  domain?: string | null;
}

// Reference link to external knowledge sources
export interface ReferenceLink {
  source: string;
  external_id: string;
}

// Update request for word senses
export interface SelectedWordSensesUpdate {
  selected_senses: WordSense[];
}

// Structure node links (replaces term relationships)
export interface StructureNodeLink {
  id: string;
  source_node_id: string; // Replaces source_term_id
  target_node_id: string; // Replaces target_term_id
  predicate: string;
  predicate_id?: string;
  created_at: string;
}

// Create structure node link interface
export interface StructureNodeLinkCreate {
  source_node_id: string;
  target_node_id: string;
  predicate: string;
  predicate_id?: string;
}

// Query parameters for listing structure node links
export interface StructureNodeLinkListParams {
  skip?: number;
  limit?: number;
  source_node_id?: string;
  target_node_id?: string;
  predicate?: string;
  [key: string]: unknown;
}

// Search result types
export interface FindStructureNodeResult extends StructureNode {
  similarity_score?: number;
  similarity_threshold?: number;
}

// Type guards for working with unified nodes
export function isLayer(node: StructureNode): boolean {
  return node.node_type === NodeType.LAYER;
}

export function isDomain(node: StructureNode): boolean {
  return node.node_type === NodeType.DOMAIN;
}

export function isTerm(node: StructureNode): boolean {
  return node.node_type === NodeType.TERM;
}

// Utility to get expected parent type
export function getExpectedParentType(nodeType: NodeType): NodeType | null {
  switch (nodeType) {
    case NodeType.LAYER:
      return null; // Layers have no parent
    case NodeType.DOMAIN:
      return NodeType.LAYER; // Domains must have layer parent
    case NodeType.TERM:
      return null; // Terms can have domain or term parent - need to check actual parent
    default:
      return null;
  }
}

// Type predicates for record types in events
export function isStructureNodeEvent(event: ChangeEvent): boolean {
  return event.record_type === RecordType.STRUCTURE_NODE;
}

export function isStructureNodeLinkEvent(event: ChangeEvent): boolean {
  return event.record_type === RecordType.STRUCTURE_NODE_LINK;
}

export function isPredicateEvent(event: ChangeEvent): boolean {
  return event.record_type === RecordType.PREDICATE;
}

export interface DomainCreate extends Omit<StructureNodeCreate, "node_type"> {
  parent_node_id: string; // Required for domains (layer_id)
}

export interface TermCreate extends Omit<StructureNodeCreate, "node_type"> {
  parent_node_id: string; // Required for terms (domain_id or parent_term_id)
}

// Validation constants
export const VALIDATION_RULES = {
  MAX_TITLE_LENGTH: 255,
  MAX_DEFINITION_LENGTH: 10000,
  MIN_TITLE_LENGTH: 1,
} as const;
