/**
 * Analytics API Hooks
 *
 * React Query hooks for analytics endpoints
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import { apiClient } from "@/api/client/axios";

// API Response Types
export interface ChangeSummary {
  total_changes: number;
  entities_modified: number;
  active_users: number;
  changesets: number;
  period_start?: string;
  period_end?: string;
}

export interface UserActivity {
  author_id: string;
  total_changes: number;
  total_entities: number;
  active_days: number;
  avg_changes_per_day: number;
  max_changes_per_day: number;
}

export interface EntityHotspot {
  entity_type: string;
  entity_id: string;
  total_modifications: number;
  unique_authors: number;
  lifespan_days: number;
  modification_rate: number;
}

export interface CollaborationMetrics {
  proposal_authors: number;
  voters: number;
  total_votes: number;
  avg_response_time_hours: number;
  approval_rate: number;
}

export interface ImpactByType {
  entity_type: string;
  count: number;
  operation: string;
}

export interface ChangeImpact {
  changeset_id: string;
  total_entities: number;
  entity_types_affected?: number;
  affected_entity_types?: string[];
  entities_created?: number;
  entities_updated?: number;
  entities_deleted?: number;
  impact_by_type: ImpactByType[];
}

export interface DailyTrend {
  date: string;
  changes: number;
  active_users: number;
  entities_modified: number;
}

export interface PeakHour {
  hour: number;
  avg_changes: number;
  peak_day: string;
}

export interface TrendAnalysis {
  daily_trends: DailyTrend[];
  peak_hours: PeakHour[];
  analysis_period_days: number;
}

export interface SyncPerformance {
  avg_sync_time_ms: number;
  total_syncs: number;
  failed_syncs: number;
  success_rate: number;
}

export interface SystemLoad {
  timestamp: string;
  cpu_percent: number;
  memory_percent: number;
  active_queries: number;
}

export interface PerformanceMetrics {
  sync_performance: SyncPerformance;
  system_load: SystemLoad[];
}

export interface CollaborationNetwork {
  user_id: string;
  connections: string[];
  collaboration_score: number;
}

export interface TeamProductivity {
  team_id: string;
  total_changes: number;
  avg_response_time_hours: number;
  productivity_score: number;
}

export interface CollaborationInsights {
  collaboration_networks: CollaborationNetwork[];
  team_productivity: TeamProductivity[];
  analysis_period_days: number;
}

export interface TopEntity {
  entity_id: string;
  entity_type: string;
  modification_count: number;
  unique_contributors: number;
}

export interface ExecutiveSummary {
  summary_period_days: number;
  key_metrics: {
    total_changes: number;
    active_users: number;
    avg_daily_changes: number;
    system_uptime_percent: number;
  };
  collaboration_health: {
    collaboration_score: number;
    avg_response_time_hours: number;
    approval_rate: number;
  };
  system_health: {
    health_score: number;
    performance_grade: string;
    issues_count: number;
  };
  top_entities: TopEntity[];
  generated_at: string;
}

export interface ConflictMetrics {
  total_conflicts: number;
  resolved_conflicts: number;
  pending_conflicts: number;
  avg_resolution_time_hours: number;
  conflict_rate: number;
  conflicts_by_type: {
    type: string;
    count: number;
  }[];
}

export interface AnalyticsHealth {
  status: string;
  duckdb_available: boolean;
  s3_configured: boolean;
  active_views: number;
  data_freshness_hours?: number;
  query_performance_ms?: number;
  system_version: string;
}

export interface DashboardMetrics {
  timestamp: string;
  refresh_interval: number;
  metrics: {
    changes_today: number;
    active_users_week: number;
    unresolved_conflicts: number;
    avg_sync_time: number;
    system_status: string;
  };
}

// Query Keys
export const analyticsKeys = {
  all: ["analytics"] as const,
  summary: (days: number) => [...analyticsKeys.all, "summary", days] as const,
  userActivity: (params?: { user_id?: string; days?: number; limit?: number }) =>
    [...analyticsKeys.all, "user-activity", params] as const,
  entityHotspots: (limit: number) =>
    [...analyticsKeys.all, "entity-hotspots", limit] as const,
  collaborationMetrics: (days: number) =>
    [...analyticsKeys.all, "collaboration-metrics", days] as const,
  changeImpact: (changesetId: string) =>
    [...analyticsKeys.all, "change-impact", changesetId] as const,
  trends: (days: number) => [...analyticsKeys.all, "trends", days] as const,
  performance: () => [...analyticsKeys.all, "performance"] as const,
  collaborationInsights: (days: number) =>
    [...analyticsKeys.all, "collaboration-insights", days] as const,
  executiveSummary: (days: number) =>
    [...analyticsKeys.all, "executive-summary", days] as const,
  conflictMetrics: () => [...analyticsKeys.all, "conflict-metrics"] as const,
  health: () => [...analyticsKeys.all, "health"] as const,
  dashboardMetrics: (refreshInterval: number) =>
    [...analyticsKeys.all, "dashboard", "metrics", refreshInterval] as const,
};

// Hooks

export function useChangeSummary(
  days: number = 30,
  options?: UseQueryOptions<ChangeSummary>
) {
  return useQuery<ChangeSummary>({
    queryKey: analyticsKeys.summary(days),
    queryFn: async () => {
      const response = await apiClient.get(`/api/analytics/summary`, {
        params: { days },
      });
      return response.data;
    },
    ...options,
  });
}

export function useUserActivity(
  params?: { user_id?: string; days?: number; limit?: number },
  options?: UseQueryOptions<UserActivity[]>
) {
  return useQuery<UserActivity[]>({
    queryKey: analyticsKeys.userActivity(params),
    queryFn: async () => {
      const response = await apiClient.get(`/api/analytics/user-activity`, {
        params,
      });
      return response.data;
    },
    ...options,
  });
}

export function useEntityHotspots(
  limit: number = 50,
  options?: UseQueryOptions<EntityHotspot[]>
) {
  return useQuery<EntityHotspot[]>({
    queryKey: analyticsKeys.entityHotspots(limit),
    queryFn: async () => {
      const response = await apiClient.get(`/api/analytics/entity-hotspots`, {
        params: { limit },
      });
      return response.data;
    },
    ...options,
  });
}

export function useCollaborationMetrics(
  days: number = 60,
  options?: UseQueryOptions<CollaborationMetrics>
) {
  return useQuery<CollaborationMetrics>({
    queryKey: analyticsKeys.collaborationMetrics(days),
    queryFn: async () => {
      const response = await apiClient.get(
        `/api/analytics/collaboration-metrics`,
        {
          params: { days },
        }
      );
      return response.data;
    },
    ...options,
  });
}

export function useChangeImpact(
  changesetId: string,
  options?: UseQueryOptions<ChangeImpact>
) {
  return useQuery<ChangeImpact>({
    queryKey: analyticsKeys.changeImpact(changesetId),
    queryFn: async () => {
      const response = await apiClient.get(
        `/api/analytics/change-impact/${changesetId}`
      );
      return response.data;
    },
    enabled: !!changesetId,
    ...options,
  });
}

export function useTrends(
  days: number = 90,
  options?: UseQueryOptions<TrendAnalysis>
) {
  return useQuery<TrendAnalysis>({
    queryKey: analyticsKeys.trends(days),
    queryFn: async () => {
      const response = await apiClient.get(`/api/analytics/trends`, {
        params: { days },
      });
      return response.data;
    },
    ...options,
  });
}

export function usePerformanceMetrics(
  options?: UseQueryOptions<PerformanceMetrics>
) {
  return useQuery<PerformanceMetrics>({
    queryKey: analyticsKeys.performance(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/analytics/performance`);
      return response.data;
    },
    ...options,
  });
}

export function useCollaborationInsights(
  days: number = 60,
  options?: UseQueryOptions<CollaborationInsights>
) {
  return useQuery<CollaborationInsights>({
    queryKey: analyticsKeys.collaborationInsights(days),
    queryFn: async () => {
      const response = await apiClient.get(
        `/api/analytics/collaboration-insights`,
        {
          params: { days },
        }
      );
      return response.data;
    },
    ...options,
  });
}

export function useExecutiveSummary(
  days: number = 30,
  options?: UseQueryOptions<ExecutiveSummary>
) {
  return useQuery<ExecutiveSummary>({
    queryKey: analyticsKeys.executiveSummary(days),
    queryFn: async () => {
      const response = await apiClient.get(`/api/analytics/executive-summary`, {
        params: { days },
      });
      return response.data;
    },
    ...options,
  });
}

export function useConflictMetrics(
  options?: UseQueryOptions<ConflictMetrics>
) {
  return useQuery<ConflictMetrics>({
    queryKey: analyticsKeys.conflictMetrics(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/analytics/conflict-metrics`);
      return response.data;
    },
    ...options,
  });
}

export function useAnalyticsHealth(
  options?: UseQueryOptions<AnalyticsHealth>
) {
  return useQuery<AnalyticsHealth>({
    queryKey: analyticsKeys.health(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/analytics/health`);
      return response.data;
    },
    ...options,
  });
}

export function useDashboardMetrics(
  refreshInterval: number = 300,
  options?: UseQueryOptions<DashboardMetrics>
) {
  return useQuery<DashboardMetrics>({
    queryKey: analyticsKeys.dashboardMetrics(refreshInterval),
    queryFn: async () => {
      const response = await apiClient.get(`/api/analytics/dashboard/metrics`, {
        params: { refresh_interval: refreshInterval },
      });
      return response.data;
    },
    refetchInterval: refreshInterval * 1000, // Convert to milliseconds
    ...options,
  });
}

// CSV Export Helper
export async function exportAnalyticsCSV(
  reportType: "user-activity" | "hotspots" | "trends",
  days: number = 30
): Promise<Blob> {
  const response = await apiClient.get(
    `/api/analytics/export/csv/${reportType}`,
    {
      params: { days },
      responseType: "blob",
    }
  );
  return response.data;
}
