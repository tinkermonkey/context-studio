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
    const response = await this.client.request<T>(config);
    return response.data;
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
   * Handles ListResponse (items/offset) format
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
    const maxIterations = 1000; // Prevent infinite loops if server returns invalid data
    let iterations = 0;
    let total = 0;

    while (iterations < maxIterations) {
      iterations++;
      const pageParams = {
        ...params,
        offset,
        limit,
      };

      // Fetch as ListResponse format (API response format)
      const response = await this.getResource<ListResponse<T>>(url, pageParams);

      // Extract items from response
      const items = this.extractItems(response);
      total = response.total;

      if (!items || items.length === 0) {
        break;
      }

      allItems.push(...items);

      if (items.length < limit || allItems.length >= total) {
        break;
      }

      offset += limit;
    }

    if (iterations >= maxIterations && allItems.length < total) {
      const error = new Error(
        "getAllPaginated exceeded maximum iterations. The server may be returning invalid pagination data.",
      );
      apiLogger.error("getAllPaginated max iterations reached", {
        url,
        params,
      });
      throw error;
    }

    return allItems;
  }

  /**
   * Get a single page of data
   * @param url The endpoint URL
   * @param params Parameters including pagination options
   * @returns Single page of items
   */
  protected async getPage<T>(
    url: string,
    params?: Record<string, unknown>,
  ): Promise<T[]> {
    const response = await this.getResource<ListResponse<T>>(url, params);
    return this.extractItems(response);
  }

  /**
   * Extract items from ListResponse format
   */
  protected extractItems<T>(response: ListResponse<T>): T[] {
    // Check if it's ListResponse format (has 'items' property)
    if ("items" in response && Array.isArray(response.items)) {
      return response.items;
    }
    // Throw error when response format doesn't match expected format
    // This prevents silent failures where users see empty tables with no indication of error
    const error = new Error("Response format did not match ListResponse");
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
