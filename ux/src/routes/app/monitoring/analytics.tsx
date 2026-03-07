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
  Download,
  TrendingUp,
  Users,
  Activity,
  Target,
  AlertCircle,
  BarChart3,
} from "lucide-react";
import {
  useChangeSummary,
  useUserActivity,
  useEntityHotspots,
  useCollaborationMetrics,
  useTrends,
  useAnalyticsHealth,
  exportAnalyticsCSV,
} from "@/api/hooks/analytics";
import {
  SystemHealthCard,
  AnalyticsChart,
  SimplePieChart,
  PerformanceMetricsPanel,
} from "@/components/monitoring";
import type { MetricGroup } from "@/components/monitoring/PerformanceMetricsPanel";
import { useButterToast } from "@/hooks/useButterToast";

export const Route = createFileRoute("/app/monitoring/analytics")({
  component: RouteComponent,
});

function RouteComponent() {
  const [timePeriod, setTimePeriod] = useState(30);
  const [exporting, setExporting] = useState(false);
  const toast = useButterToast();

  // Fetch data
  const {
    data: summary,
    isLoading: summaryLoading,
    error: summaryError,
  } = useChangeSummary(timePeriod);
  const {
    data: userActivity,
    isLoading: userActivityLoading,
    error: userActivityError,
  } = useUserActivity({ days: timePeriod });
  const {
    data: hotspots,
    isLoading: hotspotsLoading,
    error: hotspotsError,
  } = useEntityHotspots(20);
  const {
    data: collaboration,
    isLoading: collaborationLoading,
    error: collaborationError,
  } = useCollaborationMetrics(timePeriod);
  const {
    data: trends,
    isLoading: trendsLoading,
    error: trendsError,
  } = useTrends(timePeriod);
  const { data: health } = useAnalyticsHealth();

  const isLoading =
    summaryLoading ||
    userActivityLoading ||
    hotspotsLoading ||
    collaborationLoading ||
    trendsLoading;
  const hasError =
    summaryError ||
    userActivityError ||
    hotspotsError ||
    collaborationError ||
    trendsError;

  const handleExportCSV = async (
    reportType: "user-activity" | "hotspots" | "trends",
  ) => {
    try {
      setExporting(true);
      const blob = await exportAnalyticsCSV(reportType, timePeriod);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${reportType}_${timePeriod}days.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success(`Successfully exported ${reportType} to CSV`);
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error occurred";
      toast.error(`Export failed: ${errorMessage}`);
    } finally {
      setExporting(false);
    }
  };

  // Prepare metrics for display
  const summaryMetrics: MetricGroup[] = summary
    ? [
        {
          title: "Change Summary",
          metrics: [
            {
              label: "Total Changes",
              value: summary.total_changes,
              icon: <Activity className="h-5 w-5" />,
            },
            {
              label: "Entities Modified",
              value: summary.entities_modified,
              icon: <Target className="h-5 w-5" />,
            },
            {
              label: "Active Users",
              value: summary.active_users,
              icon: <Users className="h-5 w-5" />,
            },
            {
              label: "Changesets",
              value: summary.changesets,
              icon: <TrendingUp className="h-5 w-5" />,
            },
          ],
        },
      ]
    : [];

  const collaborationMetrics: MetricGroup[] = collaboration
    ? [
        {
          title: "Collaboration Metrics",
          metrics: [
            {
              label: "Proposal Authors",
              value: collaboration.proposal_authors,
            },
            {
              label: "Voters",
              value: collaboration.voters,
            },
            {
              label: "Total Votes",
              value: collaboration.total_votes,
            },
            {
              label: "Avg Response Time",
              value: collaboration.avg_response_time_hours.toFixed(1),
              unit: "hours",
            },
            {
              label: "Approval Rate",
              value: (collaboration.approval_rate * 100).toFixed(1),
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
            <CsMainTitle>Analytics Dashboard</CsMainTitle>
            <Badge color="purple" icon={BarChart3}>
              Developer Tool
            </Badge>
          </div>
          <div className="flex items-center gap-4">
            <Select
              value={timePeriod}
              onChange={(e) => setTimePeriod(Number(e.target.value))}
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={60}>Last 60 days</option>
              <option value={90}>Last 90 days</option>
              <option value={365}>Last year</option>
            </Select>
          </div>
        </div>

        {hasError && (
          <Alert color="failure" icon={AlertCircle} className="mb-4">
            <span className="font-medium">Error loading analytics data</span>
            <p className="mt-1 text-sm">
              {summaryError?.message ||
                userActivityError?.message ||
                hotspotsError?.message ||
                collaborationError?.message ||
                trendsError?.message}
            </p>
          </Alert>
        )}

        {health && (
          <div className="mb-6">
            <SystemHealthCard
              title="Analytics System"
              status={health.status}
              healthScore={
                health.query_performance_ms
                  ? Math.max(0, 100 - health.query_performance_ms / 50)
                  : undefined
              }
              metrics={[
                {
                  label: "DuckDB Available",
                  value: health.duckdb_available ? "Yes" : "No",
                  status: health.duckdb_available ? "healthy" : "error",
                },
                {
                  label: "Active Views",
                  value: health.active_views,
                },
                {
                  label: "Query Performance",
                  value: health.query_performance_ms?.toFixed(0) || "N/A",
                  unit: "ms",
                },
              ]}
              issues={
                !health.duckdb_available ? ["DuckDB is not available"] : []
              }
            />
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Spinner size="xl" />
          </div>
        ) : (
          <Tabs aria-label="Analytics tabs">
            <Tabs.Item active title="Overview" icon={Activity}>
              <div className="space-y-6">
                {/* Summary Metrics */}
                {summaryMetrics.length > 0 && (
                  <PerformanceMetricsPanel groups={summaryMetrics} />
                )}

                {/* Collaboration Metrics */}
                {collaborationMetrics.length > 0 && (
                  <PerformanceMetricsPanel groups={collaborationMetrics} />
                )}
              </div>
            </Tabs.Item>

            <Tabs.Item title="User Activity" icon={Users}>
              <div className="space-y-6">
                <div className="flex justify-end">
                  <Button
                    size="sm"
                    onClick={() => handleExportCSV("user-activity")}
                    disabled={exporting}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export CSV
                  </Button>
                </div>

                {userActivity && userActivity.length > 0 ? (
                  <AnalyticsChart
                    title="Top Active Users"
                    description={`User activity over the last ${timePeriod} days`}
                    data={userActivity.slice(0, 10).map((user) => ({
                      label: user.author_id,
                      value: user.total_changes,
                      metadata: user,
                    }))}
                    type="bar"
                  />
                ) : (
                  <Card>
                    <p className="text-center text-gray-500">
                      No user activity data available
                    </p>
                  </Card>
                )}
              </div>
            </Tabs.Item>

            <Tabs.Item title="Entity Hotspots" icon={Target}>
              <div className="space-y-6">
                <div className="flex justify-end">
                  <Button
                    size="sm"
                    onClick={() => handleExportCSV("hotspots")}
                    disabled={exporting}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export CSV
                  </Button>
                </div>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  {hotspots && hotspots.length > 0 ? (
                    <>
                      <AnalyticsChart
                        title="Most Modified Entities"
                        description="Entities with the highest modification frequency"
                        data={hotspots.slice(0, 10).map((hotspot) => ({
                          label: `${hotspot.entity_type}: ${hotspot.entity_id.substring(0, 8)}...`,
                          value: hotspot.total_modifications,
                        }))}
                        type="bar"
                      />

                      <SimplePieChart
                        title="Entity Types Distribution"
                        description="Distribution of modifications by entity type"
                        data={Object.entries(
                          hotspots.reduce(
                            (acc, h) => {
                              acc[h.entity_type] =
                                (acc[h.entity_type] || 0) +
                                h.total_modifications;
                              return acc;
                            },
                            {} as Record<string, number>,
                          ),
                        ).map(([type, count]) => ({
                          label: type,
                          value: count,
                        }))}
                      />
                    </>
                  ) : (
                    <Card>
                      <p className="text-center text-gray-500">
                        No entity hotspot data available
                      </p>
                    </Card>
                  )}
                </div>
              </div>
            </Tabs.Item>

            <Tabs.Item title="Trends" icon={TrendingUp}>
              <div className="space-y-6">
                <div className="flex justify-end">
                  <Button
                    size="sm"
                    onClick={() => handleExportCSV("trends")}
                    disabled={exporting}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export CSV
                  </Button>
                </div>

                {trends &&
                trends.daily_trends &&
                trends.daily_trends.length > 0 ? (
                  <div className="grid grid-cols-1 gap-6">
                    <AnalyticsChart
                      title="Daily Change Trends"
                      description={`Change activity over ${trends.analysis_period_days} days`}
                      data={trends.daily_trends.slice(0, 30).map(
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        (trend: any) => ({
                          label: trend.date || trend.day || "Unknown",
                          value: trend.total_changes || trend.changes || 0,
                        }),
                      )}
                      type="bar"
                    />

                    {trends.peak_hours && trends.peak_hours.length > 0 && (
                      <AnalyticsChart
                        title="Peak Activity Hours"
                        description="Activity distribution by hour of day"
                        data={trends.peak_hours.slice(0, 24).map(
                          // eslint-disable-next-line @typescript-eslint/no-explicit-any
                          (peak: any) => ({
                            label: `${peak.hour || 0}:00`,
                            value: peak.activity || peak.count || 0,
                          }),
                        )}
                        type="bar"
                      />
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
          </Tabs>
        )}
      </CsMain>
    </>
  );
}
