import axiosInstance from "@/api/client/axios";

// Errors are normalized to ApiError by the axios interceptor — error.message contains the FastAPI detail
export abstract class BaseService {
  protected async get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
    const response = await axiosInstance.get<T>(url, { params });
    return response.data;
  }

  protected async post<T>(
    url: string,
    data?: unknown,
    params?: Record<string, unknown>,
  ): Promise<T> {
    const response = await axiosInstance.post<T>(url, data, { params });
    return response.data;
  }

  protected async put<T>(url: string, data?: unknown): Promise<T> {
    const response = await axiosInstance.put<T>(url, data);
    return response.data;
  }

  protected async patch<T>(url: string, data?: unknown): Promise<T> {
    const response = await axiosInstance.patch<T>(url, data);
    return response.data;
  }

  protected async delete<T>(url: string): Promise<T> {
    const response = await axiosInstance.delete<T>(url);
    return response.data;
  }
}
