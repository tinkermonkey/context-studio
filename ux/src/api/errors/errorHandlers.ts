/**
 * API Error Handlers
 * 
 * Utilities for handling API errors and showing user-friendly messages
 */

import { ApiError, ValidationError, NotFoundError, ConflictError, NetworkError } from './ApiError';
import { apiLogger } from '../utils/logger';

// TODO: Replace with your actual toast implementation
// import { showToast } from '../utils/toast';

interface ErrorHandlerOptions {
  showToast?: boolean;
  logError?: boolean;
  defaultMessage?: string;
}

const DEFAULT_ERROR_MESSAGES = {
  400: 'Bad request. Please check your input.',
  401: 'Authentication required. Please log in.',
  403: 'Access denied. You don\'t have permission to perform this action.',
  404: 'Resource not found.',
  409: 'Conflict. The resource already exists or is in use.',
  422: 'Validation error. Please check your input.',
  500: 'Internal server error. Please try again later.',
  503: 'Service unavailable. Please try again later.',
} as const;

export const handleApiError = (
  error: unknown,
  options: ErrorHandlerOptions = {}
): ApiError => {
  const {
    showToast = true,
    logError = true,
    defaultMessage = 'An unexpected error occurred',
  } = options;

  let apiError: ApiError;

  if (error instanceof ApiError) {
    apiError = error;
  } else if (error instanceof Error) {
    if (error.message.includes('Network Error') || error.message.includes('timeout')) {
      apiError = new NetworkError(error.message);
    } else {
      apiError = new ApiError(500, error.message || defaultMessage);
    }
  } else {
    apiError = new ApiError(500, defaultMessage);
  }

  if (logError) {
    apiLogger.error('API Error occurred', {
      status: apiError.status,
      message: apiError.message,
      code: apiError.code,
      details: apiError.details,
    });
  }

  if (showToast) {
    showErrorToast(apiError);
  }

  return apiError;
};

const showErrorToast = (error: ApiError) => {
  let message = error.message;
  
  // Use default messages for common HTTP status codes
  if (error.status in DEFAULT_ERROR_MESSAGES) {
    message = DEFAULT_ERROR_MESSAGES[error.status as keyof typeof DEFAULT_ERROR_MESSAGES];
  }

  // TODO: Replace with actual toast implementation
  // showToast(message, 'error');
  console.error('Toast would show:', message);
};

export const getErrorMessage = (error: unknown): string => {
  if (error instanceof ApiError) {
    return error.message;
  }
  
  if (error instanceof Error) {
    return error.message;
  }
  
  return 'An unexpected error occurred';
};

export const isNetworkError = (error: unknown): boolean => {
  return error instanceof NetworkError || 
         (error instanceof Error && error.message.includes('Network Error'));
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
