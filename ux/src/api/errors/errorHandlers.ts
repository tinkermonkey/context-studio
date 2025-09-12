/**
 * API Error Handlers
 *
 * Utilities for handling API errors and showing user-friendly messages
 */

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
} from "./ApiError";
import { apiLogger } from "../utils/logger";

// TODO: Replace with your actual toast implementation
// import { showToast } from '../utils/toast';

interface ErrorHandlerOptions {
  showToast?: boolean;
  logError?: boolean;
  defaultMessage?: string;
  context?: string;
}

const DEFAULT_ERROR_MESSAGES = {
  400: "Bad request. Please check your input.",
  401: "Authentication required. Please log in.",
  403: "Access denied. You don't have permission to perform this action.",
  404: "Resource not found.",
  409: "Conflict. The resource already exists or is in use.",
  422: "Validation error. Please check your input.",
  429: "Too many requests. Please wait and try again.",
  500: "Internal server error. Please try again later.",
  503: "Service unavailable. Please try again later.",
} as const;

export const handleApiError = (
  error: unknown,
  options: ErrorHandlerOptions = {},
): ApiError => {
  const {
    showToast = true,
    logError = true,
    defaultMessage = "An unexpected error occurred",
    context,
  } = options;

  let apiError: ApiError;

  if (error instanceof ApiError) {
    apiError = error;
  } else if (error instanceof Error) {
    if (
      error.message.includes("Network Error") ||
      error.message.includes("timeout")
    ) {
      apiError = new NetworkError(error.message);
    } else {
      apiError = new ApiError(500, error.message || defaultMessage);
    }
  } else {
    apiError = new ApiError(500, defaultMessage);
  }

  if (logError) {
    apiLogger.error("API Error occurred", {
      status: apiError.status,
      message: apiError.message,
      code: apiError.code,
      detail: apiError.detail,
      endpoint: apiError.endpoint,
      method: apiError.method,
      context,
    });
  }

  if (showToast) {
    showErrorToast(apiError, context);
  }

  return apiError;
};

const showErrorToast = (error: ApiError, context?: string) => {
  let message = error.getUserFriendlyMessage();

  // Add context if provided
  if (context) {
    message = `${context}: ${message}`;
  }

  // Special handling for validation errors
  if (error instanceof ValidationError) {
    const validationMessage = error.getValidationMessage();
    if (validationMessage) {
      message = `Validation Error: ${validationMessage}`;
    }
  }

  // TODO: Replace with actual toast implementation
  // showToast(message, 'error');
  console.error("Toast would show:", message);
};

export const getErrorMessage = (error: unknown, context?: string): string => {
  let message = "An unexpected error occurred";

  if (error instanceof ApiError) {
    message = error.getUserFriendlyMessage();

    // Special handling for validation errors
    if (error instanceof ValidationError) {
      const validationMessage = error.getValidationMessage();
      if (validationMessage) {
        message = validationMessage;
      }
    }
  } else if (error instanceof Error) {
    message = error.message;
  }

  return context ? `${context}: ${message}` : message;
};

export const getDetailedErrorInfo = (
  error: unknown,
): {
  message: string;
  status?: number;
  code?: string;
  detail?: unknown;
  validationErrors?: Record<string, string[]>;
} => {
  if (error instanceof ValidationError) {
    return {
      message: error.message,
      status: error.status,
      code: error.code,
      detail: error.detail,
      validationErrors: error.validationErrors,
    };
  }

  if (error instanceof ApiError) {
    return {
      message: error.message,
      status: error.status,
      code: error.code,
      detail: error.detail,
    };
  }

  if (error instanceof Error) {
    return {
      message: error.message,
    };
  }

  return {
    message: "An unexpected error occurred",
  };
};

export const isNetworkError = (error: unknown): boolean => {
  return (
    error instanceof NetworkError ||
    (error instanceof Error && error.message.includes("Network Error"))
  );
};

export const isValidationError = (error: unknown): error is ValidationError => {
  return error instanceof ValidationError;
};

export const isNotFoundError = (error: unknown): error is NotFoundError => {
  return error instanceof NotFoundError;
};

export const isConflictError = (error: unknown): error is ConflictError => {
  return error instanceof ConflictError;
};

export const isBadRequestError = (error: unknown): error is BadRequestError => {
  return error instanceof BadRequestError;
};

export const isUnauthorizedError = (
  error: unknown,
): error is UnauthorizedError => {
  return error instanceof UnauthorizedError;
};

export const isForbiddenError = (error: unknown): error is ForbiddenError => {
  return error instanceof ForbiddenError;
};

export const isTooManyRequestsError = (
  error: unknown,
): error is TooManyRequestsError => {
  return error instanceof TooManyRequestsError;
};

export const isServerError = (error: unknown): boolean => {
  return error instanceof ApiError && error.isServerError();
};

export const isClientError = (error: unknown): boolean => {
  return error instanceof ApiError && error.isClientError();
};

/**
 * Extract field validation errors from a ValidationError
 */
export const getFieldErrors = (error: unknown, field: string): string[] => {
  if (error instanceof ValidationError) {
    return error.getFieldErrors(field);
  }
  return [];
};

/**
 * Check if there are field validation errors
 */
export const hasFieldErrors = (error: unknown, field: string): boolean => {
  if (error instanceof ValidationError) {
    return error.hasFieldErrors(field);
  }
  return false;
};

/**
 * Format error for form display
 */
export const formatFormError = (
  error: unknown,
): {
  message: string;
  fieldErrors: Record<string, string[]>;
} => {
  if (error instanceof ValidationError) {
    return {
      message: error.message,
      fieldErrors: error.validationErrors,
    };
  }

  return {
    message: getErrorMessage(error),
    fieldErrors: {},
  };
};
