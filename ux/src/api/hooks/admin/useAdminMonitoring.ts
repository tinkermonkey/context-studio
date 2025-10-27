/**
 * Admin Monitoring API Hooks
 *
 * React Query hooks for admin/monitoring endpoints (database, services, event processor)
 */

import { useQuery, useMutation, UseQueryOptions, UseMutationOptions, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";

// Database Monitoring Types
export interface DatabaseHealth {
  status: string;
  engines: Record<string, any>;
  timestamp: string;
  issues?: string[];
}

export interface DatabasePerformance {
  timestamp: string;
  [key: string]: any;
}

export interface DatabaseEnginesStatus {
  timestamp: string;
  total_engines: number;
  engines: Record<string, any>;
  active_connections: number;
  peak_connections: number;
}

export interface ConnectionMetrics {
  timestamp: string;
  metrics: Record<string, any>;
}

export interface DatabaseDashboard {
  timestamp: string;
  dashboard_info: Record<string, any>;
  health_status: DatabaseHealth;
  performance_metrics: Record<string, any>;
  recommendations: string[];
  engines_summary: {
    total_engines: number;
    healthy_engines: number;
    warning_engines: number;
    error_engines: number;
  };
}

// Service Monitoring Types
export interface ServiceFactoryStats {
  factory_id: string;
  cache_ttl_seconds: number;
  total_cache_entries: number;
  service_metrics: Record<string, any>;
  cache_entries: Record<string, any>;
  timestamp: string;
}

export interface ServiceFactoryPerformance {
  overall_cache_hit_rate_percent: number;
  total_services_created: number;
  best_performing_service?: Record<string, any>;
  worst_performing_service?: Record<string, any>;
}

export interface ServiceFactoryHealth {
  status: string;
  issues: string[];
  cache_size: number;
  metrics: Record<string, any>;
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
  top_services: Record<string, any>;
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

export function useDatabaseRecommendations(options?: UseQueryOptions<any>) {
  return useQuery<any>({
    queryKey: adminKeys.database.recommendations(),
    queryFn: async () => {
      const response = await apiClient.get(`/admin/database/recommendations`);
      return response.data;
    },
    ...options,
  });
}

export function useDatabaseEnvironment(options?: UseQueryOptions<any>) {
  return useQuery<any>({
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
  options?: UseMutationOptions<any, Error, string>
) {
  const queryClient = useQueryClient();

  return useMutation<any, Error, string>({
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
  options?: UseMutationOptions<any, Error, void>
) {
  const queryClient = useQueryClient();

  return useMutation<any, Error, void>({
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
  options?: UseMutationOptions<any, Error, { engine_id: string; database_url?: string }>
) {
  const queryClient = useQueryClient();

  return useMutation<any, Error, { engine_id: string; database_url?: string }>({
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
  options?: UseMutationOptions<any, Error, void>
) {
  const queryClient = useQueryClient();

  return useMutation<any, Error, void>({
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

export function useServiceTypeMetrics(
  serviceType: string,
  options?: UseQueryOptions<any>
) {
  return useQuery<any>({
    queryKey: adminKeys.services.metrics(serviceType),
    queryFn: async () => {
      const response = await apiClient.get(`/admin/services/metrics/${serviceType}`);
      return response.data;
    },
    enabled: !!serviceType,
    ...options,
  });
}

// Service Factory Mutation Hooks

export function useClearServiceCache(options?: UseMutationOptions<any, Error, void>) {
  const queryClient = useQueryClient();

  return useMutation<any, Error, void>({
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

export function useCleanupServiceCache(options?: UseMutationOptions<any, Error, void>) {
  const queryClient = useQueryClient();

  return useMutation<any, Error, void>({
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
