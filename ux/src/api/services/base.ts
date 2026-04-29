/**
 * Base Service Class
 *
 * Abstract base class for all API services
 */

import { AxiosInstance, AxiosRequestConfig } from "axios";
import { apiClient } from "../client/axios";
import type { ListResponse } from "../types/ontology";
import { apiLogger } from "../utils/logger";

export interface ListParams {
  offset?: number;
  limit?: number;
  sort?: string;
  [key: string]: unknown;
}

export interface FindParams {
  query?: string;
  limit?: number;
  threshold?: number;
  [key: string]: unknown;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface PaginationConfig {
  defaultPageSize: number;
  maxPageSize: number;
}

export abstract class BaseService {
  protected client: AxiosInstance;
  protected paginationConfig: PaginationConfig = {
    defaultPageSize: 50,
    maxPageSize: 100,
  };

  constructor(client: AxiosInstance = apiClient) {
    this.client = client;
  }

  protected async request<T>(config: AxiosRequestConfig): Promise<T> {
    try {
      const response = await this.client.request<T>(config);
      return response.data;
    } catch (error) {
      // Don't add context here - withErrorContext() will handle it
      // This prevents duplicate error message decoration
      throw error;
    }
  }

  protected async getResource<T>(
    url: string,
    params?: Record<string, unknown>,
  ): Promise<T> {
    return this.request<T>({
      method: "GET",
      url,
      params,
    });
  }

  protected async postResource<T>(
    url: string,
    data?: unknown,
    config?: { params?: Record<string, unknown> },
  ): Promise<T> {
    return this.request<T>({
      method: "POST",
      url,
      data,
      params: config?.params,
    });
  }

  protected async putResource<T>(
    url: string,
    data?: unknown,
    config?: { params?: Record<string, unknown> },
  ): Promise<T> {
    return this.request<T>({
      method: "PUT",
      url,
      data,
      params: config?.params,
    });
  }

  protected async deleteResource<T>(
    url: string,
    config?: { params?: Record<string, unknown> },
  ): Promise<T> {
    return this.request<T>({
      method: "DELETE",
      url,
      params: config?.params,
    });
  }

  /**
   * Fetch all pages of data by making multiple API calls
   * Handles both ListResponse (items/offset) and PaginatedResponse (data/skip) formats
   * @param url The endpoint URL
   * @param params Base parameters for the request
   * @returns Array of all items across all pages
   */
  protected async getAllPaginated<T>(
    url: string,
    params?: Record<string, unknown>,
  ): Promise<T[]> {
    const allItems: T[] = [];
    let offset = 0;
    const limit = this.paginationConfig.maxPageSize;

    while (true) {
      const pageParams = {
        ...params,
        offset,
        limit,
      };

      // Try to fetch as ListResponse format first (new API)
      const response = await this.getResource<
        ListResponse<T> | PaginatedResponse<T>
      >(url, pageParams);

      // Handle both response formats
      const items = this.extractItems(response);
      const total = response.total;

      if (!items || items.length === 0) {
        break;
      }

      allItems.push(...items);

      if (items.length < limit || allItems.length >= total) {
        break;
      }

      offset += limit;
    }

    return allItems;
  }

  /**
   * Get a single page of data
   * Handles both ListResponse (items/offset) and PaginatedResponse (data/skip) formats
   * @param url The endpoint URL
   * @param params Parameters including pagination options
   * @returns Single page of items
   */
  protected async getPage<T>(
    url: string,
    params?: Record<string, unknown>,
  ): Promise<T[]> {
    const response = await this.getResource<
      ListResponse<T> | PaginatedResponse<T>
    >(url, params);
    return this.extractItems(response);
  }

  /**
   * Get a paginated response with metadata
   * @param url The endpoint URL
   * @param params Parameters including pagination options
   * @returns Paginated response with data and metadata
   */
  protected async getPaginatedResponse<T>(
    url: string,
    params?: Record<string, unknown>,
  ): Promise<PaginatedResponse<T>> {
    return this.getResource<PaginatedResponse<T>>(url, params);
  }

  /**
   * Extract items from either ListResponse or PaginatedResponse format
   * @private
   */
  private extractItems<T>(
    response: ListResponse<T> | PaginatedResponse<T>,
  ): T[] {
    // Check if it's ListResponse format (has 'items' property)
    if ("items" in response && Array.isArray(response.items)) {
      return response.items;
    }
    // Otherwise treat as PaginatedResponse format (has 'data' property)
    if ("data" in response && Array.isArray(response.data)) {
      return response.data;
    }
    // Throw error when response format doesn't match either expected format
    // This prevents silent failures where users see empty tables with no indication of error
    const error = new Error(
      "Response format did not match ListResponse or PaginatedResponse",
    );
    apiLogger.error("Invalid response format", { response });
    throw error;
  }

  /**
   * Enhanced error handling wrapper for service methods
   */
  protected async withErrorContext<T>(
    operation: () => Promise<T>,
    context: string,
  ): Promise<T> {
    try {
      return await operation();
    } catch (error) {
      // Add service and operation context to errors
      if (error instanceof Error) {
        const serviceName = this.constructor.name.replace("Service", "");
        error.message = `${serviceName} ${context}: ${error.message}`;
      }
      throw error;
    }
  }

  /**
   * Validate required parameters
   */
  protected validateRequired<T>(value: T, paramName: string): T {
    if (value === null || value === undefined || value === "") {
      throw new Error(`${paramName} is required`);
    }
    return value;
  }

  /**
   * Validate and sanitize string parameters
   */
  protected sanitizeString(
    value: string,
    paramName: string,
    maxLength?: number,
  ): string {
    const sanitized = value?.trim();
    if (!sanitized) {
      throw new Error(`${paramName} cannot be empty`);
    }
    if (maxLength && sanitized.length > maxLength) {
      throw new Error(`${paramName} cannot exceed ${maxLength} characters`);
    }
    return sanitized;
  }
}
