import { createFileRoute } from "@tanstack/react-router";
import { Alert, Badge, Button, Card } from "flowbite-react";
import { CsMainTitle } from "@/components/layout/cs_main";
import { ConfigBreadcrumbs } from "@/components/configuration/ConfigBreadcrumbs";
import {
  useEnabledModels,
  useProvidersStatus,
  useToggleModel,
} from "@/api/hooks";
import { AlertTriangle, CheckCircle, Server } from "lucide-react";
import type {
  EnabledModelConfig,
  ProviderType,
} from "@/api/services/enabledModels";
import { useButterToast } from "@/hooks/useButterToast";

export const Route = createFileRoute("/app/config/models")({
  component: RouteComponent,
});

const PROVIDER_LABELS: Record<ProviderType, string> = {
  native_openai: "OpenAI",
  native_anthropic: "Anthropic",
  native_google: "Google",
  openrouter: "OpenRouter",
};

const PROVIDER_COLORS: Record<ProviderType, string> = {
  native_openai: "green",
  native_anthropic: "blue",
  native_google: "yellow",
  openrouter: "purple",
};

const COST_TIER_COLORS = {
  low: "success",
  medium: "warning",
  high: "failure",
} as const;

function RouteComponent() {
  const toast = useButterToast();
  const { data: enabledModels, isLoading: isLoadingEnabledModels } =
    useEnabledModels();
  const { data: providersStatus, isLoading: isLoadingProviders } =
    useProvidersStatus();

  const toggleModelMutation = useToggleModel();

  const handleToggleModel = async (modelName: string, enabled: boolean) => {
    const modelDisplayName =
      enabledModels?.models.find((m) => m.model_name === modelName)
        ?.display_name || modelName;
    try {
      await toggleModelMutation.mutateAsync({ modelName, enabled });
      toast.success(
        `${modelDisplayName} ${enabled ? "enabled" : "disabled"} successfully`,
      );
    } catch (error) {
      toast.error(
        `Failed to ${enabled ? "enable" : "disable"} ${modelDisplayName}: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  };

  return (
    <div className="p-6">
      <ConfigBreadcrumbs items={[{ label: "LLM Models" }]} />
      <CsMainTitle>LLM Models Configuration</CsMainTitle>

      <div className="mb-6">
        <p className="text-gray-600">
          Manage your LLM models, configure providers, and view model
          capabilities.
        </p>
      </div>

      {/* Available Models Section */}
      <AvailableModelsTab
        enabledModels={enabledModels?.models || []}
        isLoading={isLoadingEnabledModels}
        onToggleModel={handleToggleModel}
        isToggling={toggleModelMutation.isPending}
      />

      {/* Provider Configuration Section */}
      <div className="mt-8">
        <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold">
          <Server className="h-5 w-5" />
          Provider Configuration
        </h2>
        <ProviderConfigurationTab
          providersStatus={providersStatus}
          isLoading={isLoadingProviders}
        />
      </div>
    </div>
  );
}

// Available Models Tab Component
function AvailableModelsTab({
  enabledModels,
  isLoading,
  onToggleModel,
  isToggling,
}: {
  enabledModels: EnabledModelConfig[];
  isLoading: boolean;
  onToggleModel: (modelName: string, enabled: boolean) => void;
  isToggling: boolean;
}) {
  if (isLoading) {
    return <div className="py-8 text-center">Loading models...</div>;
  }

  // Group models by provider
  const modelsByProvider = enabledModels.reduce(
    (acc, model) => {
      const provider = model.provider_type;
      if (!acc[provider]) {
        acc[provider] = [];
      }
      acc[provider].push(model);
      return acc;
    },
    {} as Record<ProviderType, EnabledModelConfig[]>,
  );

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <Card>
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">
              {enabledModels.length}
            </div>
            <div className="text-sm text-gray-600">Total Models</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">
              {enabledModels.filter((m) => m.enabled).length}
            </div>
            <div className="text-sm text-gray-600">Enabled</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-2xl font-bold text-orange-600">
              {Object.keys(modelsByProvider).length}
            </div>
            <div className="text-sm text-gray-600">Providers</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600">
              {enabledModels.filter((m) => m.cost_tier === "low").length}
            </div>
            <div className="text-sm text-gray-600">Low Cost</div>
          </div>
        </Card>
      </div>

      {/* Models by Provider */}
      {Object.entries(modelsByProvider).map(([provider, models]) => (
        <Card key={provider}>
          <div className="mb-4">
            <div className="mb-2 flex items-center gap-3">
              <Badge
                color={PROVIDER_COLORS[provider as ProviderType]}
                size="lg"
              >
                {PROVIDER_LABELS[provider as ProviderType]}
              </Badge>
              <span className="text-sm text-gray-600">
                {models.filter((m) => m.enabled).length} of {models.length}{" "}
                enabled
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {models.map((model) => (
              <ModelCard
                key={model.model_name}
                model={model}
                onToggle={onToggleModel}
                isToggling={isToggling}
              />
            ))}
          </div>
        </Card>
      ))}

      {enabledModels.length === 0 && (
        <Alert color="info">
          <AlertTriangle className="h-4 w-4" />
          <span className="ml-2">
            No models configured. Add models through the configuration system.
          </span>
        </Alert>
      )}
    </div>
  );
}

// Model Card Component
function ModelCard({
  model,
  onToggle,
  isToggling,
}: {
  model: EnabledModelConfig;
  onToggle: (modelName: string, enabled: boolean) => void;
  isToggling: boolean;
}) {
  return (
    <Card
      className={`transition-all ${model.enabled ? "border-green-200 bg-green-50" : "border-gray-200"}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="mb-2 flex items-center gap-2">
            <h4 className="font-semibold">{model.display_name}</h4>
            {model.enabled && (
              <CheckCircle className="h-4 w-4 text-green-600" />
            )}
          </div>

          <p className="mb-3 text-sm text-gray-600">{model.description}</p>

          <div className="mb-3 flex items-center gap-2">
            <Badge color={COST_TIER_COLORS[model.cost_tier]} size="sm">
              {model.cost_tier} cost
            </Badge>
            {model.tags.map((tag) => (
              <Badge key={tag} color="gray" size="sm">
                {tag}
              </Badge>
            ))}
          </div>

          <div className="text-xs text-gray-500">
            API Key: {model.api_key_env_var}
          </div>
        </div>

        <div className="ml-4">
          <Button
            size="sm"
            color={model.enabled ? "failure" : "success"}
            onClick={() => onToggle(model.model_name, !model.enabled)}
            disabled={isToggling}
          >
            {model.enabled ? "Disable" : "Enable"}
          </Button>
        </div>
      </div>
    </Card>
  );
}

// Provider Configuration Tab Component
function ProviderConfigurationTab({
  providersStatus,
  isLoading,
}: {
  providersStatus: any;
  isLoading: boolean;
}) {
  if (isLoading) {
    return <div className="py-8 text-center">Loading provider status...</div>;
  }

  if (!providersStatus) {
    return <div className="py-8 text-center">No provider status available</div>;
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {Object.entries(providersStatus.providers).map(
          ([provider, status]: [string, any]) => (
            <ProviderStatusCard
              key={provider}
              provider={provider as ProviderType}
              status={status}
            />
          ),
        )}
      </div>
    </div>
  );
}

// Provider Status Card Component
function ProviderStatusCard({
  provider,
  status,
}: {
  provider: ProviderType;

  status: any;
}) {
  const hasEnabledModels = status.enabled_models > 0;

  return (
    <Card className={hasEnabledModels ? "border-green-200" : "border-gray-200"}>
      <div className="flex items-start gap-4">
        <div
          className={`rounded-lg p-3 ${hasEnabledModels ? "bg-green-100" : "bg-gray-100"}`}
        >
          <Server
            className={`h-6 w-6 ${hasEnabledModels ? "text-green-600" : "text-gray-600"}`}
          />
        </div>

        <div className="flex-1">
          <div className="mb-2 flex items-center gap-2">
            <h3 className="text-lg font-semibold">
              {PROVIDER_LABELS[provider]}
            </h3>
            <Badge color={hasEnabledModels ? "success" : "gray"} size="sm">
              {hasEnabledModels ? "Active" : "Inactive"}
            </Badge>
          </div>

          <div className="mb-3 text-sm text-gray-600">
            {status.enabled_models} of {status.total_models} models enabled
          </div>

          {status.models.length > 0 && (
            <div className="text-xs text-gray-500">
              Models: {status.models.join(", ")}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
