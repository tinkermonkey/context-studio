/**
 * DEPRECATED: Structure Nodes Service
 *
 * @deprecated This service has been removed. Use the entity-specific services instead.
 */

/**
 * @deprecated
 */
export class StructureNodesService {
  list() {
    throw new Error("StructureNodesService has been removed.");
  }

  get(_id: string) {
    throw new Error("StructureNodesService has been removed.");
  }

  create(_data: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
    throw new Error("StructureNodesService has been removed.");
  }

  update(_id: string, _data: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
    throw new Error("StructureNodesService has been removed.");
  }

  delete(_id: string) {
    throw new Error("StructureNodesService has been removed.");
  }
}

export const structureNodesService = new StructureNodesService();
