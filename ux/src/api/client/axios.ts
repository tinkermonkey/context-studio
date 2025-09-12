/**
 * Axios Client Configuration
 *
 * Main HTTP client instance with configured interceptors
 */

import axios, { AxiosInstance } from "axios";
import { API_CONFIG } from "../config";
import {
  requestInterceptor,
  responseInterceptor,
  errorInterceptor,
} from "./interceptors";

// Lazily initialize the axios instance so test setup can modify global environment
// (delete fetch/XMLHttpRequest) before adapter selection occurs.
let _internalClient: AxiosInstance | null = null;
function createClient() {
  const client = axios.create({
    baseURL: API_CONFIG.baseURL,
  });

  // Apply interceptors
  client.interceptors.request.use(requestInterceptor);
  client.interceptors.response.use(responseInterceptor, errorInterceptor);

  return client;
}

const ensureClient = () => {
  if (!_internalClient) _internalClient = createClient();
  return _internalClient;
};

// Export a Proxy that forwards all property accesses to the lazily-created axios instance.
// This preserves the existing `apiClient` import API while delaying adapter selection.
export const apiClient: AxiosInstance = new Proxy({} as AxiosInstance, {
  get(_, prop: string | symbol) {
    const client = ensureClient();
    // @ts-ignore
    return (client as any)[prop];
  },
  set(_, prop: string | symbol, value) {
    const client = ensureClient();
    // @ts-ignore
    (client as any)[prop] = value;
    return true;
  },
  apply(_, __, args: any[]) {
    const client = ensureClient();
    // @ts-ignore
    return (client as any).apply(_, args);
  },
}) as unknown as AxiosInstance;

// Export helper functions that operate on the underlying client
export const updateBaseURL = (newBaseURL: string) => {
  ensureClient().defaults.baseURL = newBaseURL;
};

export const setAuthToken = (token: string | null) => {
  const client = ensureClient();
  if (token) {
    client.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete client.defaults.headers.common["Authorization"];
  }
};
