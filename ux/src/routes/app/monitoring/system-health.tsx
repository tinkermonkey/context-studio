import { createFileRoute } from "@tanstack/react-router";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { CsSidebar } from "@/components/layout/cs_sidebar";
import { Alert, Badge, Button, Card, Spinner, Tabs } from "flowbite-react";
import {
  Activity,
  AlertCircle,
  Cpu,
  Database,
  RefreshCw,
  Server,
  Shield,
} from "lucide-react";
import {
  useDatabaseHealth,
  useDatabaseDashboard,
  useServiceFactoryDashboard,
  useServiceFactoryHealth,
} from "@/api/hooks/admin";
import {
  SystemHealthCard,
  PerformanceMetricsPanel,
} from "@/components/monitoring";
import type { MetricGroup } from "@/components/monitoring/PerformanceMetricsPanel";
import { useButterToast } from "@/hooks/useButterToast";

export const Route = createFileRoute("/app/monitoring/system-health")({
  component: RouteComponent,
});

function RouteComponent() {
  const { info } = useButterToast();
  const {
    data: dbHealth,
    isLoading: dbHealthLoading,
    error: dbHealthError,
    refetch: refetchDbHealth,
  } = useDatabaseHealth();
  const {
    data: dbDashboard,
    isLoading: dbDashboardLoading,
    error: dbDashboardError,
  } = useDatabaseDashboard();
  const {
    data: serviceHealth,
    isLoading: serviceHealthLoading,
    error: serviceHealthError,
    refetch: refetchServiceHealth,
  } = useServiceFactoryHealth();
  const {
    data: serviceDashboard,
    isLoading: serviceDashboardLoading,
    error: serviceDashboardError,
  } = useServiceFactoryDashboard();

  const isLoading =
    dbHealthLoading ||
    dbDashboardLoading ||
    serviceHealthLoading ||
    serviceDashboardLoading;
  const hasError =
    dbHealthError ||
    dbDashboardError ||
    serviceHealthError ||
    serviceDashboardError;

  const handleRefresh = () => {
    refetchDbHealth();
    refetchServiceHealth();
    info("Refreshing system health data");
  };

  // Database metrics
  const dbMetrics: MetricGroup[] = dbDashboard
    ? [
        {
          title: "Database Performance",
          metrics: Object.entries(dbDashboard.performance_metrics)
            .slice(0, 6)
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            .map(([key, value]: [string, any]) => ({
              label: key
                .replace(/_/g, " ")
                .replace(/\b\w/g, (l) => l.toUpperCase()),
              value:
                typeof value === "number" ? value.toFixed(2) : value.toString(),
            })),
        },
      ]
    : [];

  // Service factory metrics
  const serviceMetrics: MetricGroup[] = serviceDashboard
    ? [
        {
          title: "Service Factory Performance",
          metrics: [
            {
              label: "Cache Hit Rate",
              value:
                serviceDashboard.performance.overall_hit_rate_percent.toFixed(
                  1,
                ),
              unit: "%",
              icon: <Activity className="h-5 w-5" />,
            },
            {
              label: "Services Created",
              value: serviceDashboard.performance.total_services_created,
              icon: <Server className="h-5 w-5" />,
            },
            {
              label: "Total Requests",
              value: serviceDashboard.performance.total_requests,
              icon: <Cpu className="h-5 w-5" />,
            },
            {
              label: "Cache Entries",
              value: serviceDashboard.factory_info.total_cache_entries,
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
            <CsMainTitle>System Health</CsMainTitle>
            <Badge color="purple" icon={Shield}>
              Admin Tool
            </Badge>
          </div>
          <Button size="sm" onClick={handleRefresh}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>

        {hasError && (
          <Alert color="failure" icon={AlertCircle} className="mb-4">
            <span className="font-medium">
              Error loading system health data
            </span>
            <p className="mt-1 text-sm">
              {dbHealthError?.message ||
                dbDashboardError?.message ||
                serviceHealthError?.message ||
                serviceDashboardError?.message}
            </p>
          </Alert>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Spinner size="xl" />
          </div>
        ) : (
          <Tabs aria-label="System health tabs">
            <Tabs.Item active title="Overview" icon={Activity}>
              <div className="space-y-6">
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  {dbHealth && (
                    <SystemHealthCard
                      title="Database"
                      status={dbHealth.status}
                      metrics={[
                        {
                          label: "Total Engines",
                          value: Object.keys(dbHealth.engines).length,
                        },
                        {
                          label: "Healthy Engines",
                          value: Object.values(dbHealth.engines).filter(
                            // eslint-disable-next-line @typescript-eslint/no-explicit-any
                            (e: any) => e.status === "healthy",
                          ).length,
                        },
                      ]}
                      issues={dbHealth.issues || []}
                    />
                  )}

                  {serviceHealth && (
                    <SystemHealthCard
                      title="Service Factory"
                      status={serviceHealth.status}
                      metrics={[
                        {
                          label: "Cache Size",
                          value: serviceHealth.cache_size,
                        },
                      ]}
                      issues={serviceHealth.issues}
                    />
                  )}
                </div>

                {serviceMetrics.length > 0 && (
                  <PerformanceMetricsPanel groups={serviceMetrics} />
                )}

                {dbMetrics.length > 0 && (
                  <PerformanceMetricsPanel groups={dbMetrics} />
                )}
              </div>
            </Tabs.Item>

            <Tabs.Item title="Database" icon={Database}>
              <div className="space-y-6">
                {dbDashboard ? (
                  <>
                    <SystemHealthCard
                      title="Database Health"
                      status={dbDashboard.health_status.status}
                      metrics={[
                        {
                          label: "Total Engines",
                          value: dbDashboard.engines_summary.total_engines,
                        },
                        {
                          label: "Healthy",
                          value: dbDashboard.engines_summary.healthy_engines,
                          status: "healthy" as const,
                        },
                        {
                          label: "Warning",
                          value: dbDashboard.engines_summary.warning_engines,
                          status:
                            dbDashboard.engines_summary.warning_engines > 0
                              ? ("warning" as const)
                              : undefined,
                        },
                        {
                          label: "Error",
                          value: dbDashboard.engines_summary.error_engines,
                          status:
                            dbDashboard.engines_summary.error_engines > 0
                              ? ("error" as const)
                              : undefined,
                        },
                      ]}
                    />

                    {dbDashboard.recommendations &&
                      dbDashboard.recommendations.length > 0 && (
                        <Card>
                          <h5 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
                            Recommendations
                          </h5>
                          <ul className="space-y-2">
                            {dbDashboard.recommendations.map(
                              (rec: string, index: number) => (
                                <li
                                  key={index}
                                  className="text-sm text-gray-700 dark:text-gray-300"
                                >
                                  • {rec}
                                </li>
                              ),
                            )}
                          </ul>
                        </Card>
                      )}

                    {dbMetrics.length > 0 && (
                      <PerformanceMetricsPanel groups={dbMetrics} />
                    )}
                  </>
                ) : (
                  <Card>
                    <p className="text-center text-gray-500">
                      No database health data available
                    </p>
                  </Card>
                )}
              </div>
            </Tabs.Item>

            <Tabs.Item title="Services" icon={Server}>
              <div className="space-y-6">
                {serviceDashboard ? (
                  <>
                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                      <SystemHealthCard
                        title="Service Factory Health"
                        status={serviceDashboard.health.status}
                        metrics={[
                          {
                            label: "Cache Size",
                            value: serviceDashboard.health.cache_size,
                          },
                        ]}
                        issues={serviceDashboard.health.issues}
                      />

                      <Card>
                        <h5 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
                          Top Services
                        </h5>
                        <div className="space-y-3">
                          {serviceDashboard.top_services.length > 0 ? (
                            serviceDashboard.top_services.map(
                              (service, index) => (
                                <div
                                  key={index}
                                  className="rounded-lg bg-gray-50 p-3 dark:bg-gray-700"
                                >
                                  <div className="text-xs text-gray-500 dark:text-gray-400">
                                    {index === 0
                                      ? "Most Used Service"
                                      : "Top Service"}
                                  </div>
                                  <div className="font-medium text-gray-900 dark:text-white">
                                    {service.service_type}
                                  </div>
                                  <div className="text-sm text-gray-600 dark:text-gray-400">
                                    Requests: {service.request_count}
                                  </div>
                                </div>
                              ),
                            )
                          ) : (
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                              No service data available
                            </p>
                          )}
                        </div>
                      </Card>
                    </div>

                    {serviceMetrics.length > 0 && (
                      <PerformanceMetricsPanel groups={serviceMetrics} />
                    )}
                  </>
                ) : (
                  <Card>
                    <p className="text-center text-gray-500">
                      No service factory data available
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
