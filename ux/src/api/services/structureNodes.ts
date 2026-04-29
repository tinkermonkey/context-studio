/**
 * DEPRECATED: Structure Nodes Service
 *
 * @deprecated This service has been removed. Use the entity-specific services instead.
 */

/**
 * @deprecated
 */
export class OntologyClasssService {
  list() {
    throw new Error("OntologyClasssService has been removed.");
  }

  get(_id: string) {
    throw new Error("OntologyClasssService has been removed.");
  }

  create(_data: any) {  
    throw new Error("OntologyClasssService has been removed.");
  }

  update(_id: string, _data: any) {  
    throw new Error("OntologyClasssService has been removed.");
  }

  delete(_id: string) {
    throw new Error("OntologyClasssService has been removed.");
  }
}

export const ontologyClasssService = new OntologyClasssService();

// Export with singular name for backward compatibility
export const ontologyClassService = ontologyClasssService;
