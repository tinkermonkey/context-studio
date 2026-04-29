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
  skip?: number;
  limit?: number;
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
  skip?: number;
  limit?: number;
  taxonomy_id?: string;
}

// ============= OntologyClass =============
export interface OntologyClass {
  id: string;
  scheme_id: string;
  parent_class_id?: string | null;
  title: string;
  definition?: string | null;
  definition_embedding?: number[] | null;
  created_at?: string | null;
  last_modified?: string | null;
  version: number;
}

export interface OntologyClassCreate {
  title: string;
  definition?: string | null;
  parent_class_id?: string | null;
}

export interface OntologyClassUpdate {
  title?: string | null;
  definition?: string | null;
  parent_class_id?: string | null;
}

export interface OntologyClassListParams {
  skip?: number;
  limit?: number;
  scheme_id?: string;
  parent_class_id?: string;
}

// ============= Relationship =============
export interface Relationship {
  id: string;
  source_class_id: string;
  target_class_id: string;
  property_id: string;
  created_at?: string | null;
  last_modified?: string | null;
  version: number;
}

export interface RelationshipCreate {
  source_class_id: string;
  target_class_id: string;
  property_id: string;
}

export interface RelationshipUpdate {
  source_class_id?: string;
  target_class_id?: string;
  property_id?: string;
}

export interface RelationshipListParams {
  skip?: number;
  limit?: number;
  source_class_id?: string;
  target_class_id?: string;
  property_id?: string;
}

// ============= PropertyDefinition =============
export interface PropertyDefinition {
  id: string;
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
  skip?: number;
  limit?: number;
}

// ============= Generic List Response =============
export interface ListResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
