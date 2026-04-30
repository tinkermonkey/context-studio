import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { CsSidebar } from "@/components/layout/cs_sidebar";
import {
  Alert,
  Badge,
  Button,
  Card,
  Select,
  Spinner,
  Tabs,
} from "flowbite-react";
import {
  Gauge,
  Database,
  HardDrive,
  AlertCircle,
  Play,
  BarChart3,
  Wrench,
} from "lucide-react";
import {
  useSystemHealth,
  usePerformanceMetrics,
  usePerformanceTrends,
  useQueryStats,
  useStorageStats,
  useAutoTunePerformance,
  useCompressStorage,
} from "@/api/hooks/performance";
import {
  SystemHealthCard,
  PerformanceMetricsPanel,
  AnalyticsChart,
} from "@/components/monitoring";
import type { MetricGroup } from "@/components/monitoring/PerformanceMetricsPanel";
import { useButterToast } from "@/hooks/useButterToast";

export const Route = createFileRoute("/app/monitoring/performance")({
  component: RouteComponent,
});

function RouteComponent() {
  const [trendWindow, setTrendWindow] = useState(24);
  const toast = useButterToast();

  // Fetch data
  const {
    data: systemHealth,
    isLoading: healthLoading,
    error: healthError,
  } = useSystemHealth();
  const {
    data: performanceMetrics,
    isLoading: metricsLoading,
    error: metricsError,
  } = usePerformanceMetrics();
  const {
    data: trends,
    isLoading: trendsLoading,
    error: trendsError,
  } = usePerformanceTrends(trendWindow);
  const {
    data: queryStats,
    isLoading: queryStatsLoading,
    error: queryStatsError,
  } = useQueryStats();
  const {
    data: storageStats,
    isLoading: storageStatsLoading,
    error: storageStatsError,
  } = useStorageStats();

  const autoTune = useAutoTunePerformance();
  const compressStorage = useCompressStorage();

  const isLoading =
    healthLoading ||
    metricsLoading ||
    trendsLoading ||
    queryStatsLoading ||
    storageStatsLoading;
  const hasError =
    healthError ||
    metricsError ||
    trendsError ||
    queryStatsError ||
    storageStatsError;

  const handleAutoTune = () => {
    autoTune.mutate(undefined, {
      onSuccess: () => {
        toast.success("Auto-tuning triggered successfully");
      },
      onError: (error) => {
        toast.error(`Performance tuning failed: ${error.message}`);
      },
    });
  };

  const handleCompressStorage = () => {
    compressStorage.mutate(undefined, {
      onSuccess: () => {
        toast.success("Storage compression triggered successfully");
      },
      onError: (error) => {
        toast.error(`Storage compression failed: ${error.message}`);
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
              label: key
                .replace(/_/g, " ")
                .replace(/\b\w/g, (l) => l.toUpperCase()),
              value: typeof value === "number" ? value.toFixed(2) : value,
            }),
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
            },
            {
              label: "Avg Execution Time",
              value: queryStats.avg_execution_time_ms.toFixed(2),
              unit: "ms",
            },
            {
              label: "Materialized Views",
              value: queryStats.materialized_views_count,
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
            },
            {
              label: "Total Savings",
              value: (
                storageStats.optimization_summary.total_savings_bytes /
                1024 /
                1024
              ).toFixed(2),
              unit: "MB",
            },
            {
              label: "Compression Ratio",
              value: (
                storageStats.optimization_summary.average_compression_ratio *
                100
              ).toFixed(1),
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
          <div className="flex items-center gap-3">
            <CsMainTitle>Performance Monitoring</CsMainTitle>
            <Badge color="purple" icon={Wrench}>
              Developer Tool
            </Badge>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={handleAutoTune}
              disabled={autoTune.isPending}
            >
              <Play className="mr-2 h-4 w-4" />
              Auto-Tune
            </Button>
            <Button
              size="sm"
              color="light"
              onClick={handleCompressStorage}
              disabled={compressStorage.isPending}
            >
              <HardDrive className="mr-2 h-4 w-4" />
              Compress Storage
            </Button>
          </div>
        </div>

        {hasError && (
          <Alert color="failure" icon={AlertCircle} className="mb-4">
            <span className="font-medium">Error loading performance data</span>
            <p className="mt-1 text-sm">
              {
                (
                  healthError ||
                  metricsError ||
                  trendsError ||
                  queryStatsError ||
                  storageStatsError
                )?.message
              }
            </p>
          </Alert>
        )}

        {systemHealth && (
          <div className="mb-6">
            <SystemHealthCard
              title="Optimization System"
              status={systemHealth.status}
              healthScore={systemHealth.performance_score}
              metrics={[
                ...Object.entries(systemHealth.services_healthy).map(
                  ([service, healthy]) => {
                    const status: "healthy" | "error" = healthy
                      ? "healthy"
                      : "error";
                    return {
                      label: service
                        .replace(/_/g, " ")
                        .replace(/\b\w/g, (l) => l.toUpperCase()),
                      value: healthy ? "Healthy" : "Unhealthy",
                      status,
                    };
                  },
                ),
                {
                  label: "Optimization Enabled",
                  value: systemHealth.optimization_enabled ? "Yes" : "No",
                  status: systemHealth.optimization_enabled
                    ? ("healthy" as const)
                    : ("warning" as const),
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

                {!queryMetrics.length &&
                  !storageMetrics.length &&
                  !databaseMetrics.length && (
                    <Card>
                      <p className="text-center text-gray-500">
                        No performance metrics available
                      </p>
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
                      status={trends.performance_grade.toLowerCase()}
                      healthScore={trends.overall_health_score}
                      metrics={[
                        {
                          label: "Analysis Window",
                          value: trends.analysis_window_hours,
                          unit: "hours",
                        },
                      ]}
                      issues={trends.issues.map(
                        (issue: any) => issue.description || issue,
                      )}
                    />

                    {trends.recommendations &&
                      trends.recommendations.length > 0 && (
                        <Card>
                          <h5 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
                            Recommendations
                          </h5>
                          <ul className="space-y-2">
                            {trends.recommendations.map(
                              (rec: any, index: number) => (
                                <li
                                  key={index}
                                  className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300"
                                >
                                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-600" />
                                  <span>{rec.recommendation || rec}</span>
                                </li>
                              ),
                            )}
                          </ul>
                        </Card>
                      )}
                  </div>
                ) : (
                  <Card>
                    <p className="text-center text-gray-500">
                      No trend data available
                    </p>
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
                                  {key
                                    .replace(/_/g, " ")
                                    .replace(/\b\w/g, (l) => l.toUpperCase())}
                                </div>
                                <div className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
                                  {typeof value === "number"
                                    ? value.toLocaleString()
                                    : value}
                                </div>
                              </div>
                            ),
                          )}
                        </div>
                      </Card>
                    )}
                  </>
                ) : (
                  <Card>
                    <p className="text-center text-gray-500">
                      No query statistics available
                    </p>
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
                          data={Object.entries(
                            storageStats.compression_algorithms_used,
                          ).map(([algorithm, count]: [string, any]) => ({
                            label: algorithm,
                            value: count,
                          }))}
                          type="bar"
                        />
                      </Card>
                    )}
                  </>
                ) : (
                  <Card>
                    <p className="text-center text-gray-500">
                      No storage statistics available
                    </p>
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
