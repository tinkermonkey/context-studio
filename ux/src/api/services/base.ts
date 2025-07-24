/**
 * Base Service Class
 * 
 * Abstract base class for all API services
 */

import { AxiosInstance, AxiosRequestConfig } from 'axios';
import { apiClient } from '../client/axios';

export interface ListParams {
  skip?: number;
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
    const response = await this.client.request<T>(config);
    return response.data;
  }

  protected async getResource<T>(url: string, params?: Record<string, unknown>): Promise<T> {
    return this.request<T>({
      method: 'GET',
      url,
      params,
    });
  }

  protected async postResource<T>(url: string, data?: unknown, params?: Record<string, unknown>): Promise<T> {
    return this.request<T>({
      method: 'POST',
      url,
      data,
      params,
    });
  }

  protected async putResource<T>(url: string, data?: unknown, params?: Record<string, unknown>): Promise<T> {
    return this.request<T>({
      method: 'PUT',
      url,
      data,
      params,
    });
  }

  protected async deleteResource<T>(url: string, params?: Record<string, unknown>): Promise<T> {
    return this.request<T>({
      method: 'DELETE',
      url,
      params,
    });
  }

  /**
   * Fetch all pages of data by making multiple API calls
   * @param url The endpoint URL
   * @param params Base parameters for the request
   * @returns Array of all items across all pages
   */
  protected async getAllPaginated<T>(url: string, params?: Record<string, unknown>): Promise<T[]> {
    const allItems: T[] = [];
    let skip = 0;
    const limit = this.paginationConfig.maxPageSize; // Use max page size for efficiency
    
    while (true) {
      const pageParams = {
        ...params,
        skip,
        limit,
      };
      
      const response = await this.getResource<PaginatedResponse<T>>(url, pageParams);
      
      // If we got no items, we've reached the end
      if (!response.data || response.data.length === 0) {
        break;
      }
      
      allItems.push(...response.data);
      
      // If we got fewer items than the limit, or if we've reached the total, we've reached the end
      if (response.data.length < limit || allItems.length >= response.total) {
        break;
      }
      
      skip += limit;
    }
    
    return allItems;
  }

  /**
   * Get a single page of data
   * @param url The endpoint URL
   * @param params Parameters including pagination options
   * @returns Single page of items
   */
  protected async getPage<T>(url: string, params?: Record<string, unknown>): Promise<T[]> {
    const response = await this.getResource<PaginatedResponse<T>>(url, params);
    return response.data;
  }

  /**
   * Get a paginated response with metadata
   * @param url The endpoint URL
   * @param params Parameters including pagination options
   * @returns Paginated response with data and metadata
   */
  protected async getPaginatedResponse<T>(url: string, params?: Record<string, unknown>): Promise<PaginatedResponse<T>> {
    return this.getResource<PaginatedResponse<T>>(url, params);
  }
}
