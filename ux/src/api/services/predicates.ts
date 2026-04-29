/**
 * DEPRECATED: Predicates Service
 *
 * @deprecated Predicates are now modeled as PropertyDefinition entities
 */

/**
 * @deprecated
 */
export type PredicateOut = any;

/**
 * @deprecated
 */
export type PredicateCreate = any;

/**
 * @deprecated
 */
export type PredicateUpdate = any;

/**
 * @deprecated
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

/**
 * @deprecated
 */
export class PredicatesService {
  list() {
    throw new Error(
      "PredicatesService has been removed. Use PropertyDefinitionService instead.",
    );
  }

  get(_id: string) {
    throw new Error(
      "PredicatesService has been removed. Use PropertyDefinitionService instead.",
    );
  }

  create(_data: any) {
    throw new Error(
      "PredicatesService has been removed. Use PropertyDefinitionService instead.",
    );
  }

  update(_id: string, _data: any) {
    throw new Error(
      "PredicatesService has been removed. Use PropertyDefinitionService instead.",
    );
  }

  delete(_id: string) {
    throw new Error(
      "PredicatesService has been removed. Use PropertyDefinitionService instead.",
    );
  }
}

export const predicatesService = new PredicatesService();
