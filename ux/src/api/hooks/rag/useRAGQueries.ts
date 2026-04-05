/**
 * RAG Query Hooks
 *
 * React Query hooks for retrieving RAG pipeline data
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import { ragService } from "@/api/services/rag";
import { QUERY_KEYS } from "@/api/config";
import { createQueryKey } from "@/api/utils/queryClient";
import type {
  MetricsResponse,
  TraceResponse,
  LayerTraceResponse,
} from "@/api/services/missingTypes";

/**
 * Hook to retrieve processing metrics for a RAG extraction request
 */
export const useRAGMetrics = (
  requestId: string | null,
  options?: UseQueryOptions<MetricsResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.RAG, "metrics", {
      requestId: requestId || "",
    }),
    queryFn: () => {
      if (!requestId) {
        throw new Error("Request ID is required to fetch metrics");
      }
      return ragService.getMetrics(requestId);
    },
    enabled: !!requestId,
    staleTime: 30 * 1000, // 30 seconds - metrics are relatively stable
    gcTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
};

/**
 * Hook to retrieve trace data for a RAG extraction request
 */
export const useRAGTrace = (
  requestId: string | null,
  options?: UseQueryOptions<TraceResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.RAG, "trace", {
      requestId: requestId || "",
    }),
    queryFn: () => {
      if (!requestId) {
        throw new Error("Request ID is required to fetch trace data");
      }
      return ragService.getTrace(requestId);
    },
    enabled: !!requestId,
    staleTime: 60 * 1000, // 1 minute - trace data doesn't change once created
    gcTime: 10 * 60 * 1000, // 10 minutes
    ...options,
  });
};

/**
 * Hook to retrieve trace data for a specific layer of a RAG extraction request
 */
export const useRAGTraceByLayer = (
  requestId: string | null,
  layerName: string | null,
  options?: UseQueryOptions<LayerTraceResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.RAG, "trace-layer", {
      requestId: requestId || "",
      layerName: layerName || "",
    }),
    queryFn: () => {
      if (!requestId) {
        throw new Error("Request ID is required to fetch trace data");
      }
      if (!layerName) {
        throw new Error("Layer name is required to fetch layer trace data");
      }
      return ragService.getTraceByLayer(requestId, layerName);
    },
    enabled: !!requestId && !!layerName,
    staleTime: 60 * 1000, // 1 minute - trace data doesn't change once created
    gcTime: 10 * 60 * 1000, // 10 minutes
    ...options,
  });
};
