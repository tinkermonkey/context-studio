import axiosInstance from "@/api/client/axios";
import type { AxiosRequestConfig } from "axios";

// Errors are normalized to ApiError by the axios interceptor — error.message contains the FastAPI detail
export abstract class BaseService {
  protected async get<T>(url: string, params?: Record<string, unknown>, config?: AxiosRequestConfig): Promise<T> {
    const response = await axiosInstance.get<T>(url, { params, ...config });
    return response.data;
  }

  protected async post<T>(
    url: string,
    data?: unknown,
    params?: Record<string, unknown>,
    config?: AxiosRequestConfig,
  ): Promise<T> {
    const response = await axiosInstance.post<T>(url, data, { params, ...config });
    return response.data;
  }

  protected async put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    const response = await axiosInstance.put<T>(url, data, config);
    return response.data;
  }

  protected async patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    const response = await axiosInstance.patch<T>(url, data, config);
    return response.data;
  }

  protected async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await axiosInstance.delete<T>(url, config);
    return response.data;
  }
}
