/**
 * Analytics Chart Component
 *
 * Reusable chart component for displaying analytics data
 * Note: This is a simple implementation. For production, consider using a charting library like recharts or chart.js
 */

import { Card } from "flowbite-react";

export interface ChartDataPoint {
  label: string;
  value: number;

  metadata?: Record<string, any>;
}

export interface AnalyticsChartProps {
  title: string;
  data: ChartDataPoint[];
  type?: "bar" | "line" | "table";
  description?: string;
  className?: string;
}

export function AnalyticsChart({
  title,
  data,
  type = "bar",
  description,
  className = "",
}: AnalyticsChartProps) {
  const maxValue = Math.max(...data.map((d) => d.value), 1);

  if (type === "table") {
    return (
      <Card className={className}>
        <h5 className="mb-2 text-xl font-bold text-gray-900 dark:text-white">
          {title}
        </h5>
        {description && (
          <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
            {description}
          </p>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-500 dark:text-gray-400">
            <thead className="bg-gray-50 text-xs text-gray-700 uppercase dark:bg-gray-700 dark:text-gray-400">
              <tr>
                <th className="px-6 py-3">Label</th>
                <th className="px-6 py-3 text-right">Value</th>
              </tr>
            </thead>
            <tbody>
              {data.map((point, index) => (
                <tr
                  key={index}
                  className="border-b bg-white dark:border-gray-700 dark:bg-gray-800"
                >
                  <td className="px-6 py-4 font-medium text-gray-900 dark:text-white">
                    {point.label}
                  </td>
                  <td className="px-6 py-4 text-right font-semibold">
                    {point.value.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <h5 className="mb-2 text-xl font-bold text-gray-900 dark:text-white">
        {title}
      </h5>
      {description && (
        <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
          {description}
        </p>
      )}

      <div className="space-y-3">
        {data.map((point, index) => (
          <div key={index}>
            <div className="mb-1 flex justify-between text-sm">
              <span className="font-medium text-gray-700 dark:text-gray-300">
                {point.label}
              </span>
              <span className="font-semibold text-gray-900 dark:text-white">
                {point.value.toLocaleString()}
              </span>
            </div>
            <div className="h-4 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
              <div
                className="h-full rounded-full bg-blue-600 transition-all duration-500"
                style={{ width: `${(point.value / maxValue) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {data.length === 0 && (
        <div className="py-8 text-center text-gray-500 dark:text-gray-400">
          No data available
        </div>
      )}
    </Card>
  );
}

// Simplified pie chart component
export interface PieChartProps {
  title: string;
  data: ChartDataPoint[];
  description?: string;
  className?: string;
}

export function SimplePieChart({
  title,
  data,
  description,
  className = "",
}: PieChartProps) {
  const total = data.reduce((sum, point) => sum + point.value, 0);
  const colors = [
    "bg-blue-600",
    "bg-green-600",
    "bg-yellow-600",
    "bg-red-600",
    "bg-purple-600",
    "bg-pink-600",
    "bg-indigo-600",
    "bg-teal-600",
  ];

  return (
    <Card className={className}>
      <h5 className="mb-2 text-xl font-bold text-gray-900 dark:text-white">
        {title}
      </h5>
      {description && (
        <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
          {description}
        </p>
      )}

      <div className="space-y-3">
        {data.map((point, index) => {
          const percentage = total > 0 ? (point.value / total) * 100 : 0;
          return (
            <div key={index}>
              <div className="mb-1 flex justify-between text-sm">
                <div className="flex items-center gap-2">
                  <div
                    className={`h-3 w-3 rounded-full ${
                      colors[index % colors.length]
                    }`}
                  />
                  <span className="font-medium text-gray-700 dark:text-gray-300">
                    {point.label}
                  </span>
                </div>
                <span className="font-semibold text-gray-900 dark:text-white">
                  {percentage.toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                <span>{point.value.toLocaleString()} items</span>
              </div>
            </div>
          );
        })}
      </div>

      {data.length === 0 && (
        <div className="py-8 text-center text-gray-500 dark:text-gray-400">
          No data available
        </div>
      )}
    </Card>
  );
}
