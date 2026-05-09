/**
 * LLM Traceability Query Hooks
 *
 * React Query hooks for LLM traceability data fetching and caching
 * Following patterns from existing LLM analysis hooks
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import {
  llmTraceabilityService,
  type ExecutionAnalyticsResponse,
  type ExecutionHistoryResponse,
  type LLMTraceabilityHealthResponse,
  type AnalyticsFilters,
  type ExecutionHistoryFilters,
  type ExecutionHistoryByFlavorResponse,
  type FlavorAnalyticsResponse,
  type FlavorExecutionHistoryFilters,
  type FlavorAnalyticsFilters,
} from "../../services/llmTraceability";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

/**
 * Hook to get LLM traceability service health status
 */
export const useLLMTraceabilityHealth = (
  options?: UseQueryOptions<LLMTraceabilityHealthResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LLM_TRACEABILITY, "health"),
    queryFn: () => llmTraceabilityService.healthCheck(),
    staleTime: 1 * 60 * 1000, // 1 minute - health checks should be relatively fresh
    gcTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
    ...options,
  });
};

/**
 * Hook to get execution analytics with optional filtering
 */
export const useExecutionAnalytics = (
  filters?: AnalyticsFilters | null,
  options?: UseQueryOptions<ExecutionAnalyticsResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.LLM_TRACEABILITY,
      "analytics",
      (filters as Record<string, unknown>) || {},
    ),
    queryFn: () =>
      llmTraceabilityService.getExecutionAnalytics(filters || undefined),
    staleTime: 5 * 60 * 1000, // 5 minutes - analytics can be slightly stale
    gcTime: 30 * 60 * 1000, // 30 minutes
    retry: 2,
    ...options,
  });
};

/**
 * Hook to get analytics for a specific time range
 */
export const useAnalyticsForTimeRange = (
  daysBack: number | null,
  pipelineType?: string | null,
  options?: UseQueryOptions<ExecutionAnalyticsResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.LLM_TRACEABILITY,
      "analytics-time-range",
      {
        daysBack: daysBack || 0,
        pipelineType: pipelineType || "",
      },
    ),
    queryFn: () => {
      if (!daysBack || daysBack <= 0) {
        throw new Error("Days back must be a positive number");
      }
      return llmTraceabilityService.getAnalyticsForTimeRange(
        daysBack,
        pipelineType || undefined,
      );
    },
    enabled: !!daysBack && daysBack > 0,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    retry: 2,
    ...options,
  });
};

/**
 * Hook to get dashboard analytics (convenience hook with sensible defaults)
 */
export const useDashboardAnalytics = (
  daysBack: number = 30,
  options?: UseQueryOptions<ExecutionAnalyticsResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.LLM_TRACEABILITY,
      "dashboard-analytics",
      { daysBack },
    ),
    queryFn: () => llmTraceabilityService.getDashboardAnalytics(daysBack),
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    retry: 2,
    ...options,
  });
};

/**
 * Hook to get detailed execution history for a specific execution
 */
export const useExecutionHistory = (
  executionId: string | null,
  options?: UseQueryOptions<ExecutionHistoryResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LLM_TRACEABILITY, "execution-history", {
      executionId: executionId || "",
    }),
    queryFn: () => {
      if (!executionId) {
        throw new Error("Execution ID is required for execution history");
      }
      return llmTraceabilityService.getExecutionHistory(executionId);
    },
    enabled: !!executionId && executionId.trim().length > 0,
    staleTime: 2 * 60 * 1000, // 2 minutes - execution details should be relatively fresh
    gcTime: 15 * 60 * 1000, // 15 minutes
    retry: 2,
    ...options,
  });
};

/**
 * Hook to get multiple execution histories with filtering
 */
export const useExecutionHistories = (
  filters?: ExecutionHistoryFilters | null,
  options?: UseQueryOptions<ExecutionHistoryResponse[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.LLM_TRACEABILITY,
      "execution-histories",
      (filters as Record<string, unknown>) || {},
    ),
    queryFn: () =>
      llmTraceabilityService.getExecutionHistories(filters || undefined),
    staleTime: 2 * 60 * 1000,
    gcTime: 15 * 60 * 1000,
    retry: 2,
    ...options,
  });
};

/**
 * Hook to get recent executions (convenience hook)
 * @deprecated Use useFlavorExecutionHistory with a specific flavor_id instead
 */
export const useRecentExecutions = (
  limit: number = 10,
  pipelineType?: string | null,
  flavorId?: string | null,
  options?: UseQueryOptions<ExecutionHistoryResponse[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LLM_TRACEABILITY, "recent-executions", {
      limit,
      pipelineType: pipelineType || "",
      flavorId: flavorId || "",
    }),
    queryFn: () => {
      if (!flavorId) {
        throw new Error(
          "Recent executions requires a flavor_id. Use useFlavorExecutionHistory with a specific flavor_id instead.",
        );
      }
      return llmTraceabilityService.getRecentExecutions(
        limit,
        pipelineType || undefined,
        flavorId,
      );
    },
    enabled: !!flavorId && flavorId.trim().length > 0,
    staleTime: 1 * 60 * 1000, // 1 minute - recent executions should be fresh
    gcTime: 10 * 60 * 1000, // 10 minutes
    retry: 2,
    ...options,
  });
};

/**
 * Hook to check if the traceability system is healthy
 */
export const useIsSystemHealthy = (
  options?: UseQueryOptions<boolean, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LLM_TRACEABILITY, "system-healthy"),
    queryFn: () => llmTraceabilityService.isSystemHealthy(),
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 2 * 60 * 1000, // 2 minutes
    retry: 1,
    ...options,
  });
};

/**
 * Hook for analytics with auto-refresh capability
 */
export const useAnalyticsWithRefresh = (
  daysBack: number = 30,
  refreshInterval?: number, // milliseconds
  options?: UseQueryOptions<ExecutionAnalyticsResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LLM_TRACEABILITY, "analytics-refresh", {
      daysBack,
    }),
    queryFn: () => llmTraceabilityService.getDashboardAnalytics(daysBack),
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    retry: 2,
    refetchInterval: refreshInterval,
    refetchIntervalInBackground: false,
    ...options,
  });
};

/**
 * Hook for execution histories with auto-refresh capability
 */
export const useExecutionHistoriesWithRefresh = (
  filters?: ExecutionHistoryFilters | null,
  refreshInterval?: number, // milliseconds
  options?: UseQueryOptions<ExecutionHistoryResponse[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.LLM_TRACEABILITY,
      "histories-refresh",
      (filters as Record<string, unknown>) || {},
    ),
    queryFn: () =>
      llmTraceabilityService.getExecutionHistories(filters || undefined),
    staleTime: 2 * 60 * 1000,
    gcTime: 15 * 60 * 1000,
    retry: 2,
    refetchInterval: refreshInterval,
    refetchIntervalInBackground: false,
    ...options,
  });
};

/**
 * Hook to get execution history for a specific flavor
 */
export const useFlavorExecutionHistory = (
  filters: FlavorExecutionHistoryFilters | null,
  options?: UseQueryOptions<ExecutionHistoryByFlavorResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.LLM_TRACEABILITY,
      "flavor-execution-history",
      (filters || {}) as Record<string, unknown>,
    ),
    queryFn: () => {
      if (!filters?.flavor_id) {
        throw new Error("Flavor ID is required for flavor execution history");
      }
      return llmTraceabilityService.getFlavorExecutionHistory(filters);
    },
    enabled: !!filters?.flavor_id && filters.flavor_id.trim().length > 0,
    staleTime: 2 * 60 * 1000, // 2 minutes - flavor executions should be relatively fresh
    gcTime: 15 * 60 * 1000, // 15 minutes
    retry: 2,
    ...options,
  });
};

/**
 * Hook to get analytics for a specific flavor
 */
export const useFlavorAnalytics = (
  filters: FlavorAnalyticsFilters | null,
  options?: UseQueryOptions<FlavorAnalyticsResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.LLM_TRACEABILITY,
      "flavor-analytics",
      (filters || {}) as Record<string, unknown>,
    ),
    queryFn: () => {
      if (!filters?.flavor_id) {
        throw new Error("Flavor ID is required for flavor analytics");
      }
      return llmTraceabilityService.getFlavorAnalytics(filters);
    },
    enabled: !!filters?.flavor_id && filters.flavor_id.trim().length > 0,
    staleTime: 5 * 60 * 1000, // 5 minutes - analytics can be slightly stale
    gcTime: 30 * 60 * 1000, // 30 minutes
    retry: 2,
    ...options,
  });
};

/**
 * Hook to get flavor analytics with auto-refresh capability
 */
export const useFlavorAnalyticsWithRefresh = (
  filters: FlavorAnalyticsFilters | null,
  refreshInterval?: number, // milliseconds
  options?: UseQueryOptions<FlavorAnalyticsResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.LLM_TRACEABILITY,
      "flavor-analytics-refresh",
      (filters || {}) as Record<string, unknown>,
    ),
    queryFn: () => {
      if (!filters?.flavor_id) {
        throw new Error("Flavor ID is required for flavor analytics");
      }
      return llmTraceabilityService.getFlavorAnalytics(filters);
    },
    enabled: !!filters?.flavor_id && filters.flavor_id.trim().length > 0,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    retry: 2,
    refetchInterval: refreshInterval,
    refetchIntervalInBackground: false,
    ...options,
  });
};
