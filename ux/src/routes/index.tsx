import { createFileRoute, Link } from "@tanstack/react-router";
import { Card, Button, Badge, Spinner, DarkThemeToggle } from "flowbite-react";
import {
  Database,
  GitBranch,
  FileText,
  Activity,
  BarChart3,
  Network,
  ArrowRight,
} from "lucide-react";
import { TreeChartPanel } from "@/components/panels/TreeChartPanel";
import {
  useLayerNodes,
  useDomainNodes,
  useTermNodes,
} from "@/api/hooks/structure_nodes/useStructureNodes";
import { useLLMTraceabilityHealth } from "@/api/hooks/llm/useLLMTraceability";

export const Route = createFileRoute("/")({
  component: HomeComponent,
});

/**
 * Stat card component for displaying key metrics
 */
const StatCard: React.FC<{
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
  description?: string;
}> = ({ title, value, icon, color, description }) => {
  return (
    <Card className="hover:shadow-lg transition-shadow">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <div className={`p-2 rounded-lg ${color}`}>{icon}</div>
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
              {title}
            </h3>
          </div>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">
            {value}
          </p>
          {description && (
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {description}
            </p>
          )}
        </div>
      </div>
    </Card>
  );
};

/**
 * Quick action card for navigating to key features
 */
const QuickActionCard: React.FC<{
  title: string;
  description: string;
  icon: React.ReactNode;
  link: string;
  iconColor: string;
}> = ({ title, description, icon, link, iconColor }) => {
  return (
    <Link to={link}>
      <Card className="h-full hover:shadow-lg hover:border-primary-600 dark:hover:border-primary-500 transition-all cursor-pointer group">
        <div className="flex items-start gap-4">
          <div className={`p-3 rounded-lg ${iconColor}`}>{icon}</div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1 group-hover:text-primary-600 dark:group-hover:text-primary-500 transition-colors">
              {title}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {description}
            </p>
          </div>
          <ArrowRight className="h-5 w-5 text-gray-400 group-hover:text-primary-600 dark:group-hover:text-primary-500 group-hover:translate-x-1 transition-all" />
        </div>
      </Card>
    </Link>
  );
};

function HomeComponent() {
  // Fetch knowledge graph statistics
  const { data: layers, isLoading: layersLoading } = useLayerNodes();
  const { data: domains, isLoading: domainsLoading } = useDomainNodes();
  const { data: terms, isLoading: termsLoading } = useTermNodes();

  // Fetch LLM system health
  const { data: healthData, isLoading: healthLoading } =
    useLLMTraceabilityHealth();

  const statsLoading = layersLoading || domainsLoading || termsLoading;

  // Calculate statistics
  const layerCount = layers?.length || 0;
  const domainCount = domains?.length || 0;
  const termCount = terms?.length || 0;
  const totalNodes = layerCount + domainCount + termCount;

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Dark mode toggle */}
      <div className="absolute top-4 right-4 z-50">
        <DarkThemeToggle />
      </div>

      {/* Hero Section */}
      <div className="bg-gradient-to-br from-primary-600 to-primary-800 dark:from-primary-700 dark:to-primary-900 text-white py-16 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-8">
            <h1 className="text-5xl font-bold mb-4">Context Studio</h1>
            <p className="text-xl text-primary-100 mb-6">
              Create and curate knowledge graphs for RAG and AI communication
            </p>
            <div className="flex items-center justify-center gap-4">
              <Link to="/app">
                <Button size="lg" color="light">
                  Get Started
                  <ArrowRight className="ml-2 h-5 w-5" />
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
          <div className="flex items-center justify-center gap-2 mt-6">
            <span className="text-sm text-primary-100">System Status:</span>
            {healthLoading ? (
              <Spinner size="sm" />
            ) : (
              <>
                <div
                  className={`h-2.5 w-2.5 rounded-full ${
                    healthData?.status === "healthy"
                      ? "bg-green-400"
                      : healthData?.status === "degraded"
                        ? "bg-yellow-400"
                        : "bg-red-400"
                  }`}
                />
                <Badge color={healthData?.status === "healthy" ? "success" : "warning"}>
                  {healthData?.status || "Unknown"}
                </Badge>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-12">
        {/* Statistics Grid */}
        <div className="mb-12">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
            Workspace Overview
          </h2>
          {statsLoading ? (
            <div className="flex justify-center py-12">
              <Spinner size="xl" />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <StatCard
                title="Total Nodes"
                value={totalNodes}
                icon={<Database className="h-5 w-5 text-blue-600" />}
                color="bg-blue-100 dark:bg-blue-900"
                description="All knowledge graph nodes"
              />
              <StatCard
                title="Layers"
                value={layerCount}
                icon={<GitBranch className="h-5 w-5 text-purple-600" />}
                color="bg-purple-100 dark:bg-purple-900"
                description="Top-level categories"
              />
              <StatCard
                title="Domains"
                value={domainCount}
                icon={<Network className="h-5 w-5 text-green-600" />}
                color="bg-green-100 dark:bg-green-900"
                description="Domain classifications"
              />
              <StatCard
                title="Terms"
                value={termCount}
                icon={<FileText className="h-5 w-5 text-orange-600" />}
                color="bg-orange-100 dark:bg-orange-900"
                description="Detailed concepts"
              />
            </div>
          )}
        </div>

        {/* Knowledge Graph Visualization */}
        <div className="mb-12">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
            Knowledge Graph Structure
          </h2>
          <Card>
            <div className="min-h-[400px]">
              <TreeChartPanel
                className="w-full"
                loadingComponent={
                  <div className="flex flex-col items-center justify-center py-12">
                    <Spinner size="xl" />
                    <p className="mt-4 text-gray-600 dark:text-gray-400">
                      Loading knowledge graph...
                    </p>
                  </div>
                }
              />
            </div>
          </Card>
        </div>

        {/* Quick Access Cards */}
        <div className="mb-12">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
            Quick Access
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <QuickActionCard
              title="Knowledge Graph"
              description="Browse and manage layers, domains, and terms in your knowledge graph"
              icon={<Network className="h-6 w-6 text-blue-600" />}
              link="/app/layers"
              iconColor="bg-blue-100 dark:bg-blue-900"
            />
            <QuickActionCard
              title="Analytics"
              description="View LLM traceability, performance metrics, and system analytics"
              icon={<BarChart3 className="h-6 w-6 text-purple-600" />}
              link="/app/monitoring/analytics"
              iconColor="bg-purple-100 dark:bg-purple-900"
            />
            <QuickActionCard
              title="Datasets"
              description="Manage your data sources and dataset configurations"
              icon={<Database className="h-6 w-6 text-green-600" />}
              link="/app/datasets"
              iconColor="bg-green-100 dark:bg-green-900"
            />
            <QuickActionCard
              title="Predicates"
              description="Define and manage semantic relationships between nodes"
              icon={<GitBranch className="h-6 w-6 text-orange-600" />}
              link="/app/predicates"
              iconColor="bg-orange-100 dark:bg-orange-900"
            />
            <QuickActionCard
              title="Pipeline Configuration"
              description="Configure and manage LLM pipeline flavors for different tasks"
              icon={<Activity className="h-6 w-6 text-pink-600" />}
              link="/app/config/pipelines"
              iconColor="bg-pink-100 dark:bg-pink-900"
            />
            <QuickActionCard
              title="System Configuration"
              description="Manage system settings, models, and data sources"
              icon={<FileText className="h-6 w-6 text-teal-600" />}
              link="/app/config"
              iconColor="bg-teal-100 dark:bg-teal-900"
            />
          </div>
        </div>

        {/* Getting Started Section */}
        <Card className="bg-gradient-to-r from-primary-50 to-primary-100 dark:from-gray-800 dark:to-gray-700 border-primary-200 dark:border-gray-600">
          <div className="text-center py-6">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">
              Ready to get started?
            </h2>
            <p className="text-gray-600 dark:text-gray-300 mb-6">
              Explore your knowledge graph and start building with Context Studio
            </p>
            <Link to="/app">
              <Button size="lg" color="primary">
                Open Dashboard
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
          </div>
        </Card>
      </div>

      {/* Footer */}
      <footer className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 py-8 mt-12">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className="text-gray-600 dark:text-gray-400">
            Context Studio - Local-first knowledge graph and RAG platform
          </p>
        </div>
      </footer>
    </main>
  );
}
