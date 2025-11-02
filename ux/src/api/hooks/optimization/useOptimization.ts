/**
 * Optimization API Hooks
 *
 * React Query hooks for optimization endpoints
 */

import { useQuery, useMutation, UseQueryOptions, UseMutationOptions } from "@tanstack/react-query";
import { apiClient } from "@/api/client/axios";

// API Response Types
export interface SystemHealth {
  status: string;
  services_healthy: Record<string, boolean>;
  performance_score: number;
  optimization_enabled: boolean;
  last_optimization?: string;
  issues: string[];
}

export interface PerformanceMetrics {
  timestamp: string;
  database_metrics: Record<string, any>;
  s3_metrics: Record<string, any>;
  query_metrics: Record<string, any>;
  system_metrics: Record<string, any>;
  cache_metrics: Record<string, any>;
  batch_metrics: Record<string, any>;
}

export interface PerformanceTrends {
  analysis_window_hours: number;
  trends: Record<string, any>;
  issues: Array<Record<string, any>>;
  recommendations: Array<Record<string, any>>;
  overall_health_score: number;
  performance_grade: string;
}

export interface QueryStats {
  total_queries: number;
  avg_execution_time_ms: number;
  cache_stats: Record<string, any>;
  materialized_views_count: number;
}

export interface QueryOptimization {
  original_query: string;
  optimized_query: string;
  metrics: Record<string, any>;
  optimization_applied: string[];
}

export interface StorageStats {
  optimization_summary: {
    files_optimized: number;
    total_savings_bytes: number;
    average_compression_ratio: number;
  };
  compression_algorithms_used: Record<string, any>;
  total_optimizations: number;
}

export interface StorageOptimization {
  optimization_actions: Array<Record<string, any>>;
  storage_saved_bytes: number;
  cost_reduction_estimate: number;
  objects_optimized: number;
}

export interface ThreeWayDiff {
  diff_result: Record<string, any>;
  conflicts_detected: Array<Record<string, any>>;
  semantic_insights?: Record<string, any>;
  merge_recommendation?: string;
}

export interface BatchOperationResult {
  operation_id: string;
  total_items: number;
  successful_items: number;
  failed_items: number;
  processing_time_seconds: number;
  throughput_per_second: number;
  errors: Array<Record<string, any>>;
}

// Request Types
export interface QueryOptimizationRequest {
  query: string;
  context?: Record<string, any>;
}

export interface MaterializedViewRequest {
  view_name: string;
  query: string;
  refresh_strategy?: string;
}

export interface ThreeWayDiffRequest {
  base: Record<string, any>;
  local: Record<string, any>;
  remote: Record<string, any>;
  enable_semantic_analysis?: boolean;
}

export interface BatchOperationRequest {
  operation_type: string;
  entity_data: Array<Record<string, any>>;
  author_id: string;
  options?: Record<string, any>;
}

// Query Keys
export const optimizationKeys = {
  all: ["optimization"] as const,
  health: () => [...optimizationKeys.all, "health"] as const,
  performanceDashboard: () => [...optimizationKeys.all, "performance", "dashboard"] as const,
  performanceMetrics: () => [...optimizationKeys.all, "performance", "metrics"] as const,
  performanceTrends: (windowHours: number) =>
    [...optimizationKeys.all, "performance", "trends", windowHours] as const,
  queryStats: () => [...optimizationKeys.all, "query", "stats"] as const,
  storageStats: () => [...optimizationKeys.all, "storage", "stats"] as const,
  diffStats: () => [...optimizationKeys.all, "diff", "stats"] as const,
  batchStats: () => [...optimizationKeys.all, "batch", "stats"] as const,
  config: () => [...optimizationKeys.all, "config"] as const,
};

// Query Hooks

export function useSystemHealth(options?: UseQueryOptions<SystemHealth>) {
  return useQuery<SystemHealth>({
    queryKey: optimizationKeys.health(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/health`);
      return response.data;
    },
    ...options,
  });
}

export function usePerformanceDashboard(options?: UseQueryOptions<Record<string, any>>) {
  return useQuery<Record<string, any>>({
    queryKey: optimizationKeys.performanceDashboard(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/performance/dashboard`);
      return response.data;
    },
    ...options,
  });
}

export function usePerformanceMetrics(options?: UseQueryOptions<PerformanceMetrics>) {
  return useQuery<PerformanceMetrics>({
    queryKey: optimizationKeys.performanceMetrics(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/performance/metrics`);
      return response.data;
    },
    ...options,
  });
}

export function usePerformanceTrends(
  windowHours: number = 24,
  options?: UseQueryOptions<PerformanceTrends>
) {
  return useQuery<PerformanceTrends>({
    queryKey: optimizationKeys.performanceTrends(windowHours),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/performance/trends`, {
        params: { window_hours: windowHours },
      });
      return response.data;
    },
    ...options,
  });
}

export function useQueryStats(options?: UseQueryOptions<QueryStats>) {
  return useQuery<QueryStats>({
    queryKey: optimizationKeys.queryStats(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/query/stats`);
      return response.data;
    },
    ...options,
  });
}

export function useStorageStats(options?: UseQueryOptions<StorageStats>) {
  return useQuery<StorageStats>({
    queryKey: optimizationKeys.storageStats(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/storage/stats`);
      return response.data;
    },
    ...options,
  });
}

export function useDiffStats(options?: UseQueryOptions<Record<string, any>>) {
  return useQuery<Record<string, any>>({
    queryKey: optimizationKeys.diffStats(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/diff/stats`);
      return response.data;
    },
    ...options,
  });
}

export function useBatchStats(options?: UseQueryOptions<Record<string, any>>) {
  return useQuery<Record<string, any>>({
    queryKey: optimizationKeys.batchStats(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/batch/stats`);
      return response.data;
    },
    ...options,
  });
}

export function useOptimizationConfig(options?: UseQueryOptions<Record<string, any>>) {
  return useQuery<Record<string, any>>({
    queryKey: optimizationKeys.config(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/config`);
      return response.data;
    },
    ...options,
  });
}

// Mutation Hooks

export function useAutoOptimize(options?: UseMutationOptions<any, Error, void>) {
  return useMutation<any, Error, void>({
    mutationFn: async () => {
      const response = await apiClient.post(`/api/optimization/performance/auto-optimize`);
      return response.data;
    },
    ...options,
  });
}

export function useOptimizeQuery(
  options?: UseMutationOptions<QueryOptimization, Error, QueryOptimizationRequest>
) {
  return useMutation<QueryOptimization, Error, QueryOptimizationRequest>({
    mutationFn: async (request) => {
      const response = await apiClient.post(`/api/optimization/query/optimize`, request);
      return response.data;
    },
    ...options,
  });
}

export function useCreateMaterializedView(
  options?: UseMutationOptions<any, Error, MaterializedViewRequest>
) {
  return useMutation<any, Error, MaterializedViewRequest>({
    mutationFn: async (request) => {
      const response = await apiClient.post(`/api/optimization/query/materialized-view`, request);
      return response.data;
    },
    ...options,
  });
}

export function useOptimizeStorage(options?: UseMutationOptions<StorageOptimization, Error, void>) {
  return useMutation<StorageOptimization, Error, void>({
    mutationFn: async () => {
      const response = await apiClient.post(`/api/optimization/storage/optimize`);
      return response.data;
    },
    ...options,
  });
}

export function useSetupLifecyclePolicies(options?: UseMutationOptions<any, Error, void>) {
  return useMutation<any, Error, void>({
    mutationFn: async () => {
      const response = await apiClient.post(`/api/optimization/storage/lifecycle-policies`);
      return response.data;
    },
    ...options,
  });
}

export function useThreeWayDiff(
  options?: UseMutationOptions<ThreeWayDiff, Error, ThreeWayDiffRequest>
) {
  return useMutation<ThreeWayDiff, Error, ThreeWayDiffRequest>({
    mutationFn: async (request) => {
      const response = await apiClient.post(`/api/optimization/diff/three-way`, request);
      return response.data;
    },
    ...options,
  });
}

export function useBatchOperation(
  options?: UseMutationOptions<BatchOperationResult, Error, BatchOperationRequest>
) {
  return useMutation<BatchOperationResult, Error, BatchOperationRequest>({
    mutationFn: async (request) => {
      const response = await apiClient.post(`/api/optimization/batch/process`, request);
      return response.data;
    },
    ...options,
  });
}

export function useUpdateOptimizationConfig(
  options?: UseMutationOptions<any, Error, Record<string, any>>
) {
  return useMutation<any, Error, Record<string, any>>({
    mutationFn: async (config) => {
      const response = await apiClient.put(`/api/optimization/config`, config);
      return response.data;
    },
    ...options,
  });
}
