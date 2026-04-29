/**
 * React Query Configuration
 *
 * Query client setup for TanStack Query
 */

import { QueryClient, QueryClientConfig } from "@tanstack/react-query";
import { API_CONFIG } from "../config";
import { handleApiError } from "../errors/errorHandlers";

const queryClientConfig: QueryClientConfig = {
  defaultOptions: {
    queries: {
      staleTime: API_CONFIG.staleTime,
      gcTime: API_CONFIG.cacheTime, // formerly cacheTime
      retry: (failureCount, error) => {
        // Don't retry on 4xx errors (client errors)
        if (error instanceof Error && "status" in error) {
           
          const status = (error as any).status;
          if (status >= 400 && status < 500) {
            return false;
          }
        }
        return failureCount < API_CONFIG.retryAttempts;
      },
      // Exponential backoff with jitter to prevent thundering herd
      retryDelay: (attemptIndex) => {
        const baseDelay = API_CONFIG.retryDelay * 2 ** attemptIndex;
        const jitter = Math.random() * 1000; // Add random jitter (0-1000ms)
        return Math.min(baseDelay + jitter, API_CONFIG.maxRetryDelay);
      },
    },
    mutations: {
      retry: false,
      onError: (error) => {
        handleApiError(error);
      },
    },
  },
};

export const queryClient = new QueryClient(queryClientConfig);

// Query key factory for consistent key generation
export const createQueryKey = (
  entity: string,
  id?: string | number,
  params?: Record<string, unknown>,
): string[] => {
  const key = [entity];

  if (id !== undefined) {
    key.push(String(id));
  }

  if (params) {
    key.push(JSON.stringify(params));
  }

  return key;
};
