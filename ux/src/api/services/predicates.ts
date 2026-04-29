/**
 * DEPRECATED: Predicates Service
 *
 * @deprecated Predicates are now modeled as PropertyDefinition entities
 */

/**
 * @deprecated
 */
export type PredicateOut = any; // eslint-disable-line @typescript-eslint/no-explicit-any

/**
 * @deprecated
 */
export type PredicateCreate = any; // eslint-disable-line @typescript-eslint/no-explicit-any

/**
 * @deprecated
 */
export type PredicateUpdate = any; // eslint-disable-line @typescript-eslint/no-explicit-any

/**
 * @deprecated
 */
export class PredicatesService {
  list() {
    throw new Error("PredicatesService has been removed. Use PropertyDefinitionService instead.");
  }

  get(_id: string) {
    throw new Error("PredicatesService has been removed. Use PropertyDefinitionService instead.");
  }

  create(_data: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
    throw new Error("PredicatesService has been removed. Use PropertyDefinitionService instead.");
  }

  update(_id: string, _data: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
    throw new Error("PredicatesService has been removed. Use PropertyDefinitionService instead.");
  }

  delete(_id: string) {
    throw new Error("PredicatesService has been removed. Use PropertyDefinitionService instead.");
  }
}

export const predicatesService = new PredicatesService();
