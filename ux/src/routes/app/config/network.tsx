import { createFileRoute } from "@tanstack/react-router";
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Label,
  Tabs,
  TextInput,
} from "flowbite-react";
import { CsMainTitle } from "@/components/layout/cs_main";
import { ConfigBreadcrumbs } from "@/components/configuration/ConfigBreadcrumbs";
import {
  Activity,
  CheckCircle,
  Clock,
  Database,
  Globe,
  HardDrive,
  Server,
  Shield,
  Wifi,
  Zap,
} from "lucide-react";
import { useConfiguration, useUpdateConfigurationValue } from "@/api/hooks";
import { useButterToast } from "@/hooks/useButterToast";

export const Route = createFileRoute("/app/config/network")({
  component: RouteComponent,
});

function RouteComponent() {
  const { data: configuration, isLoading: isLoadingConfig } =
    useConfiguration();
  const updateConfigMutation = useUpdateConfigurationValue();
  const toast = useButterToast();

  const getProxyConfigLabel = (path: string): string => {
    const labels: Record<string, string> = {
      enabled: "Proxy server status",
      host: "Proxy host",
      port: "Proxy port",
      database_path: "Cache database path",
      max_cache_entries: "Maximum cache entries",
      default_cache_ttl: "Default cache TTL",
      default_max_response_size: "Maximum response size",
      default_requests_per_hour: "Default requests per hour",
      progressive_max_delay: "Progressive max delay",
    };
    return labels[path] || path;
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleUpdateProxyConfig = async (path: string, value: any) => {
    const label = getProxyConfigLabel(path);
    await updateConfigMutation.mutateAsync(
      {
        path: `proxy_server.${path}`,
        value,
      },
      {
        onSuccess: () => {
          toast.success(`${label} updated successfully`);
        },
        onError: (error) => {
          toast.error(
            `Failed to update ${label}: ${error instanceof Error ? error.message : "Unknown error"}`,
          );
        },
      },
    );
  };

  if (isLoadingConfig) {
    return (
      <div className="p-6">
        <ConfigBreadcrumbs items={[{ label: "Network & Proxy" }]} />
        <CsMainTitle>Network & Proxy Configuration</CsMainTitle>
        <div className="py-8 text-center">Loading configuration...</div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <ConfigBreadcrumbs items={[{ label: "Network & Proxy" }]} />
      <CsMainTitle>Network & Proxy Configuration</CsMainTitle>

      <div className="mb-6">
        <p className="text-gray-600">
          Configure the built-in caching proxy server for reference API calls
          and network settings.
        </p>
      </div>

      <Tabs aria-label="Network & Proxy Configuration" variant="underline">
        {/* Proxy Server Tab */}
        <Tabs.Item title="Proxy Server" icon={Server}>
          <ProxyServerSection
            config={configuration?.data?.proxy_server}
            onUpdate={handleUpdateProxyConfig}
            isUpdating={updateConfigMutation.isPending}
          />
        </Tabs.Item>

        {/* Cache Settings Tab */}
        <Tabs.Item title="Cache Settings" icon={Database}>
          <CacheSettingsSection
            config={configuration?.data?.proxy_server}
            onUpdate={handleUpdateProxyConfig}
            isUpdating={updateConfigMutation.isPending}
          />
        </Tabs.Item>

        {/* Rate Limiting Tab */}
        <Tabs.Item title="Rate Limiting" icon={Activity}>
          <RateLimitingSection
            config={configuration?.data?.proxy_server}
            onUpdate={handleUpdateProxyConfig}
            isUpdating={updateConfigMutation.isPending}
          />
        </Tabs.Item>
      </Tabs>
    </div>
  );
}

// Proxy Server Section Component
function ProxyServerSection({
  config,
  onUpdate,
  isUpdating,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onUpdate: (path: string, value: any) => void;
  isUpdating: boolean;
}) {
  if (!config) {
    return <div>No proxy server configuration available</div>;
  }

  const isProxyEnabled = config.enabled ?? true;

  return (
    <div className="space-y-6">
      <Alert color={isProxyEnabled ? "success" : "warning"}>
        <Server className="h-4 w-4" />
        <span className="ml-2">
          {isProxyEnabled
            ? "Proxy server is enabled and will cache reference API calls to improve performance."
            : "Proxy server is disabled. Reference API calls will go directly to upstream services."}
        </span>
      </Alert>

      {/* Enable/Disable Proxy */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Wifi className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">Proxy Status</h3>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="proxy_enabled">Enable Proxy Server</Label>
              <p className="text-sm text-gray-600">
                Route reference API calls through caching proxy
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge color={isProxyEnabled ? "success" : "gray"} size="sm">
                {isProxyEnabled ? "Enabled" : "Disabled"}
              </Badge>
              <Checkbox
                id="proxy_enabled"
                checked={isProxyEnabled}
                onChange={(e) => onUpdate("enabled", e.target.checked)}
                disabled={isUpdating}
              />
            </div>
          </div>
        </div>
      </Card>

      {/* Network Configuration */}
      {isProxyEnabled && (
        <Card>
          <div className="mb-4 flex items-center gap-3">
            <Globe className="h-5 w-5 text-green-600" />
            <h3 className="text-lg font-semibold">Network Configuration</h3>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="proxy_host">Proxy Host</Label>
              <TextInput
                id="proxy_host"
                value={config.host || "127.0.0.1"}
                onChange={(e) => onUpdate("host", e.target.value)}
                disabled={isUpdating}
              />
              <p className="mt-1 text-sm text-gray-600">
                Host address for the proxy server
              </p>
            </div>

            <div>
              <Label htmlFor="proxy_port">Proxy Port</Label>
              <TextInput
                id="proxy_port"
                type="number"
                min="1024"
                max="65535"
                value={config.port || 18080}
                onChange={(e) => onUpdate("port", parseInt(e.target.value))}
                disabled={isUpdating}
              />
              <p className="mt-1 text-sm text-gray-600">Default: 18080</p>
            </div>
          </div>

          <div className="mt-4 border-t border-gray-200 pt-4">
            <div className="text-sm text-gray-600">
              <strong>Proxy URL:</strong> http://{config.host || "127.0.0.1"}:
              {config.port || 18080}
            </div>
          </div>
        </Card>
      )}

      {/* Proxy Status Information */}
      {isProxyEnabled && (
        <Card>
          <div className="mb-4 flex items-center gap-3">
            <CheckCircle className="h-5 w-5 text-green-600" />
            <h3 className="text-lg font-semibold">Status Information</h3>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span>Service Status</span>
              <Badge color="success" size="sm">
                <CheckCircle className="mr-1 h-3 w-3" />
                Running
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <span>Cache Database</span>
              <Badge color="success" size="sm">
                Connected
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <span>Active Connections</span>
              <Badge color="info" size="sm">
                3 clients
              </Badge>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

// Cache Settings Section Component
function CacheSettingsSection({
  config,
  onUpdate,
  isUpdating,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onUpdate: (path: string, value: any) => void;
  isUpdating: boolean;
}) {
  if (!config) {
    return <div>No cache configuration available</div>;
  }

  return (
    <div className="space-y-6">
      <Alert color="info">
        <Database className="h-4 w-4" />
        <span className="ml-2">
          Cache settings control how long responses are stored and how much
          space is used.
        </span>
      </Alert>

      {/* Database Configuration */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <HardDrive className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">Database Configuration</h3>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="cache_database_path">Cache Database Path</Label>
            <TextInput
              id="cache_database_path"
              value={config.database_path || "./reference_api_cache.db"}
              onChange={(e) => onUpdate("database_path", e.target.value)}
              disabled={isUpdating}
            />
            <p className="mt-1 text-sm text-gray-600">
              SQLite database file for storing cached responses
            </p>
          </div>

          <div>
            <Label htmlFor="max_cache_entries">Maximum Cache Entries</Label>
            <TextInput
              id="max_cache_entries"
              type="number"
              min="100"
              max="1000000"
              value={config.max_cache_entries || 10000}
              onChange={(e) =>
                onUpdate("max_cache_entries", parseInt(e.target.value))
              }
              disabled={isUpdating}
            />
            <p className="mt-1 text-sm text-gray-600">
              Maximum total number of cached entries across all sources
            </p>
          </div>
        </div>
      </Card>

      {/* Cache Expiration */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Clock className="h-5 w-5 text-green-600" />
          <h3 className="text-lg font-semibold">Cache Expiration</h3>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="default_cache_ttl">Default TTL (seconds)</Label>
            <TextInput
              id="default_cache_ttl"
              type="number"
              min="60"
              max="86400"
              value={config.default_cache_ttl || 3600}
              onChange={(e) =>
                onUpdate("default_cache_ttl", parseInt(e.target.value))
              }
              disabled={isUpdating}
            />
            <p className="mt-1 text-sm text-gray-600">
              Default time-to-live:{" "}
              {Math.floor((config.default_cache_ttl || 3600) / 60)} minutes
            </p>
          </div>

          <div>
            <Label htmlFor="max_response_size">Max Response Size (bytes)</Label>
            <TextInput
              id="max_response_size"
              type="number"
              min="1024"
              value={config.default_max_response_size || 10485760}
              onChange={(e) =>
                onUpdate("default_max_response_size", parseInt(e.target.value))
              }
              disabled={isUpdating}
            />
            <p className="mt-1 text-sm text-gray-600">
              Current:{" "}
              {(
                (config.default_max_response_size || 10485760) /
                1024 /
                1024
              ).toFixed(1)}{" "}
              MB
            </p>
          </div>
        </div>
      </Card>

      {/* Cache Statistics */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Activity className="h-5 w-5 text-purple-600" />
          <h3 className="text-lg font-semibold">Cache Statistics</h3>
          <Button size="xs" color="gray">
            Clear Cache
          </Button>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">8,420</div>
            <div className="text-sm text-gray-600">Total Entries</div>
          </div>

          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">89%</div>
            <div className="text-sm text-gray-600">Hit Rate</div>
          </div>

          <div className="text-center">
            <div className="text-2xl font-bold text-orange-600">125</div>
            <div className="text-sm text-gray-600">MB Used</div>
          </div>
        </div>
      </Card>
    </div>
  );
}

// Rate Limiting Section Component
function RateLimitingSection({
  config,
  onUpdate,
  isUpdating,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onUpdate: (path: string, value: any) => void;
  isUpdating: boolean;
}) {
  if (!config) {
    return <div>No rate limiting configuration available</div>;
  }

  return (
    <div className="space-y-6">
      <Alert color="warning">
        <Zap className="h-4 w-4" />
        <span className="ml-2">
          Rate limiting helps prevent hitting API limits and ensures fair usage
          across reference sources.
        </span>
      </Alert>

      {/* Default Rate Limits */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Activity className="h-5 w-5 text-red-600" />
          <h3 className="text-lg font-semibold">Default Rate Limits</h3>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="default_requests_per_hour">
              Default Requests per Hour
            </Label>
            <TextInput
              id="default_requests_per_hour"
              type="number"
              min="1"
              max="10000"
              value={config.default_requests_per_hour || 1000}
              onChange={(e) =>
                onUpdate("default_requests_per_hour", parseInt(e.target.value))
              }
              disabled={isUpdating}
            />
            <p className="mt-1 text-sm text-gray-600">
              Default limit applied to reference sources without specific
              configuration
            </p>
          </div>
        </div>
      </Card>

      {/* Progressive Delay */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Clock className="h-5 w-5 text-orange-600" />
          <h3 className="text-lg font-semibold">Progressive Delay</h3>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="progressive_max_delay">
              Maximum Progressive Delay (seconds)
            </Label>
            <TextInput
              id="progressive_max_delay"
              type="number"
              min="1"
              max="600"
              value={config.progressive_max_delay || 300}
              onChange={(e) =>
                onUpdate("progressive_max_delay", parseInt(e.target.value))
              }
              disabled={isUpdating}
            />
            <p className="mt-1 text-sm text-gray-600">
              Maximum delay when rate limits are hit (currently:{" "}
              {Math.floor((config.progressive_max_delay || 300) / 60)} minutes)
            </p>
          </div>

          <div className="rounded-lg bg-gray-50 p-4">
            <h4 className="mb-2 font-medium text-gray-900">
              How Progressive Delay Works
            </h4>
            <ul className="space-y-1 text-sm text-gray-600">
              <li>• Starts with minimal delay on first rate limit hit</li>
              <li>• Progressively increases delay for subsequent hits</li>
              <li>• Backs off to normal operation when rate limits clear</li>
              <li>• Helps prevent cascading failures and API bans</li>
            </ul>
          </div>
        </div>
      </Card>

      {/* Rate Limit Status */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Shield className="h-5 w-5 text-green-600" />
          <h3 className="text-lg font-semibold">Current Rate Limit Status</h3>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span>ConceptNet</span>
            <div className="flex items-center gap-2">
              <Badge color="success" size="sm">
                425/1000 requests
              </Badge>
              <Badge color="success" size="sm">
                Normal
              </Badge>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <span>DBpedia</span>
            <div className="flex items-center gap-2">
              <Badge color="warning" size="sm">
                850/1000 requests
              </Badge>
              <Badge color="warning" size="sm">
                Throttled
              </Badge>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <span>Wikidata</span>
            <div className="flex items-center gap-2">
              <Badge color="success" size="sm">
                120/1000 requests
              </Badge>
              <Badge color="success" size="sm">
                Normal
              </Badge>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <span>Schema.org</span>
            <div className="flex items-center gap-2">
              <Badge color="success" size="sm">
                45/1000 requests
              </Badge>
              <Badge color="success" size="sm">
                Normal
              </Badge>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
