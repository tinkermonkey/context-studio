/**
 * Individual Service
 *
 * Service for managing individual entities
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type { components } from "../client/types";

type IndividualResponse = components["schemas"]["IndividualResponse"];
type IndividualCreateRequest = components["schemas"]["IndividualCreateRequest"];
type IndividualUpdateRequest = components["schemas"]["IndividualUpdateRequest"];
type DataPropertyValueResponse = components["schemas"]["DataPropertyValueResponse"];

export interface IndividualListParams {
  offset?: number;
  limit?: number;
  class_id?: string;
}

export class IndividualService extends BaseService {
  /**
   * List all individuals
   */
  async list(params?: IndividualListParams): Promise<IndividualResponse[]> {
    return this.withErrorContext(async () => {
      const queryParams: Record<string, unknown> = {};
      if (params?.offset !== undefined) queryParams.offset = params.offset;
      if (params?.limit !== undefined) queryParams.limit = params.limit;
      if (params?.class_id) queryParams.class_id = params.class_id;

      // If no limit specified, load all
      if (params?.limit === undefined) {
        return this.getAllPaginated<IndividualResponse>(
          ENDPOINTS.INDIVIDUALS,
          queryParams,
        );
      }

      return this.getPage<IndividualResponse>(ENDPOINTS.INDIVIDUALS, queryParams);
    }, "list");
  }

  /**
   * Get a specific individual by ID
   */
  async get(id: string): Promise<IndividualResponse> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.getResource<IndividualResponse>(
        `${ENDPOINTS.INDIVIDUALS}/${id}`,
      );
    }, "get");
  }

  /**
   * Create a new individual
   */
  async create(data: IndividualCreateRequest): Promise<IndividualResponse> {
    return this.withErrorContext(async () => {
      this.validateRequired(data.title, "title");
      this.sanitizeString(data.title, "title", 255);

      if (data.description) {
        this.sanitizeString(data.description, "description", 10000);
      }

      this.validateRequired(data.class_ids, "class_ids");

      return this.postResource<IndividualResponse>(
        ENDPOINTS.INDIVIDUALS,
        data,
      );
    }, "create");
  }

  /**
   * Update an existing individual
   */
  async update(
    id: string,
    data: IndividualUpdateRequest,
  ): Promise<IndividualResponse> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");

      if (data.title) {
        this.sanitizeString(data.title, "title", 255);
      }

      if (data.description) {
        this.sanitizeString(data.description, "description", 10000);
      }

      return this.putResource<IndividualResponse>(
        `${ENDPOINTS.INDIVIDUALS}/${id}`,
        data,
      );
    }, "update");
  }

  /**
   * Delete an individual
   */
  async delete(id: string): Promise<void> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.deleteResource<void>(`${ENDPOINTS.INDIVIDUALS}/${id}`);
    }, "delete");
  }

  /**
   * Add a class to an individual's class membership
   */
  async addClass(id: string, classId: string): Promise<IndividualResponse> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      this.validateRequired(classId, "classId");
      return this.postResource<IndividualResponse>(
        `${ENDPOINTS.INDIVIDUALS}/${id}/classes`,
        { class_id: classId },
      );
    }, "addClass");
  }

  /**
   * Remove a class from an individual's class membership
   */
  async removeClass(id: string, classId: string): Promise<void> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      this.validateRequired(classId, "classId");
      return this.deleteResource<void>(
        `${ENDPOINTS.INDIVIDUALS}/${id}/classes/${classId}`,
      );
    }, "removeClass");
  }

  /**
   * Set the order of classes for an individual
   */
  async setClassOrder(
    id: string,
    classIds: string[],
  ): Promise<IndividualResponse> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      this.validateRequired(classIds, "classIds");
      return this.putResource<IndividualResponse>(
        `${ENDPOINTS.INDIVIDUALS}/${id}/classes`,
        { class_ids: classIds },
      );
    }, "setClassOrder");
  }

  /**
   * Get inherited properties for an individual
   */
  async getInheritedProperties(
    id: string,
  ): Promise<DataPropertyValueResponse[]> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.getPage<DataPropertyValueResponse>(
        `${ENDPOINTS.INDIVIDUALS}/${id}/inherited-properties`,
      );
    }, "getInheritedProperties");
  }
}

export const individualService = new IndividualService();
