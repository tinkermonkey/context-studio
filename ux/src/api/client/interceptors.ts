import type { AxiosInstance, AxiosError } from "axios";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(message: string, status: number, detail: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function applyInterceptors(instance: AxiosInstance): void {
  // Request interceptor — placeholder for future auth token injection
  instance.interceptors.request.use(
    (config) => config,
    (error) => Promise.reject(error)
  );

  // Response interceptor — normalize FastAPI error bodies into ApiError
  instance.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
      const status = error.response?.status ?? 0;
      const data = error.response?.data as Record<string, unknown> | undefined;
      const detail =
        typeof data?.detail === "string"
          ? data.detail
          : error.message ?? "An unexpected error occurred";
      return Promise.reject(new ApiError(detail, status, detail));
    }
  );
}
