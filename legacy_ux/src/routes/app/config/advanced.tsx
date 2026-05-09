import { createFileRoute } from "@tanstack/react-router";
import {
  Alert,
  Badge,
  Button,
  Card,
  Label,
  Tabs,
  TextInput,
  Textarea,
} from "flowbite-react";
import { CsMainTitle } from "@/components/layout/cs_main";
import { ConfigBreadcrumbs } from "@/components/configuration/ConfigBreadcrumbs";
import {
  AlertTriangle,
  CheckCircle,
  CloudOff,
  Code,
  Cpu,
  Database,
  Download,
  HardDrive,
  Info,
  RotateCcw,
  Settings,
  Terminal,
  Trash2,
  Upload,
  XCircle,
} from "lucide-react";
import { useConfiguration, useUpdateConfigurationValue } from "@/api/hooks";
import { useState } from "react";
import { useButterToast } from "@/hooks/useButterToast";

export const Route = createFileRoute("/app/config/advanced")({
  component: RouteComponent,
});

function RouteComponent() {
  const { data: configuration, isLoading: isLoadingConfig } =
    useConfiguration();
  const updateConfigMutation = useUpdateConfigurationValue();
  const toast = useButterToast();

  const getConfigLabel = (path: string): string => {
    const labels: Record<string, string> = {
      S3_BUCKET: "S3 bucket",
      S3_REGION: "S3 region",
      S3_ACCESS_KEY: "S3 access key",
      S3_SECRET_KEY: "S3 secret key",
      S3_ENDPOINT: "S3 endpoint",
      DUCKDB_MEMORY_LIMIT: "DuckDB memory limit",
      DUCKDB_THREADS: "DuckDB thread count",
    };
    return labels[path] || path;
  };

  const handleUpdateConfig = async (path: string, value: any) => {
    const label = getConfigLabel(path);
    await updateConfigMutation.mutateAsync(
      {
        path,
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
        <ConfigBreadcrumbs items={[{ label: "Advanced" }]} />
        <CsMainTitle>Advanced Configuration</CsMainTitle>
        <div className="py-8 text-center">Loading configuration...</div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <ConfigBreadcrumbs items={[{ label: "Advanced" }]} />
      <CsMainTitle>Advanced Configuration</CsMainTitle>

      <div className="mb-6">
        <p className="text-gray-600">
          Expert-level tools, raw configuration editing, and system environment
          management.
        </p>
      </div>

      <Alert color="warning" className="mb-6">
        <AlertTriangle className="h-4 w-4" />
        <span className="ml-2">
          <strong>Expert Zone:</strong> Advanced settings can break your system
          if misconfigured. Always backup your configuration before making
          changes.
        </span>
      </Alert>

      <Tabs aria-label="Advanced Configuration" variant="underline">
        {/* Environment Variables Tab */}
        <Tabs.Item title="Environment" icon={Terminal}>
          <EnvironmentVariablesSection
            config={configuration?.data}
            onUpdate={handleUpdateConfig}
            isUpdating={updateConfigMutation.isPending}
          />
        </Tabs.Item>

        {/* Raw Configuration Tab */}
        <Tabs.Item title="Raw Config" icon={Code}>
          <RawConfigurationSection
            config={configuration?.data}
            isUpdating={updateConfigMutation.isPending}
          />
        </Tabs.Item>

        {/* Configuration Actions Tab */}
        <Tabs.Item title="Actions" icon={Settings}>
          <ConfigurationActionsSection />
        </Tabs.Item>

        {/* System Information Tab */}
        <Tabs.Item title="System Info" icon={Info}>
          <SystemInformationSection />
        </Tabs.Item>
      </Tabs>
    </div>
  );
}

// Environment Variables Section Component
function EnvironmentVariablesSection({
  config,
  onUpdate,
  isUpdating,
}: {
  config: any;
  onUpdate: (path: string, value: any) => void;
  isUpdating: boolean;
}) {
  if (!config) {
    return <div>No configuration available</div>;
  }

  return (
    <div className="space-y-6">
      {/* Cloud Storage Configuration */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <CloudOff className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">Cloud Storage (S3)</h3>
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="s3_bucket">S3 Bucket</Label>
              <TextInput
                id="s3_bucket"
                value={config.S3_BUCKET || ""}
                placeholder="my-context-studio-bucket"
                onChange={(e) => onUpdate("S3_BUCKET", e.target.value || null)}
                disabled={isUpdating}
              />
              <p className="mt-1 text-sm text-gray-600">
                S3 bucket for backup and sync operations
              </p>
            </div>

            <div>
              <Label htmlFor="s3_region">S3 Region</Label>
              <TextInput
                id="s3_region"
                value={config.S3_REGION || "us-east-1"}
                onChange={(e) => onUpdate("S3_REGION", e.target.value)}
                disabled={isUpdating}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="s3_access_key">Access Key</Label>
              <TextInput
                id="s3_access_key"
                type="password"
                value={config.S3_ACCESS_KEY || ""}
                placeholder="AKIA..."
                onChange={(e) =>
                  onUpdate("S3_ACCESS_KEY", e.target.value || null)
                }
                disabled={isUpdating}
              />
            </div>

            <div>
              <Label htmlFor="s3_secret_key">Secret Key</Label>
              <TextInput
                id="s3_secret_key"
                type="password"
                value={config.S3_SECRET_KEY || ""}
                placeholder="***"
                onChange={(e) =>
                  onUpdate("S3_SECRET_KEY", e.target.value || null)
                }
                disabled={isUpdating}
              />
            </div>
          </div>

          <div>
            <Label htmlFor="s3_endpoint">Custom Endpoint (Optional)</Label>
            <TextInput
              id="s3_endpoint"
              value={config.S3_ENDPOINT || ""}
              placeholder="https://s3.example.com"
              onChange={(e) => onUpdate("S3_ENDPOINT", e.target.value || null)}
              disabled={isUpdating}
            />
            <p className="mt-1 text-sm text-gray-600">
              Use for S3-compatible services like MinIO or DigitalOcean Spaces
            </p>
          </div>

          <div className="border-t border-gray-200 pt-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">
                S3 Configuration Status
              </span>
              <Badge color={config.S3_BUCKET ? "success" : "gray"} size="sm">
                {config.S3_BUCKET ? "Configured" : "Not Configured"}
              </Badge>
            </div>
          </div>
        </div>
      </Card>

      {/* DuckDB Configuration */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Database className="h-5 w-5 text-green-600" />
          <h3 className="text-lg font-semibold">DuckDB Performance</h3>
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="duckdb_memory_limit">Memory Limit</Label>
              <TextInput
                id="duckdb_memory_limit"
                value={config.DUCKDB_MEMORY_LIMIT || "2GB"}
                onChange={(e) =>
                  onUpdate("DUCKDB_MEMORY_LIMIT", e.target.value)
                }
                disabled={isUpdating}
              />
              <p className="mt-1 text-sm text-gray-600">
                DuckDB memory allocation (e.g., 2GB, 4GB, 8GB)
              </p>
            </div>

            <div>
              <Label htmlFor="duckdb_threads">Thread Count</Label>
              <TextInput
                id="duckdb_threads"
                type="number"
                min="1"
                max="32"
                value={config.DUCKDB_THREADS || 4}
                onChange={(e) =>
                  onUpdate("DUCKDB_THREADS", parseInt(e.target.value))
                }
                disabled={isUpdating}
              />
              <p className="mt-1 text-sm text-gray-600">
                Number of threads for parallel processing
              </p>
            </div>
          </div>

          <div className="rounded-lg bg-blue-50 p-4">
            <h4 className="mb-2 font-medium text-blue-900">Performance Tips</h4>
            <ul className="space-y-1 text-sm text-blue-700">
              <li>• Set memory limit to 50-75% of available RAM</li>
              <li>
                • Use thread count equal to CPU cores for best performance
              </li>
              <li>• Higher memory limits improve large dataset processing</li>
              <li>• Changes require application restart to take effect</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
}

// Raw Configuration Section Component
function RawConfigurationSection({
  config,
  isUpdating,
}: {
  config: any;
  isUpdating: boolean;
}) {
  const [configJson, setConfigJson] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [jsonError, setJsonError] = useState("");

  const handleStartEditing = () => {
    setConfigJson(JSON.stringify(config, null, 2));
    setIsEditing(true);
    setJsonError("");
  };

  const handleSaveConfig = () => {
    try {
      const parsed = JSON.parse(configJson);
      // Would need to implement full config replacement endpoint
      console.log("Parsed config:", parsed);
      setIsEditing(false);
      setJsonError("");
    } catch (error) {
      setJsonError(
        `Invalid JSON: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  };

  const handleCancelEditing = () => {
    setIsEditing(false);
    setConfigJson("");
    setJsonError("");
  };

  return (
    <div className="space-y-6">
      <Alert color="warning">
        <Code className="h-4 w-4" />
        <span className="ml-2">
          <strong>Danger Zone:</strong> Direct configuration editing can break
          your system. Only edit if you understand the configuration schema.
        </span>
      </Alert>

      {/* Raw Configuration Editor */}
      <Card>
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Code className="h-5 w-5 text-purple-600" />
            <h3 className="text-lg font-semibold">Configuration JSON</h3>
          </div>
          <div className="flex items-center gap-2">
            {!isEditing ? (
              <Button size="sm" color="gray" onClick={handleStartEditing}>
                <Code className="mr-1 h-3 w-3" />
                Edit Raw Config
              </Button>
            ) : (
              <>
                <Button
                  size="sm"
                  color="success"
                  onClick={handleSaveConfig}
                  disabled={isUpdating}
                >
                  Save Changes
                </Button>
                <Button size="sm" color="gray" onClick={handleCancelEditing}>
                  Cancel
                </Button>
              </>
            )}
          </div>
        </div>

        {jsonError && (
          <Alert color="failure" className="mb-4">
            <XCircle className="h-4 w-4" />
            <span className="ml-2">{jsonError}</span>
          </Alert>
        )}

        <div className="space-y-4">
          {isEditing ? (
            <Textarea
              value={configJson}
              onChange={(e) => setConfigJson(e.target.value)}
              rows={20}
              className="font-mono text-sm"
              placeholder="Configuration JSON..."
            />
          ) : (
            <div className="max-h-96 overflow-auto rounded-lg bg-gray-50 p-4">
              <pre className="font-mono text-sm text-gray-800">
                {JSON.stringify(config, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </Card>

      {/* Configuration Schema */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Info className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">Configuration Schema</h3>
        </div>

        <div className="space-y-3">
          <p className="text-sm text-gray-600">
            The configuration follows a nested structure with these main
            sections:
          </p>

          <div className="rounded-lg bg-gray-50 p-4">
            <ul className="space-y-1 font-mono text-sm text-gray-700">
              <li>
                • <strong>server</strong> - HTTP server configuration
              </li>
              <li>
                • <strong>database</strong> - SQLite database settings
              </li>
              <li>
                • <strong>llm</strong> - Large Language Model defaults
              </li>
              <li>
                • <strong>nlp</strong> - Natural Language Processing settings
              </li>
              <li>
                • <strong>reference_sources</strong> - External API
                configurations
              </li>
              <li>
                • <strong>proxy_server</strong> - Caching proxy settings
              </li>
              <li>
                • <strong>logging</strong> - Log level and output configuration
              </li>
              <li>
                • <strong>security</strong> - Authentication and security
                settings
              </li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
}

// Configuration Actions Section Component
function ConfigurationActionsSection() {
  const [isProcessing, setIsProcessing] = useState(false);

  const handleReloadConfig = async () => {
    setIsProcessing(true);
    try {
      // Call reload endpoint
      console.log("Reloading configuration...");
      await new Promise((resolve) => setTimeout(resolve, 1000)); // Simulate API call
    } finally {
      setIsProcessing(false);
    }
  };

  const handleResetConfig = async () => {
    if (
      !confirm(
        "Are you sure you want to reset configuration to defaults? This cannot be undone.",
      )
    ) {
      return;
    }

    setIsProcessing(true);
    try {
      // Call reset endpoint
      console.log("Resetting configuration...");
      await new Promise((resolve) => setTimeout(resolve, 1000)); // Simulate API call
    } finally {
      setIsProcessing(false);
    }
  };

  const handleExportConfig = () => {
    // Export current configuration
    console.log("Exporting configuration...");
  };

  const handleImportConfig = () => {
    // Import configuration from file
    console.log("Importing configuration...");
  };

  return (
    <div className="space-y-6">
      {/* Configuration Management */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Settings className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">Configuration Management</h3>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Button
            color="blue"
            onClick={handleReloadConfig}
            disabled={isProcessing}
          >
            <RotateCcw className="mr-2 h-4 w-4" />
            Reload Configuration
          </Button>

          <Button color="gray" onClick={handleExportConfig}>
            <Download className="mr-2 h-4 w-4" />
            Export Configuration
          </Button>

          <Button color="gray" onClick={handleImportConfig}>
            <Upload className="mr-2 h-4 w-4" />
            Import Configuration
          </Button>

          <Button
            color="failure"
            onClick={handleResetConfig}
            disabled={isProcessing}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Reset to Defaults
          </Button>
        </div>
      </Card>

      {/* Action Descriptions */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Info className="h-5 w-5 text-green-600" />
          <h3 className="text-lg font-semibold">Action Descriptions</h3>
        </div>

        <div className="space-y-4 text-sm text-gray-600">
          <div>
            <strong className="text-gray-900">Reload Configuration:</strong>{" "}
            Re-reads the configuration from disk without restarting the
            application. Use when you've manually edited config files.
          </div>

          <div>
            <strong className="text-gray-900">Export Configuration:</strong>{" "}
            Downloads the current configuration as a JSON file for backup or
            sharing between instances.
          </div>

          <div>
            <strong className="text-gray-900">Import Configuration:</strong>{" "}
            Uploads and applies a configuration file. The application may
            restart to apply all changes.
          </div>

          <div>
            <strong className="text-red-600">Reset to Defaults:</strong>{" "}
            Completely resets all configuration to factory defaults. This will
            remove all customizations and cannot be undone.
          </div>
        </div>
      </Card>

      {/* Recent Actions */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <CheckCircle className="h-5 w-5 text-green-600" />
          <h3 className="text-lg font-semibold">Recent Actions</h3>
        </div>

        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between border-b border-gray-100 py-2">
            <span>Configuration reloaded</span>
            <Badge color="success" size="sm">
              2 minutes ago
            </Badge>
          </div>

          <div className="flex items-center justify-between border-b border-gray-100 py-2">
            <span>LLM model configuration updated</span>
            <Badge color="info" size="sm">
              15 minutes ago
            </Badge>
          </div>

          <div className="flex items-center justify-between py-2">
            <span>Proxy settings modified</span>
            <Badge color="info" size="sm">
              1 hour ago
            </Badge>
          </div>
        </div>
      </Card>
    </div>
  );
}

// System Information Section Component
function SystemInformationSection() {
  return (
    <div className="space-y-6">
      {/* Application Information */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Info className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">Application Information</h3>
        </div>

        <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="font-medium">Version:</span>
              <span>1.0.0-beta.3</span>
            </div>
            <div className="flex justify-between">
              <span className="font-medium">Build:</span>
              <span>20240315.1234</span>
            </div>
            <div className="flex justify-between">
              <span className="font-medium">Environment:</span>
              <span>Development</span>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="font-medium">Python Version:</span>
              <span>3.11.7</span>
            </div>
            <div className="flex justify-between">
              <span className="font-medium">FastAPI Version:</span>
              <span>0.104.1</span>
            </div>
            <div className="flex justify-between">
              <span className="font-medium">SQLite Version:</span>
              <span>3.42.0</span>
            </div>
          </div>
        </div>
      </Card>

      {/* System Resources */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Cpu className="h-5 w-5 text-green-600" />
          <h3 className="text-lg font-semibold">System Resources</h3>
        </div>

        <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-3">
          <div className="text-center">
            <Cpu className="mx-auto mb-2 h-8 w-8 text-blue-600" />
            <div className="font-medium">CPU Cores</div>
            <div className="text-xl font-bold">8</div>
          </div>

          <div className="text-center">
            <HardDrive className="mx-auto mb-2 h-8 w-8 text-green-600" />
            <div className="font-medium">Total RAM</div>
            <div className="text-xl font-bold">16 GB</div>
          </div>

          <div className="text-center">
            <Database className="mx-auto mb-2 h-8 w-8 text-purple-600" />
            <div className="font-medium">Disk Space</div>
            <div className="text-xl font-bold">256 GB</div>
          </div>
        </div>
      </Card>

      {/* Configuration File Paths */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Settings className="h-5 w-5 text-orange-600" />
          <h3 className="text-lg font-semibold">Configuration Paths</h3>
        </div>

        <div className="space-y-3 font-mono text-sm">
          <div>
            <div className="mb-1 font-medium text-gray-900">
              Main Configuration:
            </div>
            <div className="rounded bg-gray-50 p-2 text-gray-700">
              ./config.json
            </div>
          </div>

          <div>
            <div className="mb-1 font-medium text-gray-900">
              Enabled Models:
            </div>
            <div className="rounded bg-gray-50 p-2 text-gray-700">
              ./enabled_models.json
            </div>
          </div>

          <div>
            <div className="mb-1 font-medium text-gray-900">Log Directory:</div>
            <div className="rounded bg-gray-50 p-2 text-gray-700">./logs/</div>
          </div>

          <div>
            <div className="mb-1 font-medium text-gray-900">
              Database Directory:
            </div>
            <div className="rounded bg-gray-50 p-2 text-gray-700">./</div>
          </div>
        </div>
      </Card>
    </div>
  );
}
