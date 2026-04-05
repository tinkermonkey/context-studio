/**
 * LLM Traceability Service
 *
 * Service for tracking LLM suggestion usage, analytics, and execution history
 * Extends BaseService for consistent error handling and API patterns
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type {
  SelectionRecordRequest,
  SelectionRecordResponse,
  AnalyticsFilters,
  ExecutionAnalyticsResponse,
  ExecutionHistoryResponse,
  LLMTraceabilityHealthResponse,
  ExecutionHistoryFilters,
  ExecutionHistoryByFlavorResponse,
  FlavorAnalyticsResponse,
  FlavorExecutionHistoryFilters,
  FlavorAnalyticsFilters,
} from "../types/traceability";

export class LLMTraceabilityService extends BaseService {
  /**
   * Record a user selection of an AI suggestion
   * This is async and should never block user workflows
   * @param request The selection record request
   * @returns Selection record response with confirmation
   */
  async recordSelection(
    request: SelectionRecordRequest,
  ): Promise<SelectionRecordResponse> {
    this.validateRequired(request.execution_id, "execution_id");
    this.validateRequired(request.record_id, "record_id");
    this.validateRequired(request.suggestion_field, "suggestion_field");
    this.validateRequired(request.selected_content, "selected_content");

    const sanitizedRequest = {
      ...request,
      execution_id: this.sanitizeString(request.execution_id, "execution_id"),
      record_id: this.sanitizeString(request.record_id, "record_id"),
      suggestion_field: this.sanitizeString(
        request.suggestion_field,
        "suggestion_field",
      ),
      selected_content: this.sanitizeString(
        request.selected_content,
        "selected_content",
        5000,
      ), // Limit content to 5k chars
    };

    return this.withErrorContext(
      () =>
        this.postResource<SelectionRecordResponse>(
          ENDPOINTS.LLM_TRACEABILITY.RECORD_SELECTION,
          sanitizedRequest,
        ),
      "recording selection",
    );
  }

  /**
   * Get execution analytics with optional filtering
   * @param filters Optional filters for analytics query
   * @returns Analytics data with success rates, usage trends, and performance metrics
   */
  async getExecutionAnalytics(
    filters?: AnalyticsFilters,
  ): Promise<ExecutionAnalyticsResponse> {
    const sanitizedFilters = filters
      ? {
          ...filters,
          pipeline_type: filters.pipeline_type
            ? this.sanitizeString(
                String(filters.pipeline_type),
                "pipeline_type",
              )
            : undefined,
          days_back:
            filters.days_back && filters.days_back > 0
              ? Math.min(filters.days_back, 365)
              : undefined,
          start_date: filters.start_date
            ? this.sanitizeString(
                String(filters.start_date),
                "start_date",
              )
            : undefined,
          end_date: filters.end_date
            ? this.sanitizeString(
                String(filters.end_date),
                "end_date",
              )
            : undefined,
        }
      : undefined;

    return this.withErrorContext(
      () =>
        this.getResource<ExecutionAnalyticsResponse>(
          ENDPOINTS.LLM_TRACEABILITY.EXECUTION_ANALYTICS,
          sanitizedFilters,
        ),
      "fetching execution analytics",
    );
  }

  /**
   * Get detailed execution history for a specific execution
   * @param executionId The execution ID to get history for
   * @returns Detailed execution information and selection history
   */
  async getExecutionHistory(
    executionId: string,
  ): Promise<ExecutionHistoryResponse> {
    this.validateRequired(executionId, "executionId");
    const sanitizedId = this.sanitizeString(executionId, "executionId");

    return this.withErrorContext(
      () =>
        this.getResource<ExecutionHistoryResponse>(
          `${ENDPOINTS.LLM_TRACEABILITY.EXECUTION_DETAILS}/${sanitizedId}`,
        ),
      "fetching execution history",
    );
  }

  /**
   * Get multiple execution histories with filtering and pagination
   * NOTE: This endpoint requires a flavor_id parameter - use getFlavorExecutionHistory instead
   * @param filters Optional filters for execution history query - must include flavor_id
   * @returns Array of execution histories matching the filters
   * @deprecated Use getFlavorExecutionHistory for flavor-specific execution history
   */
  async getExecutionHistories(
    filters?: ExecutionHistoryFilters,
  ): Promise<ExecutionHistoryResponse[]> {
    // The current API endpoint requires flavor_id, so we cannot support general execution history
    if (!filters || !filters.flavor_id) {
      throw new Error(
        "General execution history is not supported by the current API. Use getFlavorExecutionHistory with a specific flavor_id instead.",
      );
    }

    const sanitizedFilters = {
      ...filters,
      execution_id: filters.execution_id
        ? this.sanitizeString(
            String(filters.execution_id),
            "execution_id",
          )
        : undefined,
      pipeline_type: filters.pipeline_type
        ? this.sanitizeString(
            String(filters.pipeline_type),
            "pipeline_type",
          )
        : undefined,
      status: filters.status,
      start_date: filters.start_date
        ? this.sanitizeString(
            String(filters.start_date),
            "start_date",
          )
        : undefined,
      end_date: filters.end_date
        ? this.sanitizeString(
            String(filters.end_date),
            "end_date",
          )
        : undefined,
      limit:
        filters.limit && filters.limit > 0
          ? Math.min(filters.limit, 100)
          : undefined,
      offset:
        filters.offset && filters.offset >= 0 ? filters.offset : undefined,
      flavor_id: this.sanitizeString(
        String(filters.flavor_id),
        "flavor_id",
      ),
    };

    return this.withErrorContext(
      () =>
        this.getResource<ExecutionHistoryResponse[]>(
          ENDPOINTS.LLM_TRACEABILITY.EXECUTION_HISTORY,
          sanitizedFilters,
        ),
      "fetching execution histories",
    );
  }

  /**
   * Check the health status of the LLM traceability system
   * @returns Health status information including database connectivity
   */
  async healthCheck(): Promise<LLMTraceabilityHealthResponse> {
    return this.withErrorContext(
      () =>
        this.getResource<LLMTraceabilityHealthResponse>(
          ENDPOINTS.LLM_TRACEABILITY.HEALTH,
        ),
      "checking LLM traceability health",
    );
  }

  /**
   * Get analytics for a specific time range
   * @param daysBack Number of days to look back (max 365)
   * @param pipelineType Optional pipeline type filter
   * @returns Analytics data for the specified time range
   */
  async getAnalyticsForTimeRange(
    daysBack: number,
    pipelineType?: string,
  ): Promise<ExecutionAnalyticsResponse> {
    const filters: AnalyticsFilters = {
      days_back: Math.max(1, Math.min(daysBack, 365)),
      pipeline_type: pipelineType,
    };

    return this.getExecutionAnalytics(filters);
  }

  /**
   * Get recent execution histories (last N executions)
   * NOTE: This requires a flavor_id - use getFlavorExecutionHistory instead
   * @param limit Number of executions to retrieve (max 100)
   * @param pipelineType Optional pipeline type filter
   * @param flavorId Required flavor ID
   * @returns Recent execution histories
   * @deprecated Use getFlavorExecutionHistory with a specific flavor_id instead
   */
  async getRecentExecutions(
    limit: number = 10,
    pipelineType?: string,
    flavorId?: string,
  ): Promise<ExecutionHistoryResponse[]> {
    if (!flavorId) {
      throw new Error(
        "Recent executions requires a flavor_id. Use getFlavorExecutionHistory with a specific flavor_id instead.",
      );
    }

    const filters: ExecutionHistoryFilters = {
      limit: Math.max(1, Math.min(limit, 100)),
      pipeline_type: pipelineType,
      flavor_id: flavorId,
    };

    return this.getExecutionHistories(filters);
  }

  /**
   * Get execution history for a specific flavor
   * @param filters Flavor execution history filters
   * @returns Execution history for the specified flavor
   */
  async getFlavorExecutionHistory(
    filters: FlavorExecutionHistoryFilters,
  ): Promise<ExecutionHistoryByFlavorResponse> {
    this.validateRequired(filters.flavor_id, "flavor_id");
    const sanitizedFilters = {
      flavor_id: this.sanitizeString(
        String(filters.flavor_id),
        "flavor_id",
      ),
      limit:
        filters.limit && filters.limit > 0
          ? Math.min(filters.limit, 100)
          : undefined,
    };

    return this.withErrorContext(
      () =>
        this.getResource<ExecutionHistoryByFlavorResponse>(
          ENDPOINTS.LLM_TRACEABILITY.EXECUTION_HISTORY,
          sanitizedFilters,
        ),
      "fetching flavor execution history",
    );
  }

  /**
   * Get analytics for a specific flavor
   * @param filters Flavor analytics filters
   * @returns Analytics data for the specified flavor
   */
  async getFlavorAnalytics(
    filters: FlavorAnalyticsFilters,
  ): Promise<FlavorAnalyticsResponse> {
    this.validateRequired(filters.flavor_id, "flavor_id");
    const sanitizedFlavorId = this.sanitizeString(
      filters.flavor_id,
      "flavor_id",
    );
    const queryParams = filters.days_back
      ? {
          days_back:
            filters.days_back && filters.days_back > 0
              ? Math.min(filters.days_back, 365)
              : 30,
        }
      : undefined;

    return this.withErrorContext(
      () =>
        this.getResource<FlavorAnalyticsResponse>(
          `${ENDPOINTS.LLM_TRACEABILITY.FLAVOR_ANALYTICS}/${sanitizedFlavorId}`,
          queryParams,
        ),
      "fetching flavor analytics",
    );
  }

  /**
   * Record selection with additional context (convenience method)
   * @param executionId The execution ID
   * @param recordId The record ID (e.g., node ID)
   * @param field The field that was selected (e.g., 'definition')
   * @param content The selected content
   * @returns Selection record response
   */
  async recordSuggestionSelection(
    executionId: string,
    recordId: string,
    field: string,
    content: string,
  ): Promise<SelectionRecordResponse> {
    const request: SelectionRecordRequest = {
      execution_id: executionId,
      record_type: "structure_node",
      record_id: recordId,
      suggestion_field: field,
      selected_content: content,
    };

    return this.recordSelection(request);
  }

  /**
   * Get dashboard analytics (convenience method for common analytics needs)
   * @param daysBack Number of days to include in analytics
   * @returns Analytics data formatted for dashboard display
   */
  async getDashboardAnalytics(
    daysBack: number = 30,
  ): Promise<ExecutionAnalyticsResponse> {
    return this.getAnalyticsForTimeRange(daysBack);
  }

  /**
   * Check if the traceability system is available
   * @returns True if system is healthy, false otherwise
   */
  async isSystemHealthy(): Promise<boolean> {
    try {
      const health = await this.healthCheck();
      return health.status === "healthy" && health.database_connection;
    } catch {
      // If health check fails, system is not healthy
      return false;
    }
  }
}

// Export a singleton instance
export const llmTraceabilityService = new LLMTraceabilityService();

// Re-export types for convenience
export type {
  SelectionRecordRequest,
  SelectionRecordResponse,
  AnalyticsFilters,
  ExecutionAnalyticsResponse,
  ExecutionHistoryResponse,
  LLMTraceabilityHealthResponse,
  ExecutionHistoryFilters,
  ExecutionHistoryByFlavorResponse,
  FlavorAnalyticsResponse,
  FlavorExecutionHistoryFilters,
  FlavorAnalyticsFilters,
} from "../types/traceability";
