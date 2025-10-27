import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { CsSidebar } from "@/components/layout/cs_sidebar";
import { Card, Button, Spinner, Alert, Tabs, Select } from "flowbite-react";
import {
  Gauge,
  Database,
  HardDrive,
  Zap,
  AlertCircle,
  Play,
  BarChart3,
} from "lucide-react";
import {
  useSystemHealth,
  usePerformanceMetrics,
  usePerformanceTrends,
  useQueryStats,
  useStorageStats,
  useAutoOptimize,
  useOptimizeStorage,
} from "@/api/hooks/optimization";
import {
  SystemHealthCard,
  PerformanceMetricsPanel,
  AnalyticsChart,
} from "@/components/monitoring";
import type { MetricGroup } from "@/components/monitoring/PerformanceMetricsPanel";

export const Route = createFileRoute("/app/monitoring/performance")({
  component: RouteComponent,
});

function RouteComponent() {
  const [trendWindow, setTrendWindow] = useState(24);

  // Fetch data
  const { data: systemHealth, isLoading: healthLoading } = useSystemHealth();
  const { data: performanceMetrics, isLoading: metricsLoading } = usePerformanceMetrics();
  const { data: trends, isLoading: trendsLoading } = usePerformanceTrends(trendWindow);
  const { data: queryStats, isLoading: queryStatsLoading } = useQueryStats();
  const { data: storageStats, isLoading: storageStatsLoading } = useStorageStats();

  const autoOptimize = useAutoOptimize();
  const optimizeStorage = useOptimizeStorage();

  const isLoading = healthLoading || metricsLoading || trendsLoading || queryStatsLoading || storageStatsLoading;

  const handleAutoOptimize = () => {
    autoOptimize.mutate(undefined, {
      onSuccess: () => {
        alert("Auto-optimization triggered successfully");
      },
      onError: (error) => {
        alert(`Optimization failed: ${error.message}`);
      },
    });
  };

  const handleOptimizeStorage = () => {
    optimizeStorage.mutate(undefined, {
      onSuccess: () => {
        alert("Storage optimization triggered successfully");
      },
      onError: (error) => {
        alert(`Storage optimization failed: ${error.message}`);
      },
    });
  };

  // Prepare metrics for display
  const databaseMetrics: MetricGroup[] = performanceMetrics?.database_metrics
    ? [
        {
          title: "Database Performance",
          metrics: Object.entries(performanceMetrics.database_metrics).map(
            ([key, value]: [string, any]) => ({
              label: key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase()),
              value: typeof value === "number" ? value.toFixed(2) : value,
            })
          ),
        },
      ]
    : [];

  const queryMetrics: MetricGroup[] = queryStats
    ? [
        {
          title: "Query Optimization",
          metrics: [
            {
              label: "Total Queries",
              value: queryStats.total_queries,
              icon: <BarChart3 className="h-5 w-5" />,
            },
            {
              label: "Avg Execution Time",
              value: queryStats.avg_execution_time_ms.toFixed(2),
              unit: "ms",
              icon: <Zap className="h-5 w-5" />,
            },
            {
              label: "Materialized Views",
              value: queryStats.materialized_views_count,
              icon: <Database className="h-5 w-5" />,
            },
          ],
        },
      ]
    : [];

  const storageMetrics: MetricGroup[] = storageStats
    ? [
        {
          title: "Storage Optimization",
          metrics: [
            {
              label: "Files Optimized",
              value: storageStats.optimization_summary.files_optimized,
              icon: <HardDrive className="h-5 w-5" />,
            },
            {
              label: "Total Savings",
              value: (storageStats.optimization_summary.total_savings_bytes / 1024 / 1024).toFixed(2),
              unit: "MB",
            },
            {
              label: "Compression Ratio",
              value: (storageStats.optimization_summary.average_compression_ratio * 100).toFixed(1),
              unit: "%",
            },
          ],
        },
      ]
    : [];

  return (
    <>
      <CsSidebar></CsSidebar>
      <CsMain>
        <div className="mb-4 flex items-center justify-between">
          <CsMainTitle>Performance Monitoring</CsMainTitle>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={handleAutoOptimize}
              disabled={autoOptimize.isPending}
            >
              <Play className="mr-2 h-4 w-4" />
              Auto-Optimize
            </Button>
            <Button
              size="sm"
              color="light"
              onClick={handleOptimizeStorage}
              disabled={optimizeStorage.isPending}
            >
              <HardDrive className="mr-2 h-4 w-4" />
              Optimize Storage
            </Button>
          </div>
        </div>

        {systemHealth && (
          <div className="mb-6">
            <SystemHealthCard
              title="Optimization System"
              status={systemHealth.status}
              healthScore={systemHealth.performance_score}
              metrics={[
                ...Object.entries(systemHealth.services_healthy).map(
                  ([service, healthy]) => ({
                    label: service.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase()),
                    value: healthy ? "Healthy" : "Unhealthy",
                    status: (healthy ? "healthy" : "error") as "healthy" | "error",
                  })
                ),
                {
                  label: "Optimization Enabled",
                  value: systemHealth.optimization_enabled ? "Yes" : "No",
                  status: systemHealth.optimization_enabled ? "healthy" : "warning",
                },
              ]}
              issues={systemHealth.issues}
            />
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Spinner size="xl" />
          </div>
        ) : (
          <Tabs aria-label="Performance tabs">
            <Tabs.Item active title="Overview" icon={Gauge}>
              <div className="space-y-6">
                {queryMetrics.length > 0 && (
                  <PerformanceMetricsPanel groups={queryMetrics} />
                )}

                {storageMetrics.length > 0 && (
                  <PerformanceMetricsPanel groups={storageMetrics} />
                )}

                {databaseMetrics.length > 0 && (
                  <PerformanceMetricsPanel groups={databaseMetrics} />
                )}

                {!queryMetrics.length && !storageMetrics.length && !databaseMetrics.length && (
                  <Card>
                    <p className="text-center text-gray-500">No performance metrics available</p>
                  </Card>
                )}
              </div>
            </Tabs.Item>

            <Tabs.Item title="Trends" icon={BarChart3}>
              <div className="space-y-6">
                <div className="flex justify-end">
                  <Select
                    value={trendWindow}
                    onChange={(e) => setTrendWindow(Number(e.target.value))}
                  >
                    <option value={1}>Last hour</option>
                    <option value={6}>Last 6 hours</option>
                    <option value={24}>Last 24 hours</option>
                    <option value={72}>Last 3 days</option>
                    <option value={168}>Last week</option>
                  </Select>
                </div>

                {trends ? (
                  <div className="grid grid-cols-1 gap-6">
                    <SystemHealthCard
                      title="Performance Grade"
                      status={trends.performance_grade.toLowerCase() as any}
                      healthScore={trends.overall_health_score}
                      metrics={[
                        {
                          label: "Analysis Window",
                          value: trends.analysis_window_hours,
                          unit: "hours",
                        },
                      ]}
                      issues={trends.issues.map((issue: any) => issue.description || issue)}
                    />

                    {trends.recommendations && trends.recommendations.length > 0 && (
                      <Card>
                        <h5 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
                          Recommendations
                        </h5>
                        <ul className="space-y-2">
                          {trends.recommendations.map((rec: any, index: number) => (
                            <li
                              key={index}
                              className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300"
                            >
                              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-600" />
                              <span>{rec.recommendation || rec}</span>
                            </li>
                          ))}
                        </ul>
                      </Card>
                    )}
                  </div>
                ) : (
                  <Card>
                    <p className="text-center text-gray-500">No trend data available</p>
                  </Card>
                )}
              </div>
            </Tabs.Item>

            <Tabs.Item title="Query Stats" icon={Database}>
              <div className="space-y-6">
                {queryStats ? (
                  <>
                    {queryMetrics.length > 0 && (
                      <PerformanceMetricsPanel groups={queryMetrics} />
                    )}

                    {queryStats.cache_stats && (
                      <Card>
                        <h5 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
                          Cache Statistics
                        </h5>
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                          {Object.entries(queryStats.cache_stats).map(
                            ([key, value]: [string, any]) => (
                              <div
                                key={key}
                                className="rounded-lg bg-gray-50 p-4 dark:bg-gray-700"
                              >
                                <div className="text-sm font-medium text-gray-600 dark:text-gray-400">
                                  {key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                                </div>
                                <div className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
                                  {typeof value === "number" ? value.toLocaleString() : value}
                                </div>
                              </div>
                            )
                          )}
                        </div>
                      </Card>
                    )}
                  </>
                ) : (
                  <Card>
                    <p className="text-center text-gray-500">No query statistics available</p>
                  </Card>
                )}
              </div>
            </Tabs.Item>

            <Tabs.Item title="Storage" icon={HardDrive}>
              <div className="space-y-6">
                {storageStats ? (
                  <>
                    {storageMetrics.length > 0 && (
                      <PerformanceMetricsPanel groups={storageMetrics} />
                    )}

                    {storageStats.compression_algorithms_used && (
                      <Card>
                        <h5 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
                          Compression Algorithms
                        </h5>
                        <AnalyticsChart
                          title=""
                          data={Object.entries(storageStats.compression_algorithms_used).map(
                            ([algorithm, count]: [string, any]) => ({
                              label: algorithm,
                              value: count,
                            })
                          )}
                          type="bar"
                        />
                      </Card>
                    )}
                  </>
                ) : (
                  <Card>
                    <p className="text-center text-gray-500">No storage statistics available</p>
                  </Card>
                )}
              </div>
            </Tabs.Item>
          </Tabs>
        )}
      </CsMain>
    </>
  );
}
