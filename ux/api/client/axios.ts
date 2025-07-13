/**
 * Axios Client Configuration
 * 
 * Main HTTP client instance with configured interceptors
 */

import axios, { AxiosInstance } from 'axios';
import { API_CONFIG } from '../config';
import { requestInterceptor, responseInterceptor, errorInterceptor } from './interceptors';

// Create the main API client instance
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_CONFIG.baseURL,
  timeout: API_CONFIG.timeout,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Apply interceptors
apiClient.interceptors.request.use(requestInterceptor);
apiClient.interceptors.response.use(responseInterceptor, errorInterceptor);

// Export a function to update the base URL if needed
export const updateBaseURL = (newBaseURL: string) => {
  apiClient.defaults.baseURL = newBaseURL;
};

// Export a function to set auth token
export const setAuthToken = (token: string | null) => {
  if (token) {
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete apiClient.defaults.headers.common['Authorization'];
  }
};
