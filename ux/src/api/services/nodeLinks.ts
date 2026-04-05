/**
 * Node Links Service
 *
 * Service for managing structure node links (replaces term relationships)
 * Handles connections between structure nodes with predicates
 */

import { BaseService, PaginatedResponse } from "./base";
import { ENDPOINTS } from "../config";
import {
  StructureNodeLink,
  StructureNodeLinkCreate,
  StructureNodeLinkListParams,
} from "../types/structureNodes";

export class NodeLinkService extends BaseService {
  /**
   * List structure node links with optional pagination and filtering
   * If no limit is specified, loads all links across multiple pages
   */
  async list(
    params?: StructureNodeLinkListParams,
  ): Promise<StructureNodeLink[]> {
    return this.withErrorContext(async () => {
      const url = ENDPOINTS.NODE_LINKS + "/";

      // Build query parameters
      const queryParams: Record<string, unknown> = {};
      if (params?.skip !== undefined) queryParams.skip = params.skip;
      if (params?.limit !== undefined) queryParams.limit = params.limit;
      if (params?.source_node_id)
        queryParams.source_node_id = params.source_node_id;
      if (params?.target_node_id)
        queryParams.target_node_id = params.target_node_id;
      if (params?.predicate) queryParams.predicate = params.predicate;

      // If limit is explicitly set, use single page request
      if (params?.limit !== undefined) {
        return this.getPage<StructureNodeLink>(url, queryParams);
      }

      // Otherwise, load all links across all pages
      return this.getAllPaginated<StructureNodeLink>(url, queryParams);
    }, "list");
  }

  /**
   * List a specific page of structure node links
   */
  async listPage(
    params?: StructureNodeLinkListParams,
  ): Promise<StructureNodeLink[]> {
    return this.withErrorContext(async () => {
      const url = ENDPOINTS.NODE_LINKS + "/";

      const queryParams: Record<string, unknown> = {};
      if (params?.skip !== undefined) queryParams.skip = params.skip;
      if (params?.limit !== undefined) queryParams.limit = params.limit;
      if (params?.source_node_id)
        queryParams.source_node_id = params.source_node_id;
      if (params?.target_node_id)
        queryParams.target_node_id = params.target_node_id;
      if (params?.predicate) queryParams.predicate = params.predicate;

      return this.getPage<StructureNodeLink>(url, queryParams);
    }, "listPage");
  }

  /**
   * List a specific page of structure node links with pagination metadata
   */
  async listPageWithMetadata(
    params?: StructureNodeLinkListParams,
  ): Promise<PaginatedResponse<StructureNodeLink>> {
    return this.withErrorContext(async () => {
      const url = ENDPOINTS.NODE_LINKS + "/";

      const queryParams: Record<string, unknown> = {};
      if (params?.skip !== undefined) queryParams.skip = params.skip;
      if (params?.limit !== undefined) queryParams.limit = params.limit;
      if (params?.source_node_id)
        queryParams.source_node_id = params.source_node_id;
      if (params?.target_node_id)
        queryParams.target_node_id = params.target_node_id;
      if (params?.predicate) queryParams.predicate = params.predicate;

      return this.getPaginatedResponse<StructureNodeLink>(url, queryParams);
    }, "listPageWithMetadata");
  }

  /**
   * Get a specific structure node link by ID
   */
  async get(id: string): Promise<StructureNodeLink> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.getResource<StructureNodeLink>(
        `${ENDPOINTS.NODE_LINKS}/${id}`,
      );
    }, "get");
  }

  /**
   * Create a new structure node link
   */
  async create(data: StructureNodeLinkCreate): Promise<StructureNodeLink> {
    return this.withErrorContext(async () => {
      // Validate required fields
      this.validateRequired(data.source_node_id, "source_node_id");
      this.validateRequired(data.target_node_id, "target_node_id");
      this.sanitizeString((data.predicate as unknown as string) || '', "predicate");

      // Validate that source and target are different
      if (data.source_node_id === data.target_node_id) {
        throw new Error("Source and target nodes cannot be the same");
      }

      return this.postResource<StructureNodeLink>(
        ENDPOINTS.NODE_LINKS + "/",
        data,
      );
    }, "create");
  }

  /**
   * Delete a structure node link
   */
  async delete(id: string): Promise<void> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.deleteResource<void>(`${ENDPOINTS.NODE_LINKS}/${id}`);
    }, "delete");
  }

  // Convenience methods for common query patterns

  /**
   * Get all links where the specified node is the source
   */
  async getLinksFromNode(nodeId: string): Promise<StructureNodeLink[]> {
    return this.list({ source_node_id: nodeId });
  }

  /**
   * Get all links where the specified node is the target
   */
  async getLinksToNode(nodeId: string): Promise<StructureNodeLink[]> {
    return this.list({ target_node_id: nodeId });
  }

  /**
   * Get all links for a node (as source or target)
   */
  async getNodeLinks(nodeId: string): Promise<StructureNodeLink[]> {
    return this.withErrorContext(async () => {
      // Fetch links where node is either source or target in parallel
      const [asSource, asTarget] = await Promise.all([
        this.getLinksFromNode(nodeId),
        this.getLinksToNode(nodeId),
      ]);

      // Combine and deduplicate by ID
      const allLinks = [...asSource, ...asTarget];
      const uniqueLinks = allLinks.filter(
        (link, index, self) =>
          index === self.findIndex((l) => l.id === link.id),
      );

      return uniqueLinks;
    }, "getNodeLinks");
  }

  /**
   * Get links by predicate
   */
  async getLinksByPredicate(predicate: string): Promise<StructureNodeLink[]> {
    return this.list({ predicate });
  }

  /**
   * Get links between two specific nodes
   */
  async getLinksBetweenNodes(
    sourceId: string,
    targetId: string,
  ): Promise<StructureNodeLink[]> {
    return this.withErrorContext(async () => {
      // Get direct links from source to target
      const directLinks = await this.list({
        source_node_id: sourceId,
        target_node_id: targetId,
      });

      // Get reverse links (from target to source)
      const reverseLinks = await this.list({
        source_node_id: targetId,
        target_node_id: sourceId,
      });

      return [...directLinks, ...reverseLinks];
    }, "getLinksBetweenNodes");
  }
}

// Export singleton instance
export const nodeLinkService = new NodeLinkService();
