/**
 * Admin Monitoring API Hooks
 *
 * React Query hooks for admin/monitoring endpoints (database, services, event processor)
 */

import { useQuery, useMutation, UseQueryOptions, UseMutationOptions, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client/axios";

// Database Monitoring Types
export interface EngineInfo {
  status: string;
  connection_count: number;
  last_health_check: string;
  performance_score: number;
}

export interface DatabaseHealth {
  status: string;
  engines: Record<string, EngineInfo>;
  timestamp: string;
  issues?: string[];
}

export interface DatabasePerformance {
  timestamp: string;
  query_throughput: number;
  avg_query_time_ms: number;
  cache_hit_rate: number;
  connection_pool_utilization: number;
}

export interface EngineStatus {
  engine_id: string;
  status: string;
  connection_count: number;
  last_check: string;
}

export interface DatabaseEnginesStatus {
  timestamp: string;
  total_engines: number;
  engines: EngineStatus[];
  active_connections: number;
  peak_connections: number;
}

export interface ConnectionPoolMetrics {
  pool_size: number;
  active_connections: number;
  idle_connections: number;
  wait_time_ms: number;
}

export interface ConnectionMetrics {
  timestamp: string;
  metrics: ConnectionPoolMetrics;
}

export interface PerformanceMetric {
  metric_name: string;
  value: number;
  unit: string;
  status: "healthy" | "warning" | "critical";
}

export interface DatabaseDashboard {
  timestamp: string;
  dashboard_info: {
    database_type: string;
    version: string;
    uptime_seconds: number;
  };
  health_status: DatabaseHealth;
  performance_metrics: PerformanceMetric[];
  recommendations: string[];
  engines_summary: {
    total_engines: number;
    healthy_engines: number;
    warning_engines: number;
    error_engines: number;
  };
}

// Service Monitoring Types
export interface ServiceMetrics {
  service_type: string;
  instances_created: number;
  cache_hits: number;
  cache_misses: number;
  avg_creation_time_ms: number;
}

export interface CacheEntry {
  key: string;
  created_at: string;
  last_accessed: string;
  access_count: number;
}

export interface ServiceFactoryStats {
  factory_id: string;
  cache_ttl_seconds: number;
  total_cache_entries: number;
  service_metrics: ServiceMetrics[];
  cache_entries: CacheEntry[];
  timestamp: string;
}

export interface ServicePerformance {
  service_type: string;
  hit_rate: number;
  avg_response_time_ms: number;
  total_requests: number;
}

export interface ServiceFactoryPerformance {
  overall_cache_hit_rate_percent: number;
  total_services_created: number;
  best_performing_service?: ServicePerformance;
  worst_performing_service?: ServicePerformance;
}

export interface HealthMetric {
  metric_name: string;
  value: number;
  status: "healthy" | "degraded" | "unhealthy";
}

export interface ServiceFactoryHealth {
  status: string;
  issues: string[];
  cache_size: number;
  metrics: HealthMetric[];
}

export interface TopService {
  service_type: string;
  request_count: number;
  cache_hit_rate: number;
  avg_response_time_ms: number;
}

export interface ServiceFactoryDashboard {
  factory_info: {
    factory_id: string;
    cache_ttl_seconds: number;
    total_cache_entries: number;
  };
  performance: {
    overall_hit_rate_percent: number;
    total_services_created: number;
    total_requests: number;
  };
  health: {
    status: string;
    issues: string[];
    cache_size: number;
  };
  top_services: TopService[];
  generated_at: string;
}

// Query Keys
export const adminKeys = {
  all: ["admin"] as const,
  database: {
    all: ["admin", "database"] as const,
    health: () => [...adminKeys.database.all, "health"] as const,
    performance: () => [...adminKeys.database.all, "performance"] as const,
    engines: () => [...adminKeys.database.all, "engines"] as const,
    metrics: () => [...adminKeys.database.all, "metrics"] as const,
    recommendations: () => [...adminKeys.database.all, "recommendations"] as const,
    environment: () => [...adminKeys.database.all, "environment"] as const,
    dashboard: () => [...adminKeys.database.all, "dashboard"] as const,
  },
  services: {
    all: ["admin", "services"] as const,
    stats: () => [...adminKeys.services.all, "stats"] as const,
    performance: () => [...adminKeys.services.all, "performance"] as const,
    health: () => [...adminKeys.services.all, "health"] as const,
    dashboard: () => [...adminKeys.services.all, "dashboard"] as const,
    metrics: (serviceType: string) =>
      [...adminKeys.services.all, "metrics", serviceType] as const,
  },
};

// Database Monitoring Hooks

export function useDatabaseHealth(options?: UseQueryOptions<DatabaseHealth>) {
  return useQuery<DatabaseHealth>({
    queryKey: adminKeys.database.health(),
    queryFn: async () => {
      const response = await apiClient.get(`/admin/database/health`);
      return response.data;
    },
    ...options,
  });
}

export function useDatabasePerformance(options?: UseQueryOptions<DatabasePerformance>) {
  return useQuery<DatabasePerformance>({
    queryKey: adminKeys.database.performance(),
    queryFn: async () => {
      const response = await apiClient.get(`/admin/database/performance`);
      return response.data;
    },
    ...options,
  });
}

export function useDatabaseEngines(options?: UseQueryOptions<DatabaseEnginesStatus>) {
  return useQuery<DatabaseEnginesStatus>({
    queryKey: adminKeys.database.engines(),
    queryFn: async () => {
      const response = await apiClient.get(`/admin/database/engines`);
      return response.data;
    },
    ...options,
  });
}

export function useConnectionMetrics(options?: UseQueryOptions<ConnectionMetrics>) {
  return useQuery<ConnectionMetrics>({
    queryKey: adminKeys.database.metrics(),
    queryFn: async () => {
      const response = await apiClient.get(`/admin/database/metrics`);
      return response.data;
    },
    ...options,
  });
}

export interface DatabaseRecommendation {
  category: string;
  priority: "high" | "medium" | "low";
  title: string;
  description: string;
  estimated_impact: string;
}

export interface DatabaseRecommendations {
  recommendations: DatabaseRecommendation[];
  generated_at: string;
}

export interface DatabaseEnvironment {
  database_type: string;
  version: string;
  python_version: string;
  os_info: string;
  available_extensions: string[];
}

export function useDatabaseRecommendations(options?: UseQueryOptions<DatabaseRecommendations>) {
  return useQuery<DatabaseRecommendations>({
    queryKey: adminKeys.database.recommendations(),
    queryFn: async () => {
      const response = await apiClient.get(`/admin/database/recommendations`);
      return response.data;
    },
    ...options,
  });
}

export function useDatabaseEnvironment(options?: UseQueryOptions<DatabaseEnvironment>) {
  return useQuery<DatabaseEnvironment>({
    queryKey: adminKeys.database.environment(),
    queryFn: async () => {
      const response = await apiClient.get(`/admin/database/environment`);
      return response.data;
    },
    ...options,
  });
}

export function useDatabaseDashboard(options?: UseQueryOptions<DatabaseDashboard>) {
  return useQuery<DatabaseDashboard>({
    queryKey: adminKeys.database.dashboard(),
    queryFn: async () => {
      const response = await apiClient.get(`/admin/database/dashboard`);
      return response.data;
    },
    ...options,
  });
}

// Database Mutation Hooks

export function useOptimizeDatabase(
  options?: UseMutationOptions<MutationResponse, Error, string>
) {
  const queryClient = useQueryClient();

  return useMutation<MutationResponse, Error, string>({
    mutationFn: async (workloadType: string) => {
      const response = await apiClient.post(`/admin/database/optimize`, null, {
        params: { workload_type: workloadType },
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.database.all });
    },
    ...options,
  });
}

export function useResetDatabaseMetrics(
  options?: UseMutationOptions<MutationResponse, Error, void>
) {
  const queryClient = useQueryClient();

  return useMutation<MutationResponse, Error, void>({
    mutationFn: async () => {
      const response = await apiClient.post(`/admin/database/reset-metrics`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.database.metrics() });
    },
    ...options,
  });
}

export function useCreateDatabaseEngine(
  options?: UseMutationOptions<MutationResponse, Error, { engine_id: string; database_url?: string }>
) {
  const queryClient = useQueryClient();

  return useMutation<MutationResponse, Error, { engine_id: string; database_url?: string }>({
    mutationFn: async ({ engine_id, database_url }) => {
      const response = await apiClient.post(`/admin/database/create-engine`, null, {
        params: { engine_id, database_url },
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.database.engines() });
    },
    ...options,
  });
}

export function useCleanupDatabaseResources(
  options?: UseMutationOptions<MutationResponse, Error, void>
) {
  const queryClient = useQueryClient();

  return useMutation<MutationResponse, Error, void>({
    mutationFn: async () => {
      const response = await apiClient.delete(`/admin/database/cleanup`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.database.all });
    },
    ...options,
  });
}

// Service Factory Monitoring Hooks

export function useServiceFactoryStats(options?: UseQueryOptions<ServiceFactoryStats>) {
  return useQuery<ServiceFactoryStats>({
    queryKey: adminKeys.services.stats(),
    queryFn: async () => {
      const response = await apiClient.get(`/admin/services/stats`);
      return response.data;
    },
    ...options,
  });
}

export function useServiceFactoryPerformance(
  options?: UseQueryOptions<ServiceFactoryPerformance>
) {
  return useQuery<ServiceFactoryPerformance>({
    queryKey: adminKeys.services.performance(),
    queryFn: async () => {
      const response = await apiClient.get(`/admin/services/performance`);
      return response.data;
    },
    ...options,
  });
}

export function useServiceFactoryHealth(options?: UseQueryOptions<ServiceFactoryHealth>) {
  return useQuery<ServiceFactoryHealth>({
    queryKey: adminKeys.services.health(),
    queryFn: async () => {
      const response = await apiClient.get(`/admin/services/health`);
      return response.data;
    },
    ...options,
  });
}

export function useServiceFactoryDashboard(
  options?: UseQueryOptions<ServiceFactoryDashboard>
) {
  return useQuery<ServiceFactoryDashboard>({
    queryKey: adminKeys.services.dashboard(),
    queryFn: async () => {
      const response = await apiClient.get(`/admin/services/dashboard`);
      return response.data;
    },
    ...options,
  });
}

export interface ServiceTypeMetrics {
  service_type: string;
  total_instances: number;
  cache_hits: number;
  cache_misses: number;
  hit_rate_percent: number;
  avg_creation_time_ms: number;
  recent_requests: number;
  timestamp: string;
}

export function useServiceTypeMetrics(
  serviceType: string,
  options?: UseQueryOptions<ServiceTypeMetrics>
) {
  return useQuery<ServiceTypeMetrics>({
    queryKey: adminKeys.services.metrics(serviceType),
    queryFn: async () => {
      const response = await apiClient.get(`/admin/services/metrics/${serviceType}`);
      return response.data;
    },
    enabled: !!serviceType,
    ...options,
  });
}

// Mutation Response Types
export interface MutationResponse {
  success: boolean;
  message: string;
  timestamp: string;
}

// Service Factory Mutation Hooks

export function useClearServiceCache(options?: UseMutationOptions<MutationResponse, Error, void>) {
  const queryClient = useQueryClient();

  return useMutation<MutationResponse, Error, void>({
    mutationFn: async () => {
      const response = await apiClient.post(`/admin/services/cache/clear`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.services.all });
    },
    ...options,
  });
}

export function useCleanupServiceCache(options?: UseMutationOptions<MutationResponse, Error, void>) {
  const queryClient = useQueryClient();

  return useMutation<MutationResponse, Error, void>({
    mutationFn: async () => {
      const response = await apiClient.post(`/admin/services/cache/cleanup`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.services.all });
    },
    ...options,
  });
}
