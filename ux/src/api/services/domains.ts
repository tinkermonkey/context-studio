/**
 * Domain Service
 *
 * Domain-specific wrapper around the unified StructureNodeService
 * Provides a clean domain-focused API for components and tests
 */

import { BaseService } from "./base";
import { structureNodeService } from "./structureNodes";
import {
  StructureNode,
  StructureNodeCreate,
  StructureNodeUpdate,
  StructureNodeListParams,
  StructureNodeFindParams,
  FindStructureNodeResult,
  NodeType,
} from "../types/structureNodes";

export class DomainService extends BaseService {
  /**
   * List domains, optionally filtered by parent layer
   */
  async list(
    layerId?: string,
    params?: Omit<StructureNodeListParams, "node_type" | "parent_node_id">,
  ): Promise<StructureNode[]> {
    return this.withErrorContext(async () => {
      return structureNodeService.listDomains(layerId, params);
    }, "list");
  }

  /**
   * Get a specific domain by ID
   */
  async get(id: string): Promise<StructureNode> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      const node = await structureNodeService.get(id);
      if (node.node_type !== NodeType.DOMAIN) {
        throw new Error(`Node ${id} is not a domain`);
      }
      return node;
    }, "get");
  }

  /**
   * Create a new domain
   */
  async create(
    layerId: string,
    data: Omit<StructureNodeCreate, "node_type" | "parent_node_id">,
  ): Promise<StructureNode> {
    return this.withErrorContext(async () => {
      this.validateRequired(layerId, "layerId");
      return structureNodeService.createDomain(layerId, data);
    }, "create");
  }

  /**
   * Update an existing domain
   */
  async update(id: string, data: StructureNodeUpdate): Promise<StructureNode> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");

      // Verify it's a domain before updating
      const existingNode = await structureNodeService.get(id);
      if (existingNode.node_type !== NodeType.DOMAIN) {
        throw new Error(`Node ${id} is not a domain`);
      }

      return structureNodeService.update(id, data);
    }, "update");
  }

  /**
   * Delete a domain
   */
  async delete(id: string): Promise<void> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");

      // Verify it's a domain before deleting
      const existingNode = await structureNodeService.get(id);
      if (existingNode.node_type !== NodeType.DOMAIN) {
        throw new Error(`Node ${id} is not a domain`);
      }

      return structureNodeService.delete(id);
    }, "delete");
  }

  /**
   * Find domains using semantic search
   */
  async find(
    params: Omit<StructureNodeFindParams, "node_type">,
  ): Promise<FindStructureNodeResult[]> {
    return this.withErrorContext(async () => {
      this.validateRequired(params.query, "query");
      const findParams: StructureNodeFindParams = {
        query: params.query as string,
        limit: params.limit as number | undefined,
        threshold: params.threshold as number | undefined,
        parent_node_id: params.parent_node_id as string | undefined,
        node_type: NodeType.DOMAIN,
      };
      return structureNodeService.find(findParams);
    }, "find");
  }

  /**
   * Get child terms for a domain
   */
  async getChildTerms(domainId: string): Promise<StructureNode[]> {
    return this.withErrorContext(async () => {
      this.validateRequired(domainId, "domainId");
      return structureNodeService.getChildNodes(domainId, NodeType.TERM);
    }, "getChildTerms");
  }
}

// Export singleton instance
export const domainService = new DomainService();
