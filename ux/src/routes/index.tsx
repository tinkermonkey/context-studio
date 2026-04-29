import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Alert,
  Badge,
  Button,
  Card,
  DarkThemeToggle,
  Spinner,
} from "flowbite-react";
import {
  Database,
  GitBranch,
  FileText,
  Activity,
  BarChart3,
  Network,
  ArrowRight,
  Layers,
  Clock,
  AlertCircle,
} from "lucide-react";
import { TreeChartPanel } from "@/components/panels/TreeChartPanel";
import {
  useLayerNodes,
  useDomainNodes,
  useTermNodes,
} from "@/api/hooks/structure_nodes/useStructureNodes";
import { useLLMTraceabilityHealth } from "@/api/hooks/llm/useLLMTraceability";
import { useChangeEvents } from "@/api/hooks/events/useChangeEvents";
import { StatCard } from "@/components/ui/StatCard";
import { QuickActionCard } from "@/components/ui/QuickActionCard";

export const Route = createFileRoute("/")({
  component: HomeComponent,
});

// Style constants for consistent theming
const THEME_COLORS = {
  stat: {
    total: "bg-blue-500",
    layers: "bg-purple-500",
    domains: "bg-green-500",
    terms: "bg-orange-500",
  },
  status: {
    healthy: "bg-green-400",
    degraded: "bg-yellow-400",
    unhealthy: "bg-red-400",
  },
};

function HomeComponent() {
  // Fetch knowledge graph statistics
  const {
    data: layers,
    isLoading: layersLoading,
    error: layersError,
  } = useLayerNodes();

  const {
    data: domains,
    isLoading: domainsLoading,
    error: domainsError,
  } = useDomainNodes();

  const {
    data: terms,
    isLoading: termsLoading,
    error: termsError,
  } = useTermNodes();

  // Fetch LLM system health
  const {
    data: healthData,
    isLoading: healthLoading,
    error: healthError,
  } = useLLMTraceabilityHealth();

  // Fetch recent activity (latest 5 change events)
  const {
    data: recentEvents,
    isLoading: eventsLoading,
    error: eventsError,
  } = useChangeEvents({ limit: 5 });

  const statsLoading = layersLoading || domainsLoading || termsLoading;
  const statsError = layersError || domainsError || termsError;

  // Calculate statistics
  const layerCount = layers?.length || 0;
  const domainCount = domains?.length || 0;
  const termCount = terms?.length || 0;
  const totalNodes = layerCount + domainCount + termCount;

  // Format date for display
  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return dateString;
    }
  };

  // Get status badge color
  const getStatusBadgeColor = (status?: string) => {
    if (status === "healthy") return "success";
    if (status === "degraded") return "warning";
    return "failure";
  };

  // Format event type for display
  const formatEventType = (eventType: string) => {
    return eventType
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Dark mode toggle - Fixed positioning to prevent overlap */}
      <div className="fixed top-4 right-4 z-50">
        <DarkThemeToggle aria-label="Toggle dark mode" />
      </div>

      {/* Hero Section */}
      <div className="from-primary-600 to-primary-800 dark:from-primary-700 dark:to-primary-900 bg-gradient-to-br px-4 py-16 text-white">
        <div className="mx-auto max-w-7xl">
          <div className="mb-8 text-center">
            <h1 className="mb-4 text-5xl font-bold">Context Studio</h1>
            <p className="text-primary-100 mb-6 text-xl">
              Create and curate knowledge graphs for RAG and AI communication
            </p>
            <div className="flex flex-wrap items-center justify-center gap-4">
              <Link to="/app">
                <Button size="lg" color="light">
                  Get Started
                  <ArrowRight className="ml-2 h-5 w-5" aria-hidden="true" />
                </Button>
              </Link>
              <Link to="/app/config">
                <Button size="lg" color="light" outline>
                  Configuration
                </Button>
              </Link>
            </div>
          </div>

          {/* System Status */}
          <div className="mt-6 flex items-center justify-center gap-2">
            <span className="text-primary-100 text-sm">System Status:</span>
            {healthLoading ? (
              <Spinner size="sm" aria-label="Loading system status" />
            ) : healthError ? (
              <Badge color="failure">Error loading status</Badge>
            ) : (
              <>
                <div
                  className={`h-2.5 w-2.5 rounded-full ${
                    THEME_COLORS.status[
                      healthData?.status as keyof typeof THEME_COLORS.status
                    ] || THEME_COLORS.status.unhealthy
                  }`}
                  role="status"
                  aria-label={`System status: ${healthData?.status || "unknown"}`}
                />
                <Badge color={getStatusBadgeColor(healthData?.status)}>
                  {healthData?.status || "Unknown"}
                </Badge>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="mx-auto max-w-7xl px-4 py-12">
        {/* Statistics Grid */}
        <section className="mb-12" aria-labelledby="workspace-overview">
          <h2
            id="workspace-overview"
            className="mb-6 text-2xl font-bold text-gray-900 dark:text-white"
          >
            Workspace Overview
          </h2>

          {statsError ? (
            <Alert color="failure" icon={AlertCircle}>
              <span className="font-medium">
                Error loading workspace statistics:
              </span>{" "}
              {statsError.message || "An unknown error occurred"}
            </Alert>
          ) : statsLoading ? (
            <div className="flex justify-center py-12">
              <Spinner size="xl" aria-label="Loading workspace statistics" />
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
              <StatCard
                title="Total Nodes"
                value={totalNodes}
                icon={Database}
                iconColor={THEME_COLORS.stat.total}
                loading={statsLoading}
              />
              <StatCard
                title="Layers"
                value={layerCount}
                icon={Layers}
                iconColor={THEME_COLORS.stat.layers}
                loading={statsLoading}
              />
              <StatCard
                title="Domains"
                value={domainCount}
                icon={Network}
                iconColor={THEME_COLORS.stat.domains}
                loading={statsLoading}
              />
              <StatCard
                title="Terms"
                value={termCount}
                icon={FileText}
                iconColor={THEME_COLORS.stat.terms}
                loading={statsLoading}
              />
            </div>
          )}
        </section>

        {/* Knowledge Graph Visualization */}
        <section className="mb-12" aria-labelledby="knowledge-graph">
          <h2
            id="knowledge-graph"
            className="mb-6 text-2xl font-bold text-gray-900 dark:text-white"
          >
            Knowledge Graph Structure
          </h2>
          <Card>
            <div className="min-h-[400px]">
              <TreeChartPanel
                className="w-full"
                viewId="dashboard"
                loadingComponent={
                  <div className="flex flex-col items-center justify-center py-12">
                    <Spinner size="xl" aria-label="Loading knowledge graph" />
                    <p className="mt-4 text-gray-600 dark:text-gray-400">
                      Loading knowledge graph...
                    </p>
                  </div>
                }
                errorComponent={
                  <div className="flex flex-col items-center justify-center py-12">
                    <AlertCircle
                      className="mb-4 h-12 w-12 text-red-500"
                      aria-hidden="true"
                    />
                    <p className="mb-2 font-semibold text-gray-900 dark:text-white">
                      Failed to load knowledge graph
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Please try refreshing the page
                    </p>
                  </div>
                }
              />
            </div>
          </Card>
        </section>

        {/* Recent Activity Section */}
        <section className="mb-12" aria-labelledby="recent-activity">
          <h2
            id="recent-activity"
            className="mb-6 text-2xl font-bold text-gray-900 dark:text-white"
          >
            Recent Activity
          </h2>

          {eventsError ? (
            <Alert color="failure" icon={AlertCircle}>
              <span className="font-medium">
                Error loading recent activity:
              </span>{" "}
              {eventsError.message || "An unknown error occurred"}
            </Alert>
          ) : eventsLoading ? (
            <Card>
              <div className="flex justify-center py-8">
                <Spinner size="lg" aria-label="Loading recent activity" />
              </div>
            </Card>
          ) : !recentEvents || recentEvents.length === 0 ? (
            <Card>
              <div className="py-8 text-center">
                <Clock
                  className="mx-auto mb-3 h-12 w-12 text-gray-400"
                  aria-hidden="true"
                />
                <p className="text-gray-600 dark:text-gray-400">
                  No recent activity to display
                </p>
              </div>
            </Card>
          ) : (
            <Card>
              <div className="space-y-4">
                {recentEvents.map((event) => (
                  <div
                    key={event.id}
                    className="flex items-start gap-3 border-b border-gray-200 pb-4 last:border-b-0 last:pb-0 dark:border-gray-700"
                  >
                    <div className="bg-primary-100 dark:bg-primary-900 flex-shrink-0 rounded-lg p-2">
                      <Activity
                        className="text-primary-600 dark:text-primary-400 h-4 w-4"
                        aria-hidden="true"
                      />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex items-center gap-2">
                        <Badge color="info" size="sm">
                          {formatEventType(event.event_type)}
                        </Badge>
                        <Badge color="gray" size="sm">
                          {event.record_type}
                        </Badge>
                      </div>
                      <p className="truncate text-sm text-gray-600 dark:text-gray-400">
                        Record ID: {event.record_id}
                      </p>
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-500">
                        {event.created_at ? formatDate(event.created_at) : "Unknown"}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </section>

        {/* Quick Access Cards */}
        <section className="mb-12" aria-labelledby="quick-access">
          <h2
            id="quick-access"
            className="mb-6 text-2xl font-bold text-gray-900 dark:text-white"
          >
            Quick Access
          </h2>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            <QuickActionCard
              title="Ontology Structure"
              description="Browse and manage taxonomies, concept schemes, and classes"
              icon={Network}
              href="/app/taxonomies"
            />
            <QuickActionCard
              title="Analytics"
              description="View LLM traceability, performance metrics, and system analytics"
              icon={BarChart3}
              href="/app/monitoring/analytics"
            />
            <QuickActionCard
              title="Datasets"
              description="Manage your data sources and dataset configurations"
              icon={Database}
              href="/app/datasets"
            />
            <QuickActionCard
              title="Property Definitions"
              description="Define and manage semantic relationships between classes"
              icon={GitBranch}
              href="/app/properties"
            />
            <QuickActionCard
              title="Pipeline Configuration"
              description="Configure and manage LLM pipeline flavors for different tasks"
              icon={Activity}
              href="/app/config/pipelines"
            />
            <QuickActionCard
              title="System Configuration"
              description="Manage system settings, models, and data sources"
              icon={FileText}
              href="/app/config"
            />
          </div>
        </section>

        {/* Getting Started Section */}
        <Card className="from-primary-50 to-primary-100 border-primary-200 bg-gradient-to-r dark:border-gray-600 dark:from-gray-800 dark:to-gray-700">
          <div className="py-6 text-center">
            <h2 className="mb-3 text-2xl font-bold text-gray-900 dark:text-white">
              Ready to get started?
            </h2>
            <p className="mb-6 text-gray-600 dark:text-gray-300">
              Explore your knowledge graph and start building with Context
              Studio
            </p>
            <Link to="/app">
              <Button size="lg" color="primary">
                Open Dashboard
                <ArrowRight className="ml-2 h-5 w-5" aria-hidden="true" />
              </Button>
            </Link>
          </div>
        </Card>
      </div>

      {/* Footer */}
      <footer className="mt-12 border-t border-gray-200 bg-white py-8 dark:border-gray-700 dark:bg-gray-800">
        <div className="mx-auto max-w-7xl px-4 text-center">
          <p className="text-gray-600 dark:text-gray-400">
            Context Studio - Local-first knowledge graph and RAG platform
          </p>
        </div>
      </footer>
    </main>
  );
}
