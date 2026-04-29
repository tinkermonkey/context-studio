/**
 * API Error Classes
 *
 * Custom error classes for API operations
 */

import type { components } from "../client/types";

// Type alias for API error responses
type HTTPValidationError = components["schemas"]["HTTPValidationError"];
type ValidationErrorDetail = components["schemas"]["ValidationError"];

export class ApiError extends Error {
  constructor(
    public status: number,
    public message: string,
    public code?: string,
    public detail?: unknown,
    public endpoint?: string,
    public method?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  static fromResponse(
    response: { status: number; data?: unknown },
    fallbackMessage = "An error occurred",
    endpoint?: string,
    method?: string,
  ): ApiError {
    const message =
      typeof response.data === "object" && response.data !== null
        ?  
          (response.data as any).message || fallbackMessage
        : fallbackMessage;

    return new ApiError(
      response.status,
      message,
      typeof response.data === "object" && response.data !== null
        ?  
          (response.data as any).code
        : undefined,
      response.data,
      endpoint,
      method,
    );
  }

  /**
   * Get a user-friendly error message
   */
  getUserFriendlyMessage(): string {
    switch (this.status) {
      case 400:
        return "Invalid request. Please check your input and try again.";
      case 401:
        return "Authentication required. Please log in.";
      case 403:
        return "Access denied. You don't have permission to perform this action.";
      case 404:
        return "The requested resource was not found.";
      case 409:
        return "Conflict occurred. The resource may already exist or be in use.";
      case 422:
        return "Validation failed. Please check your input.";
      case 429:
        return "Too many requests. Please wait and try again.";
      case 500:
        return "Server error occurred. Please try again later.";
      case 503:
        return "Service is temporarily unavailable. Please try again later.";
      default:
        return this.message || "An unexpected error occurred.";
    }
  }

  /**
   * Check if this is a client-side error (4xx)
   */
  isClientError(): boolean {
    return this.status >= 400 && this.status < 500;
  }

  /**
   * Check if this is a server-side error (5xx)
   */
  isServerError(): boolean {
    return this.status >= 500;
  }
}

export class ValidationError extends ApiError {
  public validationErrors: Record<string, string[]>;

  constructor(
    message: string,
    validationErrors: Record<string, string[]>,
    detail?: unknown,
    endpoint?: string,
    method?: string,
  ) {
    super(422, message, "VALIDATION_ERROR", detail, endpoint, method);
    this.name = "ValidationError";
    this.validationErrors = validationErrors;
  }

  /**
   * Create ValidationError from FastAPI validation response
   */
  static fromValidationResponse(
    data: HTTPValidationError,
    endpoint?: string,
    method?: string,
  ): ValidationError {
    const validationErrors: Record<string, string[]> = {};

    if (data.detail && Array.isArray(data.detail)) {
      data.detail.forEach((error: ValidationErrorDetail) => {
        if (error.loc && error.msg) {
          const field = error.loc.join(".");
          if (!validationErrors[field]) {
            validationErrors[field] = [];
          }
          validationErrors[field].push(error.msg);
        }
      });
    }

    return new ValidationError(
      "Validation failed",
      validationErrors,
      data,
      endpoint,
      method,
    );
  }

  /**
   * Get validation errors for a specific field
   */
  getFieldErrors(field: string): string[] {
    return this.validationErrors[field] || [];
  }

  /**
   * Get all validation errors as a single message
   */
  getValidationMessage(): string {
    const allErrors = Object.entries(this.validationErrors)
      .map(([field, errors]) => `${field}: ${errors.join(", ")}`)
      .join("; ");
    return allErrors || this.message;
  }

  /**
   * Check if there are validation errors for a specific field
   */
  hasFieldErrors(field: string): boolean {
    return this.getFieldErrors(field).length > 0;
  }
}

export class NotFoundError extends ApiError {
  constructor(
    resource: string,
    id?: string,
    detail?: unknown,
    endpoint?: string,
    method?: string,
  ) {
    super(
      404,
      id ? `${resource} with ID ${id} not found` : `${resource} not found`,
      "NOT_FOUND",
      detail,
      endpoint,
      method,
    );
    this.name = "NotFoundError";
  }
}

export class ConflictError extends ApiError {
  constructor(
    message: string,
    detail?: unknown,
    endpoint?: string,
    method?: string,
  ) {
    super(409, message, "CONFLICT", detail, endpoint, method);
    this.name = "ConflictError";
  }
}

export class BadRequestError extends ApiError {
  constructor(
    message: string,
    detail?: unknown,
    endpoint?: string,
    method?: string,
  ) {
    super(400, message, "BAD_REQUEST", detail, endpoint, method);
    this.name = "BadRequestError";
  }
}

export class UnauthorizedError extends ApiError {
  constructor(
    message: string = "Authentication required",
    detail?: unknown,
    endpoint?: string,
    method?: string,
  ) {
    super(401, message, "UNAUTHORIZED", detail, endpoint, method);
    this.name = "UnauthorizedError";
  }
}

export class ForbiddenError extends ApiError {
  constructor(
    message: string = "Access forbidden",
    detail?: unknown,
    endpoint?: string,
    method?: string,
  ) {
    super(403, message, "FORBIDDEN", detail, endpoint, method);
    this.name = "ForbiddenError";
  }
}

export class TooManyRequestsError extends ApiError {
  constructor(
    message: string = "Too many requests",
    detail?: unknown,
    endpoint?: string,
    method?: string,
  ) {
    super(429, message, "TOO_MANY_REQUESTS", detail, endpoint, method);
    this.name = "TooManyRequestsError";
  }
}

export class InternalServerError extends ApiError {
  constructor(
    message: string = "Internal server error",
    detail?: unknown,
    endpoint?: string,
    method?: string,
  ) {
    super(500, message, "INTERNAL_SERVER_ERROR", detail, endpoint, method);
    this.name = "InternalServerError";
  }
}

export class ServiceUnavailableError extends ApiError {
  constructor(
    message: string = "Service unavailable",
    detail?: unknown,
    endpoint?: string,
    method?: string,
  ) {
    super(503, message, "SERVICE_UNAVAILABLE", detail, endpoint, method);
    this.name = "ServiceUnavailableError";
  }
}

export class NetworkError extends ApiError {
  constructor(
    message: string = "Network error occurred",
    detail?: unknown,
    endpoint?: string,
    method?: string,
  ) {
    super(0, message, "NETWORK_ERROR", detail, endpoint, method);
    this.name = "NetworkError";
  }
}
