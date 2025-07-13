/**
 * Axios Interceptors
 * 
 * Request and response interceptors for the API client
 */

import { InternalAxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';
import { apiLogger } from '../utils/logger';
import { ApiError, ValidationError, NotFoundError, ConflictError, NetworkError } from '../errors/ApiError';

export const requestInterceptor = (config: InternalAxiosRequestConfig) => {
  // Log outgoing requests
  apiLogger.request(config.method || 'GET', config.url || '', config.data);

  // Add any auth headers here if needed
  // config.headers.Authorization = `Bearer ${getAuthToken()}`;

  return config;
};

export const responseInterceptor = (response: AxiosResponse) => {
  // Log successful responses
  apiLogger.response(
    response.config.method || 'GET',
    response.config.url || '',
    response.status,
    response.data
  );

  return response;
};

export const errorInterceptor = (error: AxiosError) => {
  const { response, request, config } = error;

  // Log the error
  apiLogger.requestError(
    config?.method || 'GET',
    config?.url || '',
    error
  );

  // Handle different error scenarios
  if (response) {
    // Server responded with error status
    const { status, data } = response;

    switch (status) {
      case 400:
        return Promise.reject(new ApiError(400, 'Bad Request', 'BAD_REQUEST', data));
      
      case 401:
        return Promise.reject(new ApiError(401, 'Unauthorized', 'UNAUTHORIZED', data));
      
      case 403:
        return Promise.reject(new ApiError(403, 'Forbidden', 'FORBIDDEN', data));
      
      case 404:
        return Promise.reject(new NotFoundError('Resource'));
      
      case 409:
        return Promise.reject(new ConflictError('Resource conflict'));
      
      case 422:
        // Handle validation errors
        if (data && typeof data === 'object' && 'detail' in data) {
          const validationErrors: Record<string, string[]> = {};
          
          // Parse FastAPI validation errors
          if (Array.isArray(data.detail)) {
            data.detail.forEach((error: any) => {
              if (error.loc && error.msg) {
                const field = error.loc.join('.');
                if (!validationErrors[field]) {
                  validationErrors[field] = [];
                }
                validationErrors[field].push(error.msg);
              }
            });
          }
          
          return Promise.reject(new ValidationError('Validation failed', validationErrors));
        }
        return Promise.reject(new ApiError(422, 'Validation Error', 'VALIDATION_ERROR', data));
      
      case 500:
        return Promise.reject(new ApiError(500, 'Internal Server Error', 'INTERNAL_ERROR', data));
      
      default:
        return Promise.reject(ApiError.fromResponse(response, 'An error occurred'));
    }
  } else if (request) {
    // Network error
    return Promise.reject(new NetworkError('Network error - no response received'));
  } else {
    // Something else happened
    return Promise.reject(new ApiError(0, error.message || 'An unknown error occurred'));
  }
};
