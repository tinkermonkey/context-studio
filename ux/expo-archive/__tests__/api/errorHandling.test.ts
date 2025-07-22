/**
 * Error Handling Tests
 * 
 * Tests for API error handling functionality
 */

import { ApiError, ValidationError, NotFoundError, ConflictError, NetworkError } from '../../api/errors/ApiError';
import { handleApiError, getErrorMessage, isValidationError, isNetworkError } from '../../api/errors/errorHandlers';

describe('Error Handling', () => {
  // Mock console to avoid noise in tests
  const mockConsoleError = jest.fn();
  const originalConsoleError = console.error;

  beforeEach(() => {
    console.error = mockConsoleError;
    mockConsoleError.mockClear();
  });

  afterEach(() => {
    console.error = originalConsoleError;
  });

  describe('ApiError', () => {
    it('should create an ApiError with correct properties', () => {
      const error = new ApiError(404, 'Not found', 'NOT_FOUND', { id: '123' });

      expect(error.name).toBe('ApiError');
      expect(error.status).toBe(404);
      expect(error.message).toBe('Not found');
      expect(error.code).toBe('NOT_FOUND');
      expect(error.details).toEqual({ id: '123' });
    });

    it('should create an ApiError from response', () => {
      const response = {
        status: 422,
        data: {
          message: 'Validation failed',
          code: 'VALIDATION_ERROR',
        },
      };

      const error = ApiError.fromResponse(response);

      expect(error.status).toBe(422);
      expect(error.message).toBe('Validation failed');
      expect(error.code).toBe('VALIDATION_ERROR');
    });

    it('should use fallback message when response has no message', () => {
      const response = { status: 500, data: {} };
      const fallback = 'Server error';

      const error = ApiError.fromResponse(response, fallback);

      expect(error.message).toBe(fallback);
    });
  });

  describe('ValidationError', () => {
    it('should create a ValidationError with validation details', () => {
      const validationErrors = {
        title: ['String should have at least 2 characters'],
        email: ['Invalid email format'],
      };

      const error = new ValidationError('Validation failed', validationErrors);

      expect(error.name).toBe('ValidationError');
      expect(error.status).toBe(422);
      expect(error.code).toBe('VALIDATION_ERROR');
      expect(error.validationErrors).toEqual(validationErrors);
    });
  });

  describe('NotFoundError', () => {
    it('should create a NotFoundError for a resource', () => {
      const error = new NotFoundError('Layer');

      expect(error.name).toBe('NotFoundError');
      expect(error.status).toBe(404);
      expect(error.message).toBe('Layer not found');
      expect(error.code).toBe('NOT_FOUND');
    });

    it('should create a NotFoundError with ID', () => {
      const error = new NotFoundError('Layer', '123');

      expect(error.message).toBe('Layer with ID 123 not found');
    });
  });

  describe('ConflictError', () => {
    it('should create a ConflictError', () => {
      const error = new ConflictError('Resource already exists');

      expect(error.name).toBe('ConflictError');
      expect(error.status).toBe(409);
      expect(error.message).toBe('Resource already exists');
      expect(error.code).toBe('CONFLICT');
    });
  });

  describe('NetworkError', () => {
    it('should create a NetworkError', () => {
      const error = new NetworkError('Connection failed');

      expect(error.name).toBe('NetworkError');
      expect(error.status).toBe(0);
      expect(error.message).toBe('Connection failed');
      expect(error.code).toBe('NETWORK_ERROR');
    });

    it('should use default message', () => {
      const error = new NetworkError();

      expect(error.message).toBe('Network error occurred');
    });
  });

  describe('handleApiError', () => {
    it('should handle ApiError instances', () => {
      const apiError = new ApiError(500, 'Server error');
      const result = handleApiError(apiError, { showToast: true, logError: false });

      expect(result).toBe(apiError);
      expect(mockConsoleError).toHaveBeenCalledWith(
        'Toast would show:',
        'Internal server error. Please try again later.'
      );
    });

    it('should handle regular Error instances', () => {
      const error = new Error('Something went wrong');
      const result = handleApiError(error, { showToast: false });

      expect(result).toBeInstanceOf(ApiError);
      expect(result.message).toBe('Something went wrong');
      expect(result.status).toBe(500);
    });

    it('should handle network errors', () => {
      const error = new Error('Network Error: timeout');
      const result = handleApiError(error, { showToast: false });

      expect(result).toBeInstanceOf(NetworkError);
      expect(result.message).toBe('Network Error: timeout');
    });

    it('should handle unknown errors', () => {
      const error = 'string error';
      const result = handleApiError(error, { showToast: false });

      expect(result).toBeInstanceOf(ApiError);
      expect(result.status).toBe(500);
      expect(result.message).toBe('An unexpected error occurred');
    });

    it('should skip logging when logError is false', () => {
      const error = new ApiError(404, 'Not found');
      handleApiError(error, { logError: false, showToast: false });

      expect(mockConsoleError).not.toHaveBeenCalled();
    });
  });

  describe('getErrorMessage', () => {
    it('should get message from ApiError', () => {
      const error = new ApiError(404, 'Not found');
      expect(getErrorMessage(error)).toBe('Not found');
    });

    it('should get message from regular Error', () => {
      const error = new Error('Something failed');
      expect(getErrorMessage(error)).toBe('Something failed');
    });

    it('should return default message for unknown errors', () => {
      expect(getErrorMessage('string error')).toBe('An unexpected error occurred');
      expect(getErrorMessage(null)).toBe('An unexpected error occurred');
      expect(getErrorMessage(undefined)).toBe('An unexpected error occurred');
    });
  });

  describe('error type guards', () => {
    it('should identify ValidationError', () => {
      const validationError = new ValidationError('Validation failed', {});
      const otherError = new ApiError(500, 'Server error');

      expect(isValidationError(validationError)).toBe(true);
      expect(isValidationError(otherError)).toBe(false);
    });

    it('should identify NetworkError', () => {
      const networkError = new NetworkError();
      const otherError = new ApiError(500, 'Server error');
      const regularError = new Error('Network Error: failed');

      expect(isNetworkError(networkError)).toBe(true);
      expect(isNetworkError(regularError)).toBe(true);
      expect(isNetworkError(otherError)).toBe(false);
    });
  });
});
