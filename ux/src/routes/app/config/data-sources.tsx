import { createFileRoute } from "@tanstack/react-router";
import { Card, Alert, Badge, Button, TextInput, Label, Checkbox, Tabs } from "flowbite-react";
import { CsMainTitle } from "@/components/layout/cs_main";
import { ConfigBreadcrumbs } from "@/components/configuration/ConfigBreadcrumbs";
import {
  Database,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Settings,
  ExternalLink,
  RefreshCw,
  Server,
  Globe
} from "lucide-react";
import {
  useConfiguration,
  useReferenceSourcesConfig,
  useReferenceSourcesStatus,
  useUpdateReferenceSourceConfig
} from "@/api/hooks";

export const Route = createFileRoute("/app/config/data-sources")({
  component: RouteComponent,
});

const REFERENCE_SOURCE_LABELS: Record<string, { name: string; description: string; icon: React.ComponentType<{ className?: string }> }> = {
  conceptnet: {
    name: "ConceptNet",
    description: "Semantic network of common sense knowledge",
    icon: Globe
  },
  dbpedia: {
    name: "DBpedia",
    description: "Structured content from Wikipedia",
    icon: Database
  },
  dbpedia_spotlight: {
    name: "DBpedia Spotlight",
    description: "Entity recognition and linking service",
    icon: ExternalLink
  },
  wikidata: {
    name: "Wikidata",
    description: "Collaborative knowledge base",
    icon: Database
  },
  schema_org: {
    name: "Schema.org",
    description: "Structured data vocabulary",
    icon: Settings
  }
};

function RouteComponent() {
  const { data: configuration, isLoading: isLoadingConfig } = useConfiguration();
  const { data: referenceSourcesConfig, isLoading: isLoadingRefConfig } = useReferenceSourcesConfig();
  const { data: referenceSourcesStatus, isLoading: isLoadingStatus } = useReferenceSourcesStatus();
  const updateReferenceSourceMutation = useUpdateReferenceSourceConfig();

  const handleToggleSource = async (sourceName: string, enabled: boolean) => {
    try {
      await updateReferenceSourceMutation.mutateAsync({
        sourceName,
        path: "enabled",
        value: enabled
      });
    } catch (error) {
      console.error(`Failed to toggle ${sourceName}:`, error);
    }
  };

  const handleUpdateTimeout = async (sourceName: string, timeout: number) => {
    try {
      await updateReferenceSourceMutation.mutateAsync({
        sourceName,
        path: "timeout",
        value: timeout
      });
    } catch (error) {
      console.error(`Failed to update timeout for ${sourceName}:`, error);
    }
  };

  const handleToggleProxy = async (sourceName: string, useProxy: boolean) => {
    try {
      await updateReferenceSourceMutation.mutateAsync({
        sourceName,
        path: "use_proxy",
        value: useProxy
      });
    } catch (error) {
      console.error(`Failed to toggle proxy for ${sourceName}:`, error);
    }
  };

  if (isLoadingConfig || isLoadingRefConfig || isLoadingStatus) {
    return (
      <div className="p-6">
        <ConfigBreadcrumbs items={[{ label: "Data Sources" }]} />
        <CsMainTitle>Data Sources Configuration</CsMainTitle>
        <div className="text-center py-8">Loading configuration...</div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <ConfigBreadcrumbs items={[{ label: "Data Sources" }]} />
      <CsMainTitle>Data Sources Configuration</CsMainTitle>

      <div className="mb-6">
        <p className="text-gray-600">
          Configure reference APIs and database settings for knowledge graph enrichment.
        </p>
      </div>

      <Tabs aria-label="Data Sources Configuration" variant="underline">
        {/* Reference APIs Tab */}
        <Tabs.Item title="Reference APIs" icon={Globe}>
          <ReferenceAPIsSection
            config={referenceSourcesConfig?.data}
            status={referenceSourcesStatus?.data}
            onToggleSource={handleToggleSource}
            onUpdateTimeout={handleUpdateTimeout}
            onToggleProxy={handleToggleProxy}
            isUpdating={updateReferenceSourceMutation.isPending}
          />
        </Tabs.Item>

        {/* Database Settings Tab */}
        <Tabs.Item title="Database Settings" icon={Database}>
          <DatabaseSettingsSection config={configuration?.data?.database} />
        </Tabs.Item>
      </Tabs>
    </div>
  );
}

// Reference APIs Section Component
function ReferenceAPIsSection({
  config,
  status,
  onToggleSource,
  onUpdateTimeout,
  onToggleProxy,
  isUpdating
}: {
  config: any;
  status: any;
  onToggleSource: (sourceName: string, enabled: boolean) => void;
  onUpdateTimeout: (sourceName: string, timeout: number) => void;
  onToggleProxy: (sourceName: string, useProxy: boolean) => void;
  isUpdating: boolean;
}) {
  if (!config || !status) {
    return <div>No configuration data available</div>;
  }

  // Get all reference sources except global settings
  const sources = Object.keys(config)
    .filter(key => !['default_language', 'search_timeout'].includes(key))
    .filter(key => typeof config[key] === 'object');

  return (
    <div className="space-y-6">
      {/* Global Settings */}
      <Card>
        <h3 className="text-lg font-semibold mb-4">Global Settings</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="default_language">Default Language</Label>
            <TextInput
              id="default_language"
              value={config.default_language || 'en'}
              disabled
            />
          </div>
          <div>
            <Label htmlFor="search_timeout">Search Timeout (seconds)</Label>
            <TextInput
              id="search_timeout"
              type="number"
              value={config.search_timeout || 30}
              disabled
            />
          </div>
        </div>
      </Card>

      {/* Reference Sources */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {sources.map((sourceName) => {
          const sourceConfig = config[sourceName];
          const sourceStatus = status[sourceName];
          const sourceInfo = REFERENCE_SOURCE_LABELS[sourceName];

          if (!sourceInfo) return null;

          const Icon = sourceInfo.icon;
          const isEnabled = sourceConfig?.enabled ?? false;
          const hasProxy = sourceConfig?.use_proxy ?? false;

          return (
            <ReferenceSourceCard
              key={sourceName}
              sourceName={sourceName}
              sourceInfo={sourceInfo}
              config={sourceConfig}
              status={sourceStatus}
              isEnabled={isEnabled}
              hasProxy={hasProxy}
              onToggleSource={onToggleSource}
              onUpdateTimeout={onUpdateTimeout}
              onToggleProxy={onToggleProxy}
              isUpdating={isUpdating}
              Icon={Icon}
            />
          );
        })}
      </div>
    </div>
  );
}

// Reference Source Card Component
function ReferenceSourceCard({
  sourceName,
  sourceInfo,
  config,
  status,
  isEnabled,
  hasProxy,
  onToggleSource,
  onUpdateTimeout,
  onToggleProxy,
  isUpdating,
  Icon
}: {
  sourceName: string;
  sourceInfo: any;
  config: any;
  status: any;
  isEnabled: boolean;
  hasProxy: boolean;
  onToggleSource: (sourceName: string, enabled: boolean) => void;
  onUpdateTimeout: (sourceName: string, timeout: number) => void;
  onToggleProxy: (sourceName: string, useProxy: boolean) => void;
  isUpdating: boolean;
  Icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Card className={`transition-all ${isEnabled ? 'border-green-200 bg-green-50' : 'border-gray-200'}`}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <Icon className={`h-6 w-6 ${isEnabled ? 'text-green-600' : 'text-gray-400'}`} />
          <div>
            <h4 className="font-semibold">{sourceInfo.name}</h4>
            <p className="text-sm text-gray-600">{sourceInfo.description}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isEnabled ? (
            <CheckCircle className="h-5 w-5 text-green-600" />
          ) : (
            <XCircle className="h-5 w-5 text-gray-400" />
          )}
          <Badge color={isEnabled ? "success" : "gray"} size="sm">
            {isEnabled ? "Enabled" : "Disabled"}
          </Badge>
        </div>
      </div>

      <div className="space-y-4">
        {/* Enable/Disable Toggle */}
        <div className="flex items-center justify-between">
          <Label htmlFor={`${sourceName}_enabled`}>Enable {sourceInfo.name}</Label>
          <Checkbox
            id={`${sourceName}_enabled`}
            checked={isEnabled}
            onChange={(e) => onToggleSource(sourceName, e.target.checked)}
            disabled={isUpdating}
          />
        </div>

        {isEnabled && (
          <>
            {/* URL */}
            <div>
              <Label htmlFor={`${sourceName}_url`}>API URL</Label>
              <div className="flex items-center gap-2">
                <TextInput
                  id={`${sourceName}_url`}
                  value={config.upstream_url || ''}
                  disabled
                  className="flex-1"
                />
                <Button size="xs" color="gray">
                  <ExternalLink className="h-3 w-3" />
                </Button>
              </div>
            </div>

            {/* Timeout */}
            <div>
              <Label htmlFor={`${sourceName}_timeout`}>Timeout (seconds)</Label>
              <TextInput
                id={`${sourceName}_timeout`}
                type="number"
                value={config.timeout || 30}
                onChange={(e) => onUpdateTimeout(sourceName, parseInt(e.target.value))}
                disabled={isUpdating}
              />
            </div>

            {/* Use Proxy */}
            <div className="flex items-center justify-between">
              <Label htmlFor={`${sourceName}_proxy`}>Route through proxy</Label>
              <Checkbox
                id={`${sourceName}_proxy`}
                checked={hasProxy}
                onChange={(e) => onToggleProxy(sourceName, e.target.checked)}
                disabled={isUpdating}
              />
            </div>

            {/* Rate Limiting Info */}
            {config.rate_limit && (
              <div className="pt-3 border-t border-gray-200">
                <h5 className="text-sm font-medium text-gray-700 mb-2">Rate Limiting</h5>
                <div className="text-sm text-gray-600 space-y-1">
                  <div>Requests per hour: {config.rate_limit.requests_per_hour}</div>
                  <div>Max delay: {config.rate_limit.max_delay}s</div>
                  <div>Progressive delay: {config.rate_limit.progressive_delay ? 'Yes' : 'No'}</div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </Card>
  );
}

// Database Settings Section Component
function DatabaseSettingsSection({ config }: { config: any }) {
  if (!config) {
    return <div>No database configuration available</div>;
  }

  return (
    <div className="space-y-6">
      <Alert color="warning">
        <AlertTriangle className="h-4 w-4" />
        <span className="ml-2">
          Database settings require server restart to take effect.
        </span>
      </Alert>

      <Card>
        <h3 className="text-lg font-semibold mb-4">Database File Paths</h3>
        <div className="space-y-4">
          <div>
            <Label htmlFor="default_dataset">Default Dataset File</Label>
            <TextInput
              id="default_dataset"
              value={config.default_dataset_filename || ''}
              disabled
            />
          </div>

          <div>
            <Label htmlFor="schema_org_path">Schema.org Database Path</Label>
            <TextInput
              id="schema_org_path"
              value={config.schema_org_path || ''}
              disabled
            />
          </div>

          <div>
            <Label htmlFor="reference_cache_path">Reference Cache Database Path</Label>
            <TextInput
              id="reference_cache_path"
              value={config.reference_cache_path || ''}
              disabled
            />
          </div>

          <div>
            <Label htmlFor="operations_path">Operations database Path</Label>
            <TextInput
              id="operations_path"
              value={config.operations_path || ''}
              disabled
            />
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="text-lg font-semibold mb-4">Connection Settings</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="pool_timeout">Connection Pool Timeout (seconds)</Label>
            <TextInput
              id="pool_timeout"
              type="number"
              value={config.pool_timeout || 30}
              disabled
            />
          </div>

          <div className="flex items-center justify-between">
            <Label htmlFor="check_same_thread">Check Same Thread</Label>
            <Checkbox
              id="check_same_thread"
              checked={config.check_same_thread ?? true}
              disabled
            />
          </div>
        </div>
      </Card>
    </div>
  );
}