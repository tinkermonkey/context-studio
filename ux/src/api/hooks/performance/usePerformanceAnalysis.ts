/**
 * Performance Analysis API Hooks
 *
 * React Query hooks for performance monitoring and tuning endpoints
 */

import {
  useQuery,
  useMutation,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
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

export interface DatabaseMetrics {
  connection_pool_size: number;
  active_connections: number;
  idle_connections: number;
  wait_time_ms: number;
}

export interface S3Metrics {
  objects_stored: number;
  total_size_bytes: number;
  average_object_size_bytes: number;
  requests_per_hour: number;
}

export interface QueryMetrics {
  queries_executed: number;
  avg_execution_time_ms: number;
  slow_queries_count: number;
  cache_hit_rate: number;
}

export interface SystemMetrics {
  cpu_usage_percent: number;
  memory_usage_percent: number;
  disk_usage_percent: number;
  uptime_seconds: number;
}

export interface CacheMetrics {
  cache_size: number;
  hit_rate: number;
  miss_rate: number;
  eviction_count: number;
}

export interface BatchMetrics {
  batches_processed: number;
  avg_batch_size: number;
  avg_processing_time_ms: number;
  failure_rate: number;
}

export interface PerformanceMetrics {
  timestamp: string;
  database_metrics: DatabaseMetrics;
  s3_metrics: S3Metrics;
  query_metrics: QueryMetrics;
  system_metrics: SystemMetrics;
  cache_metrics: CacheMetrics;
  batch_metrics: BatchMetrics;
}

export interface PerformanceTrend {
  timestamp: string;
  metric_name: string;
  value: number;
  trend_direction: "up" | "down" | "stable";
}

export interface PerformanceIssue {
  severity: "critical" | "warning" | "info";
  component: string;
  message: string;
  detected_at: string;
}

export interface PerformanceRecommendation {
  priority: "high" | "medium" | "low";
  category: string;
  title: string;
  description: string;
  estimated_impact: string;
}

export interface PerformanceTrends {
  analysis_window_hours: number;
  trends: PerformanceTrend[];
  issues: PerformanceIssue[];
  recommendations: PerformanceRecommendation[];
  overall_health_score: number;
  performance_grade: string;
}

export interface CacheStatistics {
  total_entries: number;
  hit_rate: number;
  miss_rate: number;
  eviction_count: number;
}

export interface QueryStats {
  total_queries: number;
  avg_execution_time_ms: number;
  cache_stats: CacheStatistics;
  materialized_views_count: number;
}

export interface QueryTuningMetrics {
  execution_time_before_ms: number;
  execution_time_after_ms: number;
  improvement_percent: number;
  rows_scanned_before: number;
  rows_scanned_after: number;
}

export interface QueryTuningResult {
  original_query: string;
  tuned_query: string;
  metrics: QueryTuningMetrics;
  techniques_applied: string[];
}

export interface CompressionAlgorithmStats {
  algorithm: string;
  files_compressed: number;
  total_savings_bytes: number;
  avg_compression_ratio: number;
}

export interface StorageStats {
  optimization_summary: {
    files_optimized: number;
    total_savings_bytes: number;
    average_compression_ratio: number;
  };
  compression_algorithms_used: CompressionAlgorithmStats[];
  total_optimizations: number;
}

export interface StorageAction {
  action_type: string;
  object_key: string;
  size_before_bytes: number;
  size_after_bytes: number;
  savings_bytes: number;
}

export interface StorageCompressionResult {
  optimization_actions: StorageAction[];
  storage_saved_bytes: number;
  cost_reduction_estimate: number;
  objects_optimized: number;
}

export interface DiffConflict {
  path: string;
  conflict_type: string;
   
  base_value: any;
   
  local_value: any;
   
  remote_value: any;
}

export interface ThreeWayDiff {
  diff_result: {
    added: string[];
    removed: string[];
    modified: string[];
    conflicts: string[];
  };
  conflicts_detected: DiffConflict[];
  semantic_insights?: {
    confidence_score: number;
    suggested_resolution: string;
  };
  merge_recommendation?: string;
}

export interface BatchOperationError {
  item_index: number;
  error_message: string;
   
  item_data: any;
}

export interface BatchOperationResult {
  operation_id: string;
  total_items: number;
  successful_items: number;
  failed_items: number;
  processing_time_seconds: number;
  throughput_per_second: number;
  errors: BatchOperationError[];
}

// Request Types
export interface QueryTuningRequest {
  query: string;
  context?: {
     
    table_schemas?: Record<string, any>;
    expected_result_size?: number;
  };
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
  options?: {
    parallel_processing?: boolean;
    batch_size?: number;
    continue_on_error?: boolean;
  };
}

export interface PerformanceConfig {
  auto_tune_enabled: boolean;
  cache_size_mb: number;
  query_timeout_seconds: number;
  batch_size: number;
  compression_enabled: boolean;
  monitoring_interval_seconds: number;
}

export interface DashboardData {
  system_health: SystemHealth;
  performance_metrics: PerformanceMetrics;
  query_stats: QueryStats;
  storage_stats: StorageStats;
}

export interface DiffStats {
  total_diffs_processed: number;
  conflicts_resolved: number;
  conflicts_pending: number;
  avg_processing_time_ms: number;
}

export interface BatchStats {
  total_batches_processed: number;
  avg_batch_size: number;
  avg_processing_time_seconds: number;
  success_rate: number;
  total_items_processed: number;
}

// Query Keys
export const performanceKeys = {
  all: ["performance"] as const,
  health: () => [...performanceKeys.all, "health"] as const,
  dashboard: () => [...performanceKeys.all, "dashboard"] as const,
  metrics: () => [...performanceKeys.all, "metrics"] as const,
  trends: (windowHours: number) =>
    [...performanceKeys.all, "trends", windowHours] as const,
  queryStats: () => [...performanceKeys.all, "query", "stats"] as const,
  storageStats: () => [...performanceKeys.all, "storage", "stats"] as const,
  diffStats: () => [...performanceKeys.all, "diff", "stats"] as const,
  batchStats: () => [...performanceKeys.all, "batch", "stats"] as const,
  config: () => [...performanceKeys.all, "config"] as const,
};

// Query Hooks

export function useSystemHealth(options?: UseQueryOptions<SystemHealth>) {
  return useQuery<SystemHealth>({
    queryKey: performanceKeys.health(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/health`);
      return response.data;
    },
    ...options,
  });
}

export function usePerformanceDashboard(
  options?: UseQueryOptions<DashboardData>,
) {
  return useQuery<DashboardData>({
    queryKey: performanceKeys.dashboard(),
    queryFn: async () => {
      const response = await apiClient.get(
        `/api/optimization/performance/dashboard`,
      );
      return response.data;
    },
    ...options,
  });
}

export function usePerformanceMetrics(
  options?: UseQueryOptions<PerformanceMetrics>,
) {
  return useQuery<PerformanceMetrics>({
    queryKey: performanceKeys.metrics(),
    queryFn: async () => {
      const response = await apiClient.get(
        `/api/optimization/performance/metrics`,
      );
      return response.data;
    },
    ...options,
  });
}

export function usePerformanceTrends(
  windowHours: number = 24,
  options?: UseQueryOptions<PerformanceTrends>,
) {
  return useQuery<PerformanceTrends>({
    queryKey: performanceKeys.trends(windowHours),
    queryFn: async () => {
      const response = await apiClient.get(
        `/api/optimization/performance/trends`,
        {
          params: { window_hours: windowHours },
        },
      );
      return response.data;
    },
    ...options,
  });
}

export function useQueryStats(options?: UseQueryOptions<QueryStats>) {
  return useQuery<QueryStats>({
    queryKey: performanceKeys.queryStats(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/query/stats`);
      return response.data;
    },
    ...options,
  });
}

export function useStorageStats(options?: UseQueryOptions<StorageStats>) {
  return useQuery<StorageStats>({
    queryKey: performanceKeys.storageStats(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/storage/stats`);
      return response.data;
    },
    ...options,
  });
}

export function useDiffStats(options?: UseQueryOptions<DiffStats>) {
  return useQuery<DiffStats>({
    queryKey: performanceKeys.diffStats(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/diff/stats`);
      return response.data;
    },
    ...options,
  });
}

export function useBatchStats(options?: UseQueryOptions<BatchStats>) {
  return useQuery<BatchStats>({
    queryKey: performanceKeys.batchStats(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/batch/stats`);
      return response.data;
    },
    ...options,
  });
}

export function usePerformanceConfig(
  options?: UseQueryOptions<PerformanceConfig>,
) {
  return useQuery<PerformanceConfig>({
    queryKey: performanceKeys.config(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/optimization/config`);
      return response.data;
    },
    ...options,
  });
}

// Mutation Hooks

export function useAutoTunePerformance(
   
  options?: UseMutationOptions<any, Error, void>,
) {
   
  return useMutation<any, Error, void>({
    mutationFn: async () => {
      const response = await apiClient.post(
        `/api/optimization/performance/auto-optimize`,
      );
      return response.data;
    },
    ...options,
  });
}

export function useTuneQuery(
  options?: UseMutationOptions<QueryTuningResult, Error, QueryTuningRequest>,
) {
  return useMutation<QueryTuningResult, Error, QueryTuningRequest>({
    mutationFn: async (request) => {
      const response = await apiClient.post(
        `/api/optimization/query/optimize`,
        request,
      );
      return response.data;
    },
    ...options,
  });
}
export function useCreateMaterializedView(
   
  options?: UseMutationOptions<any, Error, MaterializedViewRequest>,
) {
   
  return useMutation<any, Error, MaterializedViewRequest>({
    mutationFn: async (request) => {
      const response = await apiClient.post(
        `/api/optimization/query/materialized-view`,
        request,
      );
      return response.data;
    },
    ...options,
  });
}

export function useCompressStorage(
  options?: UseMutationOptions<StorageCompressionResult, Error, void>,
) {
  return useMutation<StorageCompressionResult, Error, void>({
    mutationFn: async () => {
      const response = await apiClient.post(
        `/api/optimization/storage/optimize`,
      );
      return response.data;
    },
    ...options,
  });
}
export function useSetupLifecyclePolicies(
   
  options?: UseMutationOptions<any, Error, void>,
) {
   
  return useMutation<any, Error, void>({
    mutationFn: async () => {
      const response = await apiClient.post(
        `/api/optimization/storage/lifecycle-policies`,
      );
      return response.data;
    },
    ...options,
  });
}

export function useThreeWayDiff(
  options?: UseMutationOptions<ThreeWayDiff, Error, ThreeWayDiffRequest>,
) {
  return useMutation<ThreeWayDiff, Error, ThreeWayDiffRequest>({
    mutationFn: async (request) => {
      const response = await apiClient.post(
        `/api/optimization/diff/three-way`,
        request,
      );
      return response.data;
    },
    ...options,
  });
}

export function useBatchOperation(
  options?: UseMutationOptions<
    BatchOperationResult,
    Error,
    BatchOperationRequest
  >,
) {
  return useMutation<BatchOperationResult, Error, BatchOperationRequest>({
    mutationFn: async (request) => {
      const response = await apiClient.post(
        `/api/optimization/batch/process`,
        request,
      );
      return response.data;
    },
    ...options,
  });
}

export function useUpdatePerformanceConfig(
   
  options?: UseMutationOptions<any, Error, PerformanceConfig>,
) {
   
  return useMutation<any, Error, PerformanceConfig>({
    mutationFn: async (config) => {
      const response = await apiClient.put(`/api/optimization/config`, config);
      return response.data;
    },
    ...options,
  });
}
