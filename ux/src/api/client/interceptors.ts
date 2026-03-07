/**
 * Axios Interceptors
 *
 * Request and response interceptors for the API client
 */

import { InternalAxiosRequestConfig, AxiosResponse, AxiosError } from "axios";
import { apiLogger } from "../utils/logger";
import {
  ApiError,
  ValidationError,
  NotFoundError,
  ConflictError,
  BadRequestError,
  UnauthorizedError,
  ForbiddenError,
  TooManyRequestsError,
  InternalServerError,
  ServiceUnavailableError,
  NetworkError,
} from "../errors/ApiError";
import type { components } from "./types";

type HTTPValidationError = components["schemas"]["HTTPValidationError"];

export const requestInterceptor = (config: InternalAxiosRequestConfig) => {
  // Log outgoing requests
  apiLogger.request(config.method || "GET", config.url || "", config.data);
  // In test environment, print a compact debug line to help MSW handler matching
  // NOTE: removed test-only console output to keep test logs clean.

  // Add any auth headers here if needed
  // config.headers.Authorization = `Bearer ${getAuthToken()}`;

  return config;
};

export const responseInterceptor = (response: AxiosResponse) => {
  // Log successful responses
  apiLogger.response(
    response.config.method || "GET",
    response.config.url || "",
    response.status,
    response.data,
  );

  return response;
};

export const errorInterceptor = (error: AxiosError) => {
  const { response, request, config } = error;
  const endpoint = config?.url;
  const method = config?.method?.toUpperCase();

  // Log the error
  apiLogger.requestError(method || "GET", endpoint || "", error);

  // Handle different error scenarios
  if (response) {
    // Server responded with error status
    const { status, data } = response;

    switch (status) {
      case 400:
        return Promise.reject(
          new BadRequestError(
            extractErrorMessage(data, "Bad Request"),
            data,
            endpoint,
            method,
          ),
        );

      case 401:
        return Promise.reject(
          new UnauthorizedError(
            extractErrorMessage(data, "Unauthorized"),
            data,
            endpoint,
            method,
          ),
        );

      case 403:
        return Promise.reject(
          new ForbiddenError(
            extractErrorMessage(data, "Forbidden"),
            data,
            endpoint,
            method,
          ),
        );

      case 404:
        return Promise.reject(
          new NotFoundError("Resource", undefined, data, endpoint, method),
        );

      case 409:
        return Promise.reject(
          new ConflictError(
            extractErrorMessage(data, "Resource conflict"),
            data,
            endpoint,
            method,
          ),
        );

      case 422:
        // Handle FastAPI validation errors
        if (isValidationErrorResponse(data)) {
          return Promise.reject(
            ValidationError.fromValidationResponse(data, endpoint, method),
          );
        }
        return Promise.reject(
          new ValidationError("Validation failed", {}, data, endpoint, method),
        );

      case 429:
        return Promise.reject(
          new TooManyRequestsError(
            extractErrorMessage(data, "Too many requests"),
            data,
            endpoint,
            method,
          ),
        );

      case 500:
        return Promise.reject(
          new InternalServerError(
            extractErrorMessage(data, "Internal Server Error"),
            data,
            endpoint,
            method,
          ),
        );

      case 503:
        return Promise.reject(
          new ServiceUnavailableError(
            extractErrorMessage(data, "Service Unavailable"),
            data,
            endpoint,
            method,
          ),
        );

      default:
        return Promise.reject(
          ApiError.fromResponse(
            response,
            "An error occurred",
            endpoint,
            method,
          ),
        );
    }
  } else if (request) {
    // Network error
    return Promise.reject(
      new NetworkError(
        "Network error - no response received",
        undefined,
        endpoint,
        method,
      ),
    );
  } else {
    // Something else happened
    return Promise.reject(
      new ApiError(
        0,
        error.message || "An unknown error occurred",
        "UNKNOWN_ERROR",
        error,
        endpoint,
        method,
      ),
    );
  }
};

/**
 * Extract error message from response data
 */
function extractErrorMessage(data: unknown, fallback: string): string {
  if (typeof data === "object" && data !== null) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const errorData = data as any;
    return errorData.message || errorData.detail || fallback;
  }
  return fallback;
}

/**
 * Check if response data is a validation error response
 */
function isValidationErrorResponse(data: unknown): data is HTTPValidationError {
  return (
    typeof data === "object" &&
    data !== null &&
    "detail" in data &&
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    Array.isArray((data as any).detail)
  );
}
