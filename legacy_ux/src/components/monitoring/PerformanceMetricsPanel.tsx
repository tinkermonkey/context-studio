/**
 * Performance Metrics Panel Component
 *
 * Reusable component for displaying performance metrics in a grid layout
 */

import { Card } from "flowbite-react";
import { TrendingUp, TrendingDown, Minus, ArrowRight } from "lucide-react";

export interface MetricData {
  label: string;
  value: string | number;
  unit?: string;
  trend?: "up" | "down" | "stable";
  trendValue?: string | number;
  description?: string;
  icon?: React.ReactNode;
}

export interface MetricGroup {
  title: string;
  metrics: MetricData[];
}

export interface PerformanceMetricsPanelProps {
  groups: MetricGroup[];
  className?: string;
}

export function PerformanceMetricsPanel({
  groups,
  className = "",
}: PerformanceMetricsPanelProps) {
  const getTrendIcon = (trend?: "up" | "down" | "stable") => {
    switch (trend) {
      case "up":
        return <TrendingUp className="h-4 w-4 text-green-600" />;
      case "down":
        return <TrendingDown className="h-4 w-4 text-red-600" />;
      case "stable":
        return <Minus className="h-4 w-4 text-gray-600" />;
      default:
        return null;
    }
  };

  const getTrendColor = (trend?: "up" | "down" | "stable") => {
    switch (trend) {
      case "up":
        return "text-green-600 dark:text-green-400";
      case "down":
        return "text-red-600 dark:text-red-400";
      case "stable":
        return "text-gray-600 dark:text-gray-400";
      default:
        return "";
    }
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {groups.map((group, groupIndex) => (
        <div key={groupIndex}>
          <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
            {group.title}
          </h3>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {group.metrics.map((metric, metricIndex) => (
              <Card key={metricIndex}>
                <div className="flex flex-col">
                  {/* Metric Header */}
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                      {metric.label}
                    </span>
                    {metric.icon && (
                      <div className="text-gray-400">{metric.icon}</div>
                    )}
                  </div>

                  {/* Metric Value */}
                  <div className="mb-2 flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-gray-900 dark:text-white">
                      {metric.value}
                    </span>
                    {metric.unit && (
                      <span className="text-sm text-gray-500 dark:text-gray-400">
                        {metric.unit}
                      </span>
                    )}
                  </div>

                  {/* Trend Indicator */}
                  {metric.trend && (
                    <div
                      className={`flex items-center gap-1 text-sm ${getTrendColor(
                        metric.trend,
                      )}`}
                    >
                      {getTrendIcon(metric.trend)}
                      {metric.trendValue && <span>{metric.trendValue}</span>}
                    </div>
                  )}

                  {/* Description */}
                  {metric.description && (
                    <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                      {metric.description}
                    </p>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// Specialized metric card for comparison
export interface ComparisonMetricProps {
  label: string;
  before: string | number;
  after: string | number;
  unit?: string;
  improvement?: boolean;
  className?: string;
}

export function ComparisonMetric({
  label,
  before,
  after,
  unit = "",
  improvement,
  className = "",
}: ComparisonMetricProps) {
  const getImprovementColor = () => {
    if (improvement === undefined) return "text-gray-600 dark:text-gray-400";
    return improvement
      ? "text-green-600 dark:text-green-400"
      : "text-red-600 dark:text-red-400";
  };

  return (
    <Card className={className}>
      <div>
        <div className="mb-3 text-sm font-medium text-gray-600 dark:text-gray-400">
          {label}
        </div>
        <div className="flex items-center justify-between">
          <div className="text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">
              Before
            </div>
            <div className="text-lg font-semibold text-gray-700 dark:text-gray-300">
              {before} {unit}
            </div>
          </div>
          <ArrowRight className={`h-5 w-5 ${getImprovementColor()}`} />
          <div className="text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">
              After
            </div>
            <div className={`text-lg font-semibold ${getImprovementColor()}`}>
              {after} {unit}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
