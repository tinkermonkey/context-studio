import type { AxiosInstance, AxiosError } from "axios";
import { trace, SpanStatusCode } from "@opentelemetry/api";

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
  const tracer = trace.getTracer("axios-interceptor", "1.0.0");

  // Request interceptor — inject traceparent header and create span
  instance.interceptors.request.use(
    (config) => {
      const span = tracer.startSpan(`HTTP ${config.method?.toUpperCase() || "GET"} ${config.url}`);

      // Inject traceparent header for trace propagation
      const traceId = span.spanContext().traceId;
      const spanId = span.spanContext().spanId;
      const traceparent = `00-${traceId}-${spanId}-01`;

      config.headers.set("traceparent", traceparent);

      // Store span on config for later retrieval in response interceptor
      (config as any).__span = span;

      return config;
    },
    (error) => Promise.reject(error),
  );

  // Response interceptor — normalize FastAPI error bodies into ApiError and record status
  instance.interceptors.response.use(
    (response) => {
      const span = (response.config as any)?.__span;
      if (span) {
        span.setAttributes({
          "http.method": response.config.method?.toUpperCase() || "GET",
          "http.url": response.config.url || "",
          "http.status_code": response.status,
        });
        span.end();
      }
      return response;
    },
    (error: AxiosError) => {
      const span = (error.config as any)?.__span;
      if (span) {
        const status = error.response?.status ?? 0;
        span.setAttributes({
          "http.method": error.config?.method?.toUpperCase() || "GET",
          "http.url": error.config?.url || "",
          "http.status_code": status,
          "error.type": "http_error",
        });
        span.setStatus({ code: SpanStatusCode.ERROR });
        span.end();
      }

      const status = error.response?.status ?? 0;
      const data = error.response?.data as Record<string, unknown> | undefined;
      const detail =
        typeof data?.detail === "string"
          ? data.detail
          : (error.message ?? "An unexpected error occurred");
      return Promise.reject(new ApiError(detail, status, detail));
    },
  );
}
