import axiosInstance from "@/api/client/axios";

/**
 * BaseService provides HTTP methods that unwrap axios responses.
 *
 * Error Handling:
 * All HTTP errors are converted to ApiError instances by the axios response interceptor
 * (in interceptors.ts). This ensures error.message always contains the FastAPI detail
 * field when available, providing meaningful domain error messages to callers.
 *
 * Callers should handle errors as:
 *   catch (error) {
 *     const message = error instanceof Error ? error.message : "Unknown error";
 *   }
 */
export abstract class BaseService {
  protected async get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
    const response = await axiosInstance.get<T>(url, { params });
    return response.data;
  }

  protected async post<T>(url: string, data?: unknown): Promise<T> {
    const response = await axiosInstance.post<T>(url, data);
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
