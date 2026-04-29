/**
 * DEPRECATED: Predicates Type Aliases
 *
 * This file provides backward compatibility for predicates types.
 * Predicates are now modeled as PropertyDefinition entities.
 *
 * @deprecated Use PropertyDefinition types from @/api/services/propertyDefinition instead
 */

import type {
  PropertyDefinition,
  PropertyDefinitionCreate,
  PropertyDefinitionUpdate,
} from "../types/ontology";

/**
 * @deprecated Use PropertyDefinition instead
 */
export type PredicateOut = PropertyDefinition;

/**
 * @deprecated Use PropertyDefinitionCreate instead
 */
export type PredicateCreate = PropertyDefinitionCreate;

/**
 * @deprecated Use PropertyDefinitionUpdate instead
 */
export type PredicateUpdate = PropertyDefinitionUpdate;

/**
 * @deprecated This interface represents external predicate metadata
 */
export interface ExternalPredicateOut {
  id: string;
  title: string;
  definition: string;
  source: string;
  external_id: string;
  attributes?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
