/**
 * AnalyticsDashboard Component
 *
 * Dashboard for displaying LLM traceability analytics including success rates,
 * usage trends, and performance metrics. Uses Flowbite React components for layout.
 */

import React, { useState, useMemo } from "react";
import { Card, Button, Select, Spinner, Alert } from "flowbite-react";
import {
  useAnalyticsForTimeRange,
  useAnalyticsWithRefresh,
  useLLMTraceabilityHealth,
} from "@/api/hooks/llm/useLLMTraceability";
import type {
  ExecutionAnalyticsData,
  AnalyticsDashboardConfig,
  AnalyticsTimeRangeFilter,
} from "@/api/types/traceability";

export interface AnalyticsDashboardProps {
  /**
   * Dashboard configuration options
   */
  config?: AnalyticsDashboardConfig;

  /**
   * Custom CSS class name
   */
  className?: string;

  /**
   * Whether to show the health status indicator
   * @default true
   */
  showHealthStatus?: boolean;

  /**
   * Optional pipeline type filter
   */
  pipelineTypeFilter?: string;

  /**
   * Callback when analytics data changes
   */
  onDataUpdate?: (data: ExecutionAnalyticsData) => void;
}

// Predefined time range options
const TIME_RANGE_OPTIONS: AnalyticsTimeRangeFilter[] = [
  { label: "Last 24 Hours", days: 1 },
  { label: "Last 7 Days", days: 7 },
  { label: "Last 30 Days", days: 30 },
  { label: "Last 90 Days", days: 90 },
  { label: "Last Year", days: 365 },
];

/**
 * Metric card component for displaying key performance indicators
 */
const MetricCard: React.FC<{
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: "up" | "down" | "neutral";
  icon?: React.ReactNode;
}> = ({ title, value, subtitle, trend, icon }) => {
  const trendColor =
    trend === "up"
      ? "text-green-600"
      : trend === "down"
        ? "text-red-600"
        : "text-gray-600";

  return (
    <Card className="min-h-[120px]">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
            {title}
          </h3>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
            {value}
          </p>
          {subtitle && (
            <p className={`mt-1 text-xs ${trendColor}`}>{subtitle}</p>
          )}
        </div>
        {icon && <div className="text-gray-400 dark:text-gray-600">{icon}</div>}
      </div>
    </Card>
  );
};

/**
 * Main analytics dashboard component
 */
export const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({
  config = {},
  className = "",
  showHealthStatus = true,
  pipelineTypeFilter,
  onDataUpdate,
}) => {
  const {
    autoRefresh = false,
    refreshInterval = 5 * 60 * 1000, // 5 minutes
    defaultTimeRange = 30,
    showExportButton = false,
  } = config;

  const [selectedTimeRange, setSelectedTimeRange] =
    useState<number>(defaultTimeRange);

  // Fetch analytics data with optional auto-refresh
  const {
    data: analyticsData,
    isLoading: analyticsLoading,
    error: analyticsError,
    refetch: refetchAnalytics,
  } = autoRefresh
    ? useAnalyticsWithRefresh(selectedTimeRange, refreshInterval)
    : useAnalyticsForTimeRange(selectedTimeRange, pipelineTypeFilter);

  // Health status
  const { data: healthData, isLoading: healthLoading } =
    useLLMTraceabilityHealth();

  // Memoized analytics calculations
  const metrics = useMemo(() => {
    if (!analyticsData?.data) {
      return null;
    }

    const data = analyticsData.data;

    return {
      totalExecutions: data.total_executions.toLocaleString(),
      successRate: `${(data.success_rate * 100).toFixed(1)}%`,
      avgExecutionTime: `${data.avg_execution_time.toFixed(0)}ms`,
      totalTokens: data.total_tokens_used.toLocaleString(),
      selectionRate: `${(data.selection_rate * 100).toFixed(1)}%`,
      totalSelections: data.total_selections.toLocaleString(),
    };
  }, [analyticsData]);

  // Call onDataUpdate when data changes
  React.useEffect(() => {
    if (analyticsData?.data && onDataUpdate) {
      onDataUpdate(analyticsData.data);
    }
  }, [analyticsData?.data, onDataUpdate]);

  const handleTimeRangeChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    setSelectedTimeRange(parseInt(event.target.value));
  };

  const handleRefresh = () => {
    refetchAnalytics();
  };

  const handleExport = () => {
    if (analyticsData?.data) {
      const dataStr = JSON.stringify(analyticsData.data, null, 2);
      const dataBlob = new Blob([dataStr], { type: "application/json" });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `llm-analytics-${Date.now()}.json`;
      link.click();
      URL.revokeObjectURL(url);
    }
  };

  return (
    <div className={`analytics-dashboard ${className}`.trim()}>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            LLM Analytics Dashboard
          </h2>
          <p className="mt-1 text-gray-600 dark:text-gray-400">
            Track AI suggestion usage and performance metrics
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Health Status */}
          {showHealthStatus && (
            <div className="flex items-center gap-2">
              {healthLoading ? (
                <Spinner size="sm" />
              ) : (
                <div
                  className={`h-3 w-3 rounded-full ${
                    healthData?.status === "healthy"
                      ? "bg-green-500"
                      : healthData?.status === "degraded"
                        ? "bg-yellow-500"
                        : "bg-red-500"
                  }`}
                />
              )}
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {healthData?.status || "Unknown"}
              </span>
            </div>
          )}

          {/* Time Range Selector */}
          <Select
            value={selectedTimeRange}
            onChange={handleTimeRangeChange}
            className="min-w-[150px]"
          >
            {TIME_RANGE_OPTIONS.map((option) => (
              <option key={option.days} value={option.days}>
                {option.label}
              </option>
            ))}
          </Select>

          {/* Refresh Button */}
          <Button
            onClick={handleRefresh}
            disabled={analyticsLoading}
            size="sm"
            color="gray"
          >
            {analyticsLoading ? <Spinner size="sm" /> : "Refresh"}
          </Button>

          {/* Export Button */}
          {showExportButton && (
            <Button
              onClick={handleExport}
              disabled={!analyticsData?.data}
              size="sm"
              color="light"
            >
              Export
            </Button>
          )}
        </div>
      </div>

      {/* Error State */}
      {analyticsError && (
        <Alert color="failure" className="mb-6">
          <span className="font-medium">Failed to load analytics:</span>{" "}
          {analyticsError.message}
        </Alert>
      )}

      {/* Loading State */}
      {analyticsLoading && !analyticsData && (
        <div className="flex justify-center py-12">
          <div className="text-center">
            <Spinner size="xl" />
            <p className="mt-4 text-gray-600 dark:text-gray-400">
              Loading analytics data...
            </p>
          </div>
        </div>
      )}

      {/* Metrics Grid */}
      {metrics && (
        <div className="mb-8 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          <MetricCard
            title="Total Executions"
            value={metrics.totalExecutions}
            subtitle="LLM calls processed"
            icon={
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100">
                <span className="text-blue-600">🔄</span>
              </div>
            }
          />

          <MetricCard
            title="Success Rate"
            value={metrics.successRate}
            subtitle="Successful completions"
            trend={analyticsData?.data?.success_rate && analyticsData.data.success_rate > 0.9 ? "up" : "neutral"}
            icon={
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-100">
                <span className="text-green-600">✅</span>
              </div>
            }
          />

          <MetricCard
            title="Avg Response Time"
            value={metrics.avgExecutionTime}
            subtitle="Per execution"
            trend={
              analyticsData?.data?.avg_execution_time && analyticsData.data.avg_execution_time < 1000 ? "up" : "down"
            }
            icon={
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-100">
                <span className="text-purple-600">⚡</span>
              </div>
            }
          />

          <MetricCard
            title="Total Selections"
            value={metrics.totalSelections}
            subtitle="User selections made"
            icon={
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-100">
                <span className="text-orange-600">👆</span>
              </div>
            }
          />

          <MetricCard
            title="Selection Rate"
            value={metrics.selectionRate}
            subtitle="% of suggestions used"
            trend={analyticsData?.data?.selection_rate && analyticsData.data.selection_rate > 0.5 ? "up" : "neutral"}
            icon={
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-100">
                <span className="text-teal-600">📊</span>
              </div>
            }
          />

          <MetricCard
            title="Tokens Used"
            value={metrics.totalTokens}
            subtitle="Total token consumption"
            icon={
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-100">
                <span className="text-red-600">🎯</span>
              </div>
            }
          />
        </div>
      )}

      {/* Additional Analytics Section */}
      {analyticsData?.data && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Performance Overview Card */}
          <Card>
            <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
              Performance Overview
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-gray-600 dark:text-gray-400">
                  Success Rate
                </span>
                <div className="flex items-center gap-2">
                  <div className="h-2 w-24 rounded-full bg-gray-200 dark:bg-gray-700">
                    <div
                      className="h-2 rounded-full bg-green-600"
                      style={{
                        width: `${analyticsData.data.success_rate * 100}%`,
                      }}
                    />
                  </div>
                  <span className="text-sm font-medium">
                    {metrics?.successRate}
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-gray-600 dark:text-gray-400">
                  Selection Rate
                </span>
                <div className="flex items-center gap-2">
                  <div className="h-2 w-24 rounded-full bg-gray-200 dark:bg-gray-700">
                    <div
                      className="h-2 rounded-full bg-blue-600"
                      style={{
                        width: `${analyticsData.data.selection_rate * 100}%`,
                      }}
                    />
                  </div>
                  <span className="text-sm font-medium">
                    {metrics?.selectionRate}
                  </span>
                </div>
              </div>
            </div>
          </Card>

          {/* Usage Summary Card */}
          <Card>
            <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
              Usage Summary
            </h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">
                  Time Period
                </span>
                <span className="font-medium">
                  {
                    TIME_RANGE_OPTIONS.find(
                      (opt) => opt.days === selectedTimeRange,
                    )?.label
                  }
                </span>
              </div>

              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">
                  Successful Executions
                </span>
                <span className="font-medium">
                  {analyticsData.data.successful_executions.toLocaleString()}
                </span>
              </div>

              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">
                  Failed Executions
                </span>
                <span className="font-medium">
                  {(
                    analyticsData.data.total_executions -
                    analyticsData.data.successful_executions
                  ).toLocaleString()}
                </span>
              </div>

              {pipelineTypeFilter && (
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">
                    Pipeline Type
                  </span>
                  <span className="font-medium">{pipelineTypeFilter}</span>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}

      {/* No Data State */}
      {!analyticsLoading && !analyticsData?.data && !analyticsError && (
        <div className="py-12 text-center">
          <div className="mb-4 text-gray-400 dark:text-gray-600">
            <span className="text-6xl">📊</span>
          </div>
          <h3 className="mb-2 text-lg font-medium text-gray-900 dark:text-white">
            No Analytics Data
          </h3>
          <p className="text-gray-600 dark:text-gray-400">
            No LLM executions found for the selected time period.
          </p>
        </div>
      )}
    </div>
  );
};

export default AnalyticsDashboard;
