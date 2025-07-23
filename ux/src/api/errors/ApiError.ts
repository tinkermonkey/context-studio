/**
 * API Error Classes
 * 
 * Custom error classes for API operations
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public message: string,
    public code?: string,
    public detail?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }

  static fromResponse(response: { status: number; data?: unknown }, fallbackMessage = 'An error occurred'): ApiError {
    const message = typeof response.data === 'object' && response.data !== null
      ? (response.data as any).message || fallbackMessage
      : fallbackMessage;

    return new ApiError(
      response.status,
      message,
      typeof response.data === 'object' && response.data !== null
        ? (response.data as any).code
        : undefined,
      response.data
    );
  }
}


export class ValidationError extends ApiError {
  constructor(message: string, public validationErrors: Record<string, string[]>, detail?: unknown) {
    super(422, message, 'VALIDATION_ERROR', detail ?? validationErrors);
    this.name = 'ValidationError';
  }
}


export class NotFoundError extends ApiError {
  constructor(resource: string, id?: string, detail?: unknown) {
    super(
      404,
      id ? `${resource} with ID ${id} not found` : `${resource} not found`,
      'NOT_FOUND',
      detail
    );
    this.name = 'NotFoundError';
  }
}


export class ConflictError extends ApiError {
  constructor(message: string, detail?: unknown) {
    super(409, message, 'CONFLICT', detail);
    this.name = 'ConflictError';
  }
}


export class NetworkError extends ApiError {
  constructor(message: string = 'Network error occurred', detail?: unknown) {
    super(0, message, 'NETWORK_ERROR', detail);
    this.name = 'NetworkError';
  }
}
