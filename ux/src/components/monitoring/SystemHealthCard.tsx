/**
 * System Health Card Component
 *
 * Reusable card component for displaying system health status and metrics
 */

import { Badge, Card, Progress } from "flowbite-react";;
import { CheckCircle, AlertTriangle, XCircle, Activity } from "lucide-react";

export interface HealthMetric {
  label: string;
  value: string | number;
  status?: "healthy" | "warning" | "error";
  unit?: string;
}

export interface SystemHealthCardProps {
  title: string;
  status: string;
  healthScore?: number;
  metrics?: HealthMetric[];
  issues?: string[];
  className?: string;
}

export function SystemHealthCard({
  title,
  status,
  healthScore,
  metrics = [],
  issues = [],
  className = "",
}: SystemHealthCardProps) {
  const getStatusColor = (
    status: string,
  ): "success" | "warning" | "failure" | "info" => {
    switch (status) {
      case "healthy":
      case "excellent":
        return "success";
      case "warning":
      case "degraded":
      case "good":
        return "warning";
      case "error":
      case "critical":
        return "failure";
      default:
        return "info";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "healthy":
      case "excellent":
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case "warning":
      case "degraded":
      case "good":
        return <AlertTriangle className="h-5 w-5 text-yellow-600" />;
      case "error":
      case "critical":
        return <XCircle className="h-5 w-5 text-red-600" />;
      default:
        return <Activity className="h-5 w-5 text-blue-600" />;
    }
  };

  const getProgressColor = (score: number): string => {
    if (score >= 90) return "green";
    if (score >= 70) return "blue";
    if (score >= 50) return "yellow";
    return "red";
  };

  return (
    <Card className={className}>
      <div className="flex items-center justify-between">
        <h5 className="text-xl font-bold text-gray-900 dark:text-white">
          {title}
        </h5>
        <div className="flex items-center gap-2">
          {getStatusIcon(status)}
          <Badge color={getStatusColor(status)} size="sm">
            {status.toUpperCase()}
          </Badge>
        </div>
      </div>

      {healthScore !== undefined && (
        <div className="mt-4">
          <div className="mb-2 flex justify-between text-sm">
            <span className="font-medium text-gray-700 dark:text-gray-300">
              Health Score
            </span>
            <span className="font-semibold text-gray-900 dark:text-white">
              {healthScore.toFixed(1)}%
            </span>
          </div>
          <Progress
            progress={healthScore}
            color={getProgressColor(healthScore)}
            size="lg"
          />
        </div>
      )}

      {metrics.length > 0 && (
        <div className="mt-4 space-y-2">
          {metrics.map((metric, index) => (
            <div
              key={index}
              className="flex items-center justify-between rounded-lg bg-gray-50 p-3 dark:bg-gray-700"
            >
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {metric.label}
              </span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-gray-900 dark:text-white">
                  {metric.value}
                  {metric.unit && (
                    <span className="ml-1 text-xs text-gray-500">
                      {metric.unit}
                    </span>
                  )}
                </span>
                {metric.status && (
                  <Badge color={getStatusColor(metric.status)} size="xs">
                    {metric.status}
                  </Badge>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {issues.length > 0 && (
        <div className="mt-4">
          <h6 className="mb-2 text-sm font-semibold text-gray-900 dark:text-white">
            Issues Detected
          </h6>
          <ul className="space-y-1">
            {issues.map((issue, index) => (
              <li
                key={index}
                className="flex items-start gap-2 text-sm text-red-600 dark:text-red-400"
              >
                <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                <span>{issue}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
