import { createFileRoute, Link } from "@tanstack/react-router";
import { Card, Badge } from "flowbite-react";
import {
  Brain,
  Database,
  Settings,
  Shield,
  Zap,
  Globe,
  Server,
  Cog,
  ExternalLink,
} from "lucide-react";
import { CsMainTitle } from "@/components/layout/cs_main";
import { ConfigBreadcrumbs } from "@/components/configuration/ConfigBreadcrumbs";
import { useProvidersStatus, useValidateConfiguration } from "@/api/hooks";

export const Route = createFileRoute("/app/config/")({
  component: RouteComponent,
});

function RouteComponent() {
  const { data: providersStatus } = useProvidersStatus();
  const { data: validationStatus } = useValidateConfiguration();

  // Count enabled providers and models
  const enabledProviders = providersStatus
    ? Object.values(providersStatus.providers).filter(
        (p) => p.enabled_models > 0,
      ).length
    : 0;

  const totalEnabledModels = providersStatus
    ? Object.values(providersStatus.providers).reduce(
        (sum, p) => sum + p.enabled_models,
        0,
      )
    : 0;

  const hasValidationIssues = validationStatus && !validationStatus.valid;

  return (
    <div className="p-6">
      <ConfigBreadcrumbs items={[]} />
      <CsMainTitle>Configuration</CsMainTitle>

      {/* Status Overview */}
      <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <div className="flex items-center gap-3">
            <Brain className="h-8 w-8 text-blue-600" />
            <div>
              <h3 className="text-lg font-semibold">LLM Models</h3>
              <p className="text-sm text-gray-600">
                {totalEnabledModels} models across {enabledProviders} providers
              </p>
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <Settings className="h-8 w-8 text-green-600" />
            <div>
              <h3 className="text-lg font-semibold">System Status</h3>
              <div className="flex items-center gap-2">
                <Badge
                  color={hasValidationIssues ? "failure" : "success"}
                  size="sm"
                >
                  {hasValidationIssues ? "Issues Found" : "Healthy"}
                </Badge>
                {hasValidationIssues && (
                  <span className="text-sm text-red-600">
                    {validationStatus?.errors.length} issue(s)
                  </span>
                )}
              </div>
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <Zap className="h-8 w-8 text-purple-600" />
            <div>
              <h3 className="text-lg font-semibold">Quick Actions</h3>
              <p className="text-sm text-gray-600">
                Manage settings efficiently
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Configuration Sections */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* LLM Models - Priority Section */}
        <Link to="/app/config/models" className="group">
          <Card className="h-full transition-all duration-200 group-hover:bg-blue-50 hover:border-blue-300 hover:shadow-lg">
            <div className="flex items-start gap-4">
              <div className="rounded-lg bg-blue-100 p-3 transition-colors group-hover:bg-blue-200">
                <Brain className="h-6 w-6 text-blue-600" />
              </div>
              <div className="flex-1">
                <div className="mb-2 flex items-center gap-2">
                  <h3 className="text-lg font-semibold">LLM Models</h3>
                  <Badge color="info" size="sm">
                    Priority
                  </Badge>
                </div>
                <p className="mb-3 text-sm text-gray-600">
                  Manage available models, configure providers, and view model
                  capabilities.
                </p>
                <div className="text-sm text-gray-500">
                  • Available Models • Provider Configuration • Model
                  Capabilities
                </div>
              </div>
              <ExternalLink className="h-4 w-4 text-gray-400 transition-colors group-hover:text-blue-600" />
            </div>
          </Card>
        </Link>

        {/* Data Sources */}
        <Link to="/app/config/data-sources" className="group">
          <Card className="h-full transition-all duration-200 group-hover:bg-green-50 hover:border-green-300 hover:shadow-lg">
            <div className="flex items-start gap-4">
              <div className="rounded-lg bg-green-100 p-3 transition-colors group-hover:bg-green-200">
                <Database className="h-6 w-6 text-green-600" />
              </div>
              <div className="flex-1">
                <h3 className="mb-2 text-lg font-semibold">Data Sources</h3>
                <p className="mb-3 text-sm text-gray-600">
                  Configure reference APIs and database settings.
                </p>
                <div className="text-sm text-gray-500">
                  • Reference APIs • Database Settings
                </div>
              </div>
              <ExternalLink className="h-4 w-4 text-gray-400 transition-colors group-hover:text-green-600" />
            </div>
          </Card>
        </Link>

        {/* Processing */}
        <Link to="/app/config/processing" className="group">
          <Card className="h-full transition-all duration-200 group-hover:bg-purple-50 hover:border-purple-300 hover:shadow-lg">
            <div className="flex items-start gap-4">
              <div className="rounded-lg bg-purple-100 p-3 transition-colors group-hover:bg-purple-200">
                <Zap className="h-6 w-6 text-purple-600" />
              </div>
              <div className="flex-1">
                <h3 className="mb-2 text-lg font-semibold">Processing</h3>
                <p className="mb-3 text-sm text-gray-600">
                  NLP configuration and pipeline defaults.
                </p>
                <div className="text-sm text-gray-500">
                  • NLP Configuration • Pipeline Defaults
                </div>
              </div>
              <ExternalLink className="h-4 w-4 text-gray-400 transition-colors group-hover:text-purple-600" />
            </div>
          </Card>
        </Link>

        {/* System */}
        <Link to="/app/config/system" className="group">
          <Card className="h-full transition-all duration-200 group-hover:bg-orange-50 hover:border-orange-300 hover:shadow-lg">
            <div className="flex items-start gap-4">
              <div className="rounded-lg bg-orange-100 p-3 transition-colors group-hover:bg-orange-200">
                <Server className="h-6 w-6 text-orange-600" />
              </div>
              <div className="flex-1">
                <h3 className="mb-2 text-lg font-semibold">System</h3>
                <p className="mb-3 text-sm text-gray-600">
                  Server settings, logging, and security configuration.
                </p>
                <div className="text-sm text-gray-500">
                  • Server Settings • Logging • Security
                </div>
              </div>
              <ExternalLink className="h-4 w-4 text-gray-400 transition-colors group-hover:text-orange-600" />
            </div>
          </Card>
        </Link>

        {/* Network & Proxy */}
        <Link to="/app/config/network" className="group">
          <Card className="h-full transition-all duration-200 group-hover:bg-cyan-50 hover:border-cyan-300 hover:shadow-lg">
            <div className="flex items-start gap-4">
              <div className="rounded-lg bg-cyan-100 p-3 transition-colors group-hover:bg-cyan-200">
                <Globe className="h-6 w-6 text-cyan-600" />
              </div>
              <div className="flex-1">
                <h3 className="mb-2 text-lg font-semibold">Network & Proxy</h3>
                <p className="mb-3 text-sm text-gray-600">
                  Proxy server and caching configuration.
                </p>
                <div className="text-sm text-gray-500">
                  • Proxy Configuration • Cache Settings
                </div>
              </div>
              <ExternalLink className="h-4 w-4 text-gray-400 transition-colors group-hover:text-cyan-600" />
            </div>
          </Card>
        </Link>

        {/* Advanced */}
        <Link to="/app/config/advanced" className="group">
          <Card className="h-full transition-all duration-200 group-hover:bg-gray-50 hover:border-gray-300 hover:shadow-lg">
            <div className="flex items-start gap-4">
              <div className="rounded-lg bg-gray-100 p-3 transition-colors group-hover:bg-gray-200">
                <Cog className="h-6 w-6 text-gray-600" />
              </div>
              <div className="flex-1">
                <div className="mb-2 flex items-center gap-2">
                  <h3 className="text-lg font-semibold">Advanced</h3>
                  <Badge color="warning" size="sm">
                    Expert
                  </Badge>
                </div>
                <p className="mb-3 text-sm text-gray-600">
                  Raw configuration editor and advanced tools.
                </p>
                <div className="text-sm text-gray-500">
                  • Raw Configuration • Import/Export • Reset
                </div>
              </div>
              <ExternalLink className="h-4 w-4 text-gray-400 transition-colors group-hover:text-gray-600" />
            </div>
          </Card>
        </Link>
      </div>

      {/* Validation Issues Alert */}
      {hasValidationIssues && (
        <Card className="mt-6 border-red-200 bg-red-50">
          <div className="flex items-start gap-3">
            <Shield className="mt-0.5 h-5 w-5 text-red-600" />
            <div>
              <h4 className="mb-1 font-semibold text-red-800">
                Configuration Issues Detected
              </h4>
              <div className="space-y-1 text-sm text-red-700">
                {validationStatus?.errors.map((error, index) => (
                  <div key={index}>• {error}</div>
                ))}
              </div>
              <Link
                to="/app/config/advanced"
                className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-red-800 hover:text-red-900"
              >
                Review Configuration
                <ExternalLink className="h-3 w-3" />
              </Link>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
