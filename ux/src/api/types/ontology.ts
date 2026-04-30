/**
 * Ontology Entity Type Definitions
 *
 * Type definitions for the five core ontology entities:
 * Taxonomy, ConceptScheme, OntologyClass, Relationship, PropertyDefinition
 */

// ============= Taxonomy =============
export interface Taxonomy {
  id: string;
  title: string;
  description?: string | null;
  created_at?: string | null;
  last_modified?: string | null;
  version: number;
}

export interface TaxonomyCreate {
  title: string;
  description?: string | null;
}

export interface TaxonomyUpdate {
  title?: string | null;
  description?: string | null;
}

export interface TaxonomyListParams {
  offset?: number;
  limit?: number;
  [key: string]: unknown;
}

// ============= ConceptScheme =============
export interface ConceptScheme {
  id: string;
  taxonomy_id: string;
  title: string;
  description?: string | null;
  created_at?: string | null;
  last_modified?: string | null;
  version: number;
}

export interface ConceptSchemeCreate {
  title: string;
  description?: string | null;
}

export interface ConceptSchemeUpdate {
  title?: string | null;
  description?: string | null;
}

export interface ConceptSchemeListParams {
  offset?: number;
  limit?: number;
  taxonomy_id?: string;
  [key: string]: unknown;
}

// ============= OntologyClass =============
export interface OntologyClass {
  id: string;
  concept_scheme_id: string;
  taxonomy_id: string;
  title: string;
  description?: string | null;
  parent_class_id?: string | null;
  structural_property_id?: string | null;
  external_references?: ExternalReference[];
  lexical_senses?: LexicalSense[];
  data_properties?: DataPropertyValue[];
  embedding?: number[] | null;
  created_at?: string | null;
  last_modified?: string | null;
  version: number;
  // Legacy properties for backward compatibility
  node_type?: NodeType;
}

export interface OntologyClassCreate {
  title: string;
  description?: string | null;
  parent_class_id?: string | null;
}

export interface OntologyClassUpdate {
  title?: string | null;
  description?: string | null;
}

export interface OntologyClassListParams {
  offset?: number;
  limit?: number;
  concept_scheme_id?: string;
  parent_class_id?: string;
  [key: string]: unknown;
}

// ============= ExternalReference =============
export interface ExternalReference {
  source: string;
  identifier: string;
  uri?: string | null;
  metadata?: Record<string, unknown>;
}

// ============= LexicalSense =============
export interface LexicalSense {
  label: string;
  language_code: string;
  sense_type: string;
}

// ============= DataPropertyValue =============
export interface DataPropertyValue {
  property_identifier: string;
  value: string | number | boolean | null;
  datatype?: string | null;
}

// ============= WordSense (Deprecated - for backward compatibility) =============
/** @deprecated Use LexicalSense instead */
export type WordSense = LexicalSense;

// ============= NodeType =============
export enum NodeType {
  TAXONOMY = "taxonomy",
  CONCEPT_SCHEME = "concept_scheme",
  CLASS = "class",
  INDIVIDUAL = "individual",
  PROPERTY_DEFINITION = "property_definition",
  // Deprecated aliases for backward compatibility
  DOMAIN = "domain",
  TERM = "term",
  LAYER = "layer",
}

// ============= OntologyClassLink (Deprecated) =============
/** @deprecated */
export interface OntologyClassLink {
  id: string;
  source_id: string;
  target_id: string;
  property_definition_id: string;
  created_at?: string | null;
}

export interface OntologyClassLinkCreate {
  source_id: string;
  target_id: string;
  property_definition_id: string;
}

// ============= Relationship =============
export interface Relationship {
  id: string;
  source_id: string;
  target_id: string;
  property_definition_id: string;
  created_at?: string | null;
  last_modified?: string | null;
  version?: number;
}

export interface RelationshipCreate {
  source_id: string;
  target_id: string;
  relationship_type: string;
}

export interface RelationshipUpdate {
  source_id?: string;
  target_id?: string;
  relationship_type?: string;
}

export interface RelationshipListParams {
  offset?: number;
  limit?: number;
  source_id?: string;
  target_id?: string;
  relationship_type?: string;
  [key: string]: unknown;
}

// ============= PropertyDefinition =============
export interface PropertyDefinition {
  id: string;
  identifier: string;
  title: string;
  description?: string | null;
  range?: string | null;
  created_at?: string | null;
  last_modified?: string | null;
  version: number;
}

export interface PropertyDefinitionCreate {
  title: string;
  description?: string | null;
  range?: string | null;
}

export interface PropertyDefinitionUpdate {
  title?: string | null;
  description?: string | null;
  range?: string | null;
}

export interface PropertyDefinitionListParams {
  offset?: number;
  limit?: number;
  [key: string]: unknown;
}

// ============= Generic List Response =============
export interface ListResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// ============= Deprecated Types for Backward Compatibility =============
// Note: ReferenceLink has been moved to reference.ts service for proper API alignment

/** @deprecated */
export interface OntologyClassAttribute {
  id?: string;
  name?: string;
  value?: unknown;
  key?: string;
  title?: string;
  value_type?: string;
  [key: string]: any;
}

/** @deprecated */
export type AttributeValueType = string | number | boolean | null | Key;

/** @deprecated */
export interface ResolvedAttribute {
  name?: string;
  value?: unknown;
  inherited?: boolean;
  key?: string;
  title?: string;
  value_type?: string;
  source_node_id?: string;
  [key: string]: any;
}

type Key = string | number | symbol;

/** @deprecated */
export interface FindOntologyClassResult {
  id: string;
  title: string;
  description?: string;
  node_type?: any;
  parent_node_id?: any;
  definition?: any;
  structural_predicate_id?: any;
  created_at?: any;
  version?: any;
  last_modified?: any;
}
