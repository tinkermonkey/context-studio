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

export abstract class BaseService {
  protected client: AxiosInstance;

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
}
