/**
 * LLM Traceability Types
 *
 * TypeScript interfaces for LLM traceability API requests and responses
 * Following patterns from existing API types and the traceability specification
 */

// Core traceability interfaces matching the API specification
export interface SelectionRecordRequest {
  execution_id: string;
  record_type: "structure_node";
  record_id: string;
  suggestion_field: string;
  selected_content: string;
}

export interface SelectionRecordResponse {
  success: boolean;
  message: string;
  selection_id?: string;
}

export interface AnalyticsFilters {
  pipeline_type?: string;
  days_back?: number;
  start_date?: string;
  end_date?: string;
}

export interface ExecutionAnalyticsData {
  total_executions: number;
  successful_executions: number;
  success_rate: number;
  avg_execution_time: number;
  total_tokens_used: number;
  total_selections: number;
  selection_rate: number;
}

export interface ExecutionAnalyticsResponse {
  success: boolean;
  data: ExecutionAnalyticsData;
  filters: {
    pipeline_type: string;
    days_back: number;
  };
}

export interface SelectionRecord {
  selection_id: string;
  record_type: string;
  record_id: string;
  suggestion_field: string;
  selected_content: string;
  timestamp: string;
}

export interface ExecutionDetails {
  execution_id: string;
  pipeline_type: string;
  status: "completed" | "failed" | "in_progress";
  execution_time: number;
  tokens_used: number;
  timestamp: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  error_details?: string;
  user_prompt?: string;
  response_message?: string;
}

export interface ExecutionHistoryData {
  execution: ExecutionDetails;
  selections: SelectionRecord[];
}

export interface ExecutionHistoryResponse {
  success: boolean;
  data: ExecutionHistoryData;
}

// New response models for flavor-specific endpoints
export interface ExecutionHistoryByFlavorResponse {
  executions: Array<Record<string, unknown>>;
  total_count: number;
  flavor_id: string;
}

export interface FlavorAnalyticsResponse {
  flavor_id: string;
  analytics: Record<string, unknown>;
  time_range_days: number;
}

export interface LLMTraceabilityHealthResponse {
  status: "healthy" | "degraded" | "unhealthy";
  database_connection: boolean;
  api_version: string;
  timestamp: string;
  uptime_seconds: number;
}

// Extended interfaces for UI components
export interface AnalyticsTimeRangeFilter {
  label: string;
  days: number;
}

export interface AnalyticsChartData {
  date: string;
  executions: number;
  selections: number;
  success_rate: number;
}

export interface ExecutionHistoryFilters {
  execution_id?: string;
  pipeline_type?: string;
  status?: ExecutionDetails["status"];
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
  /**
   * Required flavor_id for execution history queries
   * The current API requires this parameter
   */
  flavor_id?: string;
}

// New filter types for flavor-specific queries
export interface FlavorExecutionHistoryFilters {
  flavor_id: string;
  limit?: number;
}

export interface FlavorAnalyticsFilters {
  flavor_id: string;
  days_back?: number;
}

// Error interfaces following existing patterns
export interface TraceabilityError {
  success: false;
  error: string;
  error_type: string;
  details?: string;
}

// Selection tracking context interface
export interface SelectionTrackingContext {
  executionId: string;
  recordId: string;
  suggestionField: string;
  onSelectionRecorded?: (selectionId?: string) => void;
  onError?: (error: Error) => void;
}

// Analytics dashboard configuration
export interface AnalyticsDashboardConfig {
  autoRefresh?: boolean;
  refreshInterval?: number; // milliseconds
  defaultTimeRange?: number; // days
  showExportButton?: boolean;
}

// Execution history viewer configuration
export interface ExecutionHistoryConfig {
  maxEntries?: number;
  autoRefresh?: boolean;
  refreshInterval?: number; // milliseconds
  showFilters?: boolean;
}
