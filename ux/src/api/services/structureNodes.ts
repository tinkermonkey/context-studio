/**
 * DEPRECATED: Structure Nodes Service
 *
 * @deprecated This service has been removed. Use the entity-specific services instead.
 */

/**
 * @deprecated
 */
export class OntologyClassService {
  list() {
    throw new Error("OntologyClassService has been removed.");
  }

  get(_id: string) {
    throw new Error("OntologyClassService has been removed.");
  }

  create(_data: any) {
    throw new Error("OntologyClassService has been removed.");
  }

  update(_id: string, _data: any) {
    throw new Error("OntologyClassService has been removed.");
  }

  delete(_id: string) {
    throw new Error("OntologyClassService has been removed.");
  }
}

export const ontologyClassService = new OntologyClassService();
