import { createFileRoute } from "@tanstack/react-router";
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Label,
  Progress,
  Select,
  Tabs,
  TextInput,
} from "flowbite-react";
import { CsMainTitle } from "@/components/layout/cs_main";
import { ConfigBreadcrumbs } from "@/components/configuration/ConfigBreadcrumbs";
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Database,
  FileText,
  Globe,
  Lock,
  Monitor,
  RotateCcw,
  Server,
  Settings,
  Shield,
} from "lucide-react";
import { useConfiguration, useUpdateConfigurationValue } from "@/api/hooks";
import { useButterToast } from "@/hooks/useButterToast";

export const Route = createFileRoute("/app/config/system")({
  component: RouteComponent,
});

const LOG_LEVELS = [
  {
    value: "DEBUG",
    label: "Debug",
    description: "Detailed information for diagnosing problems",
  },
  {
    value: "INFO",
    label: "Info",
    description: "General information about system operation",
  },
  {
    value: "WARNING",
    label: "Warning",
    description: "Warning messages about potential issues",
  },
  {
    value: "ERROR",
    label: "Error",
    description: "Error events that might still allow operation",
  },
  {
    value: "CRITICAL",
    label: "Critical",
    description: "Critical errors that may abort operation",
  },
];

function RouteComponent() {
  const { data: configuration, isLoading: isLoadingConfig } =
    useConfiguration();
  const updateConfigMutation = useUpdateConfigurationValue();
  const toast = useButterToast();

  const getConfigLabel = (path: string): string => {
    const labels: Record<string, string> = {
      host: "Host address",
      port: "Port",
      cors_origins: "CORS origins",
      reload: "Auto-reload",
      access_log: "Access logs",
      log_level: "Server log level",
      level: "Log level",
      enable_console: "Console logging",
      enable_file: "File logging",
      file_path: "Log file path",
      format: "Log format",
      date_format: "Date format",
      max_file_size: "Max file size",
      backup_count: "Backup count",
      require_secure_key: "Secure key requirement",
      secure_key: "Secure key",
      api_key_header: "API key header",
      log_security_events: "Security event logging",
    };
    return labels[path] || path;
  };

   
  const handleUpdateServerConfig = async (path: string, value: any) => {
    const label = getConfigLabel(path);
    await updateConfigMutation.mutateAsync(
      {
        path: `server.${path}`,
        value,
      },
      {
        onSuccess: () => {
          toast.success(`Server ${label} updated successfully`);
        },
        onError: (error) => {
          toast.error(
            `Failed to update server ${label}: ${error instanceof Error ? error.message : "Unknown error"}`,
          );
        },
      },
    );
  };

   
  const handleUpdateLoggingConfig = async (path: string, value: any) => {
    const label = getConfigLabel(path);
    await updateConfigMutation.mutateAsync(
      {
        path: `logging.${path}`,
        value,
      },
      {
        onSuccess: () => {
          toast.success(`Logging ${label} updated successfully`);
        },
        onError: (error) => {
          toast.error(
            `Failed to update logging ${label}: ${error instanceof Error ? error.message : "Unknown error"}`,
          );
        },
      },
    );
  };

   
  const handleUpdateSecurityConfig = async (path: string, value: any) => {
    const label = getConfigLabel(path);
    await updateConfigMutation.mutateAsync(
      {
        path: `security.${path}`,
        value,
      },
      {
        onSuccess: () => {
          toast.success(`Security ${label} updated successfully`);
        },
        onError: (error) => {
          toast.error(
            `Failed to update security ${label}: ${error instanceof Error ? error.message : "Unknown error"}`,
          );
        },
      },
    );
  };

  if (isLoadingConfig) {
    return (
      <div className="p-6">
        <ConfigBreadcrumbs items={[{ label: "System" }]} />
        <CsMainTitle>System Configuration</CsMainTitle>
        <div className="py-8 text-center">Loading configuration...</div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <ConfigBreadcrumbs items={[{ label: "System" }]} />
      <CsMainTitle>System Configuration</CsMainTitle>

      <div className="mb-6">
        <p className="text-gray-600">
          Server settings, logging, security, and system monitoring
          configuration.
        </p>
      </div>

      <Tabs aria-label="System Configuration" variant="underline">
        {/* Server Settings Tab */}
        <Tabs.Item title="Server Settings" icon={Server}>
          <ServerSettingsSection
            config={configuration?.data?.server}
            onUpdate={handleUpdateServerConfig}
            isUpdating={updateConfigMutation.isPending}
          />
        </Tabs.Item>

        {/* Logging Configuration Tab */}
        <Tabs.Item title="Logging" icon={FileText}>
          <LoggingConfigurationSection
            config={configuration?.data?.logging}
            onUpdate={handleUpdateLoggingConfig}
            isUpdating={updateConfigMutation.isPending}
          />
        </Tabs.Item>

        {/* Security Settings Tab */}
        <Tabs.Item title="Security" icon={Shield}>
          <SecuritySettingsSection
            config={configuration?.data?.security}
            onUpdate={handleUpdateSecurityConfig}
            isUpdating={updateConfigMutation.isPending}
          />
        </Tabs.Item>

        {/* Performance Monitoring Tab */}
        <Tabs.Item title="Performance" icon={Activity}>
          <PerformanceMonitoringSection />
        </Tabs.Item>
      </Tabs>
    </div>
  );
}

// Server Settings Section Component
function ServerSettingsSection({
  config,
  onUpdate,
  isUpdating,
}: {
   
  config: any;

   
  onUpdate: (path: string, value: any) => void;
  isUpdating: boolean;
}) {
  if (!config) {
    return <div>No server configuration available</div>;
  }

  return (
    <div className="space-y-6">
      <Alert color="warning">
        <AlertTriangle className="h-4 w-4" />
        <span className="ml-2">
          Server configuration changes require a restart to take effect.
        </span>
      </Alert>

      {/* Network Configuration */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Globe className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">Network Configuration</h3>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="server_host">Host Address</Label>
            <TextInput
              id="server_host"
              value={config.host || "127.0.0.1"}
              onChange={(e) => onUpdate("host", e.target.value)}
              disabled={isUpdating}
            />
            <p className="mt-1 text-sm text-gray-600">
              Server bind address (use 0.0.0.0 for external access)
            </p>
          </div>

          <div>
            <Label htmlFor="server_port">Port</Label>
            <TextInput
              id="server_port"
              type="number"
              min="1024"
              max="65535"
              value={config.port || 8000}
              onChange={(e) => onUpdate("port", parseInt(e.target.value))}
              disabled={isUpdating}
            />
          </div>
        </div>
      </Card>

      {/* CORS Configuration */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Shield className="h-5 w-5 text-green-600" />
          <h3 className="text-lg font-semibold">CORS Configuration</h3>
        </div>

        <div>
          <Label htmlFor="cors_origins">Allowed Origins</Label>
          <TextInput
            id="cors_origins"
            value={config.cors_origins?.join(", ") || "*"}
            onChange={(e) =>
              onUpdate(
                "cors_origins",
                e.target.value.split(",").map((s) => s.trim()),
              )
            }
            disabled={isUpdating}
          />
          <p className="mt-1 text-sm text-gray-600">
            Comma-separated list of allowed CORS origins (* for all)
          </p>
        </div>
      </Card>

      {/* Development Settings */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Settings className="h-5 w-5 text-orange-600" />
          <h3 className="text-lg font-semibold">Development Settings</h3>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="auto_reload">Auto-reload</Label>
              <p className="text-sm text-gray-600">
                Automatically reload server on code changes
              </p>
            </div>
            <Checkbox
              id="auto_reload"
              checked={config.reload ?? true}
              onChange={(e) => onUpdate("reload", e.target.checked)}
              disabled={isUpdating}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="access_log">Access Logs</Label>
              <p className="text-sm text-gray-600">
                Enable detailed HTTP access logging
              </p>
            </div>
            <Checkbox
              id="access_log"
              checked={config.access_log ?? false}
              onChange={(e) => onUpdate("access_log", e.target.checked)}
              disabled={isUpdating}
            />
          </div>

          <div>
            <Label htmlFor="server_log_level">Server Log Level</Label>
            <Select
              id="server_log_level"
              value={config.log_level || "INFO"}
              onChange={(e) => onUpdate("log_level", e.target.value)}
              disabled={isUpdating}
            >
              {LOG_LEVELS.map((level) => (
                <option key={level.value} value={level.value}>
                  {level.label}
                </option>
              ))}
            </Select>
          </div>
        </div>
      </Card>
    </div>
  );
}

// Logging Configuration Section Component
function LoggingConfigurationSection({
  config,
  onUpdate,
  isUpdating,
}: {
   
  config: any;

   
  onUpdate: (path: string, value: any) => void;
  isUpdating: boolean;
}) {
  if (!config) {
    return <div>No logging configuration available</div>;
  }

  const currentLogLevel =
    LOG_LEVELS.find((l) => l.value === config.level) || LOG_LEVELS[1];

  return (
    <div className="space-y-6">
      {/* Log Level Configuration */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <FileText className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">Log Level Configuration</h3>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="log_level">Log Level</Label>
            <Select
              id="log_level"
              value={config.level || "INFO"}
              onChange={(e) => onUpdate("level", e.target.value)}
              disabled={isUpdating}
            >
              {LOG_LEVELS.map((level) => (
                <option key={level.value} value={level.value}>
                  {level.label} - {level.description}
                </option>
              ))}
            </Select>
            <p className="mt-1 text-sm text-gray-600">
              Currently using:{" "}
              <span className="font-medium">{currentLogLevel.label}</span>
            </p>
          </div>
        </div>
      </Card>

      {/* Output Configuration */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Monitor className="h-5 w-5 text-green-600" />
          <h3 className="text-lg font-semibold">Output Configuration</h3>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="enable_console">Console Logging</Label>
              <p className="text-sm text-gray-600">
                Output logs to console/terminal
              </p>
            </div>
            <Checkbox
              id="enable_console"
              checked={config.enable_console ?? false}
              onChange={(e) => onUpdate("enable_console", e.target.checked)}
              disabled={isUpdating}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="enable_file">File Logging</Label>
              <p className="text-sm text-gray-600">
                Output logs to file system
              </p>
            </div>
            <Checkbox
              id="enable_file"
              checked={config.enable_file ?? true}
              onChange={(e) => onUpdate("enable_file", e.target.checked)}
              disabled={isUpdating}
            />
          </div>

          {config.enable_file && (
            <div>
              <Label htmlFor="file_path">Log File Path</Label>
              <TextInput
                id="file_path"
                value={config.file_path || "./logs/context_studio.log"}
                onChange={(e) => onUpdate("file_path", e.target.value)}
                disabled={isUpdating}
              />
            </div>
          )}
        </div>
      </Card>

      {/* Format Configuration */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Settings className="h-5 w-5 text-purple-600" />
          <h3 className="text-lg font-semibold">Format Configuration</h3>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="log_format">Log Format</Label>
            <TextInput
              id="log_format"
              value={
                config.format ||
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
              }
              onChange={(e) => onUpdate("format", e.target.value)}
              disabled={isUpdating}
            />
            <p className="mt-1 text-sm text-gray-600">
              Python logging format string
            </p>
          </div>

          <div>
            <Label htmlFor="date_format">Date Format</Label>
            <TextInput
              id="date_format"
              value={config.date_format || "%Y-%m-%d %H:%M:%S"}
              onChange={(e) => onUpdate("date_format", e.target.value)}
              disabled={isUpdating}
            />
            <p className="mt-1 text-sm text-gray-600">
              strftime format for timestamps
            </p>
          </div>
        </div>
      </Card>

      {/* File Rotation */}
      {config.enable_file && (
        <Card>
          <div className="mb-4 flex items-center gap-3">
            <RotateCcw className="h-5 w-5 text-orange-600" />
            <h3 className="text-lg font-semibold">File Rotation</h3>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="max_file_size">Max File Size (bytes)</Label>
              <TextInput
                id="max_file_size"
                type="number"
                min="1024"
                value={config.max_file_size || 10485760}
                onChange={(e) =>
                  onUpdate("max_file_size", parseInt(e.target.value))
                }
                disabled={isUpdating}
              />
              <p className="mt-1 text-sm text-gray-600">
                Current:{" "}
                {((config.max_file_size || 10485760) / 1024 / 1024).toFixed(1)}{" "}
                MB
              </p>
            </div>

            <div>
              <Label htmlFor="backup_count">Backup Files</Label>
              <TextInput
                id="backup_count"
                type="number"
                min="0"
                max="50"
                value={config.backup_count || 5}
                onChange={(e) =>
                  onUpdate("backup_count", parseInt(e.target.value))
                }
                disabled={isUpdating}
              />
              <p className="mt-1 text-sm text-gray-600">
                Number of rotated log files to keep
              </p>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

// Security Settings Section Component
function SecuritySettingsSection({
  config,
  onUpdate,
  isUpdating,
}: {
   
  config: any;

   
  onUpdate: (path: string, value: any) => void;
  isUpdating: boolean;
}) {
  if (!config) {
    return <div>No security configuration available</div>;
  }

  return (
    <div className="space-y-6">
      <Alert color="info">
        <Lock className="h-4 w-4" />
        <span className="ml-2">
          Security settings help protect your Context Studio instance from
          unauthorized access.
        </span>
      </Alert>

      {/* API Security */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Lock className="h-5 w-5 text-red-600" />
          <h3 className="text-lg font-semibold">API Security</h3>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="require_secure_key">Require Secure Key</Label>
              <p className="text-sm text-gray-600">
                Require API key for proxy access
              </p>
            </div>
            <Checkbox
              id="require_secure_key"
              checked={config.require_secure_key ?? false}
              onChange={(e) => onUpdate("require_secure_key", e.target.checked)}
              disabled={isUpdating}
            />
          </div>

          {config.require_secure_key && (
            <>
              <div>
                <Label htmlFor="secure_key">Secure Key</Label>
                <TextInput
                  id="secure_key"
                  type="password"
                  value={config.secure_key || ""}
                  onChange={(e) => onUpdate("secure_key", e.target.value)}
                  disabled={isUpdating}
                  placeholder="Enter secure API key"
                />
                <p className="mt-1 text-sm text-gray-600">
                  API key required for accessing the proxy service
                </p>
              </div>

              <div>
                <Label htmlFor="api_key_header">API Key Header</Label>
                <TextInput
                  id="api_key_header"
                  value={config.api_key_header || "X-API-Key"}
                  onChange={(e) => onUpdate("api_key_header", e.target.value)}
                  disabled={isUpdating}
                />
                <p className="mt-1 text-sm text-gray-600">
                  HTTP header name for API key authentication
                </p>
              </div>
            </>
          )}
        </div>
      </Card>

      {/* Security Logging */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <FileText className="h-5 w-5 text-orange-600" />
          <h3 className="text-lg font-semibold">Security Logging</h3>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="log_security_events">Log Security Events</Label>
              <p className="text-sm text-gray-600">
                Log authentication attempts and security events
              </p>
            </div>
            <Checkbox
              id="log_security_events"
              checked={config.log_security_events ?? false}
              onChange={(e) =>
                onUpdate("log_security_events", e.target.checked)
              }
              disabled={isUpdating}
            />
          </div>
        </div>
      </Card>

      {/* Security Status */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Shield className="h-5 w-5 text-green-600" />
          <h3 className="text-lg font-semibold">Security Status</h3>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span>API Key Protection</span>
            <Badge
              color={config.require_secure_key ? "success" : "warning"}
              size="sm"
            >
              {config.require_secure_key ? "Enabled" : "Disabled"}
            </Badge>
          </div>

          <div className="flex items-center justify-between">
            <span>Security Event Logging</span>
            <Badge
              color={config.log_security_events ? "success" : "gray"}
              size="sm"
            >
              {config.log_security_events ? "Enabled" : "Disabled"}
            </Badge>
          </div>

          <div className="flex items-center justify-between">
            <span>HTTPS Required</span>
            <Badge color="warning" size="sm">
              Not Configured
            </Badge>
          </div>
        </div>
      </Card>
    </div>
  );
}

// Performance Monitoring Section Component
function PerformanceMonitoringSection() {
  return (
    <div className="space-y-6">
      <Alert color="info">
        <Activity className="h-4 w-4" />
        <span className="ml-2">
          Monitor system performance and resource usage in real-time.
        </span>
      </Alert>

      {/* System Metrics */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Monitor className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">System Metrics</h3>
          <Button size="xs" color="gray">
            <RotateCcw className="mr-1 h-3 w-3" />
            Refresh
          </Button>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div>
            <Label>CPU Usage</Label>
            <div className="mt-2 flex items-center gap-3">
              <Progress progress={45} color="blue" className="flex-1" />
              <span className="text-sm font-medium">45%</span>
            </div>
          </div>

          <div>
            <Label>Memory Usage</Label>
            <div className="mt-2 flex items-center gap-3">
              <Progress progress={67} color="yellow" className="flex-1" />
              <span className="text-sm font-medium">67%</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Database Performance */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Database className="h-5 w-5 text-green-600" />
          <h3 className="text-lg font-semibold">Database Performance</h3>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">142</div>
            <div className="text-sm text-gray-600">Completed Operations</div>
          </div>

          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">7.5</div>
            <div className="text-sm text-gray-600">Avg Sync Time (min)</div>
          </div>

          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600">12,450</div>
            <div className="text-sm text-gray-600">Total Synced Changes</div>
          </div>
        </div>
      </Card>

      {/* Health Status */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <CheckCircle className="h-5 w-5 text-green-600" />
          <h3 className="text-lg font-semibold">System Health</h3>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span>API Service</span>
            <Badge color="success" size="sm">
              <CheckCircle className="mr-1 h-3 w-3" />
              Healthy
            </Badge>
          </div>

          <div className="flex items-center justify-between">
            <span>Database Connection</span>
            <Badge color="success" size="sm">
              <CheckCircle className="mr-1 h-3 w-3" />
              Connected
            </Badge>
          </div>

          <div className="flex items-center justify-between">
            <span>Proxy Service</span>
            <Badge color="success" size="sm">
              <CheckCircle className="mr-1 h-3 w-3" />
              Running
            </Badge>
          </div>

          <div className="flex items-center justify-between">
            <span>NLP Pipeline</span>
            <Badge color="warning" size="sm">
              <AlertTriangle className="mr-1 h-3 w-3" />
              Limited
            </Badge>
          </div>
        </div>
      </Card>
    </div>
  );
}
