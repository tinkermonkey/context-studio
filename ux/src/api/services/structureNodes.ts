/**
 * Structure Nodes Service
 *
 * Unified service for managing structure nodes (layers, domains, terms)
 * Consolidates the functionality of LayerService, DomainService, and TermService
 */

import { BaseService, ListParams, FindParams, PaginatedResponse } from "./base";
import { ENDPOINTS } from "../config";
import {
  StructureNode,
  StructureNodeCreate,
  StructureNodeUpdate,
  StructureNodeListParams,
  StructureNodeFindParams,
  FindStructureNodeResult,
  NodeType,
  VALIDATION_RULES,
} from "../types/structureNodes";

export class StructureNodeService extends BaseService {
  /**
   * List structure nodes with optional pagination and filtering
   * If no limit is specified, loads all nodes across multiple pages
   */
  async list(params?: StructureNodeListParams): Promise<StructureNode[]> {
    return this.withErrorContext(async () => {
      const url = ENDPOINTS.STRUCTURE_NODES + "/";

      // Build query parameters
      const queryParams: Record<string, unknown> = {};
      if (params?.skip !== undefined) queryParams.skip = params.skip;
      if (params?.limit !== undefined) queryParams.limit = params.limit;
      if (params?.sort) queryParams.sort = params.sort;
      if (params?.node_type) queryParams.node_type = params.node_type;
      if (params?.parent_node_id)
        queryParams.parent_node_id = params.parent_node_id;

      // If limit is explicitly set, use single page request
      if (params?.limit !== undefined) {
        return this.getPage<StructureNode>(url, queryParams);
      }

      // Otherwise, load all nodes across all pages
      return this.getAllPaginated<StructureNode>(url, queryParams);
    }, "list");
  }

  /**
   * List a specific page of structure nodes
   */
  async listPage(params?: StructureNodeListParams): Promise<StructureNode[]> {
    return this.withErrorContext(async () => {
      const url = ENDPOINTS.STRUCTURE_NODES + "/";

      const queryParams: Record<string, unknown> = {};
      if (params?.skip !== undefined) queryParams.skip = params.skip;
      if (params?.limit !== undefined) queryParams.limit = params.limit;
      if (params?.sort) queryParams.sort = params.sort;
      if (params?.node_type) queryParams.node_type = params.node_type;
      if (params?.parent_node_id)
        queryParams.parent_node_id = params.parent_node_id;

      return this.getPage<StructureNode>(url, queryParams);
    }, "listPage");
  }

  /**
   * List a specific page of structure nodes with pagination metadata
   */
  async listPageWithMetadata(
    params?: StructureNodeListParams,
  ): Promise<PaginatedResponse<StructureNode>> {
    return this.withErrorContext(async () => {
      const url = ENDPOINTS.STRUCTURE_NODES + "/";

      const queryParams: Record<string, unknown> = {};
      if (params?.skip !== undefined) queryParams.skip = params.skip;
      if (params?.limit !== undefined) queryParams.limit = params.limit;
      if (params?.sort) queryParams.sort = params.sort;
      if (params?.node_type) queryParams.node_type = params.node_type;
      if (params?.parent_node_id)
        queryParams.parent_node_id = params.parent_node_id;

      return this.getPaginatedResponse<StructureNode>(url, queryParams);
    }, "listPageWithMetadata");
  }

  /**
   * Get a specific structure node by ID
   */
  async get(id: string): Promise<StructureNode> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.getResource<StructureNode>(
        `${ENDPOINTS.STRUCTURE_NODES}/${id}`,
      );
    }, "get");
  }

  /**
   * Create a new structure node
   */
  async create(data: StructureNodeCreate): Promise<StructureNode> {
    return this.withErrorContext(async () => {
      // Validate required fields
      this.validateRequired(data.node_type, "node_type");
      this.sanitizeString(
        data.title,
        "title",
        VALIDATION_RULES.MAX_TITLE_LENGTH,
      );

      // Validate business rules
      this.validateNodeTypeConstraints(data);

      if (data.definition) {
        this.sanitizeString(
          data.definition,
          "definition",
          VALIDATION_RULES.MAX_DEFINITION_LENGTH,
        );
      }

      return this.postResource<StructureNode>(
        ENDPOINTS.STRUCTURE_NODES + "/",
        data,
      );
    }, "create");
  }

  /**
   * Update an existing structure node
   */
  async update(id: string, data: StructureNodeUpdate): Promise<StructureNode> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");

      // Validate optional fields if present
      if (data.title) {
        this.sanitizeString(
          data.title,
          "title",
          VALIDATION_RULES.MAX_TITLE_LENGTH,
        );
      }
      if (data.definition) {
        this.sanitizeString(
          data.definition,
          "definition",
          VALIDATION_RULES.MAX_DEFINITION_LENGTH,
        );
      }

      return this.putResource<StructureNode>(
        `${ENDPOINTS.STRUCTURE_NODES}/${id}`,
        data,
      );
    }, "update");
  }

  /**
   * Delete a structure node
   */
  async delete(id: string): Promise<void> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.deleteResource<void>(`${ENDPOINTS.STRUCTURE_NODES}/${id}`);
    }, "delete");
  }

  /**
   * Find structure nodes using semantic search
   */
  async find(
    params: StructureNodeFindParams,
  ): Promise<FindStructureNodeResult[]> {
    return this.withErrorContext(async () => {
      this.validateRequired(params.query, "query");
      this.sanitizeString(params.query, "query");

      return this.postResource<FindStructureNodeResult[]>(
        `${ENDPOINTS.STRUCTURE_NODES}/find`,
        params,
      );
    }, "find");
  }

  // Convenience methods for specific node types

  /**
   * List all layers
   */
  async listLayers(
    params?: Omit<StructureNodeListParams, "node_type">,
  ): Promise<StructureNode[]> {
    return this.list({ ...params, node_type: NodeType.LAYER });
  }

  /**
   * List domains, optionally filtered by parent layer
   */
  async listDomains(
    layerId?: string,
    params?: Omit<StructureNodeListParams, "node_type" | "parent_node_id">,
  ): Promise<StructureNode[]> {
    return this.list({
      ...params,
      node_type: NodeType.DOMAIN,
      parent_node_id: layerId,
    });
  }

  /**
   * List terms, optionally filtered by parent (domain or term)
   */
  async listTerms(
    parentId?: string,
    params?: Omit<StructureNodeListParams, "node_type" | "parent_node_id">,
  ): Promise<StructureNode[]> {
    return this.list({
      ...params,
      node_type: NodeType.TERM,
      parent_node_id: parentId,
    });
  }

  /**
   * Create a layer (convenience method)
   */
  async createLayer(
    data: Omit<StructureNodeCreate, "node_type" | "parent_node_id">,
  ): Promise<StructureNode> {
    return this.create({
      ...data,
      node_type: NodeType.LAYER,
      // parent_node_id is omitted for layers
    });
  }

  /**
   * Create a domain (convenience method)
   */
  async createDomain(
    layerId: string,
    data: Omit<StructureNodeCreate, "node_type" | "parent_node_id">,
  ): Promise<StructureNode> {
    return this.create({
      ...data,
      node_type: NodeType.DOMAIN,
      parent_node_id: layerId,
    });
  }

  /**
   * Create a term (convenience method)
   */
  async createTerm(
    parentId: string,
    data: Omit<StructureNodeCreate, "node_type" | "parent_node_id">,
  ): Promise<StructureNode> {
    return this.create({
      ...data,
      node_type: NodeType.TERM,
      parent_node_id: parentId,
    });
  }

  /**
   * Get nodes by parent relationship
   */
  async getChildNodes(
    parentId: string,
    nodeType?: NodeType,
  ): Promise<StructureNode[]> {
    const params: StructureNodeListParams = { parent_node_id: parentId };
    if (nodeType) {
      params.node_type = nodeType;
    }
    return this.list(params);
  }

  /**
   * Validate node type constraints
   * @private
   */
  private validateNodeTypeConstraints(data: StructureNodeCreate): void {
    switch (data.node_type) {
      case NodeType.LAYER:
        if (data.parent_node_id) {
          throw new Error("Layers cannot have parent nodes");
        }
        break;
      case NodeType.DOMAIN:
        if (!data.parent_node_id) {
          throw new Error("Domains must have a parent layer");
        }
        break;
      case NodeType.TERM:
        if (!data.parent_node_id) {
          throw new Error("Terms must have a parent domain or term");
        }
        break;
      default:
        throw new Error(`Invalid node_type: ${data.node_type}`);
    }
  }
}

// Export singleton instance
export const structureNodeService = new StructureNodeService();
