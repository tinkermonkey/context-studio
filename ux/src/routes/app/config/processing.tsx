import { createFileRoute } from "@tanstack/react-router";
import { Card,
  Alert,
  TextInput,
  Tabs,
 } from "flowbite-react";
import { CsMainTitle } from "@/components/layout/cs_main";
import { ConfigBreadcrumbs } from "@/components/configuration/ConfigBreadcrumbs";
import {
  Zap,
  Brain,
    Timer,
  FileText,
} from "lucide-react";
import {
  useConfiguration,
  useUpdateConfigurationValue,
  useEnabledModelsOnly,
} from "@/api/hooks";
import { useButterToast } from "@/hooks/useButterToast";

export const Route = createFileRoute("/app/config/processing")({
  component: RouteComponent,
});

const NLP_MODELS = [
  {
    value: "en_core_web_sm",
    label: "English Small (en_core_web_sm)",
    size: "15MB",
  },
  {
    value: "en_core_web_md",
    label: "English Medium (en_core_web_md)",
    size: "40MB",
  },
  {
    value: "en_core_web_lg",
    label: "English Large (en_core_web_lg)",
    size: "750MB",
  },
  {
    value: "en_core_web_trf",
    label: "English Transformer (en_core_web_trf)",
    size: "560MB",
  },
];

const CONCEPTNET_RELATIONS = [
  "RELATED_TO",
  "IS_A",
  "PART_OF",
  "USED_FOR",
  "CAPABLE_OF",
  "AT_LOCATION",
  "CAUSES",
  "HAS_A",
  "MADE_OF",
  "RECEIVES_ACTION",
];

function RouteComponent() {
  const toast = useButterToast();
  const { data: configuration, isLoading: isLoadingConfig } =
    useConfiguration();
  const { data: enabledModels, isLoading: isLoadingModels } =
    useEnabledModelsOnly();
  const updateConfigMutation = useUpdateConfigurationValue();

  const getNLPConfigLabel = (path: string): string => {
    const labels: Record<string, string> = {
      model_name: "spaCy model",
      auto_download_models: "Auto-download models",
      download_timeout: "Download timeout",
      max_text_length: "Max text length",
      request_timeout: "Request timeout",
      filter_missing_text: "Filter missing text",
      edge_weight_filter: "Edge weight filter",
      concepcy_relations: "ConceptNet relations",
    };
    return labels[path] || path;
  };

  const getLLMConfigLabel = (path: string): string => {
    const labels: Record<string, string> = {
      model_name: "Default model",
      temperature: "Temperature",
      max_tokens: "Max tokens",
      timeout: "Request timeout",
      max_text_length: "Max input length",
      retry_attempts: "Retry attempts",
    };
    return labels[path] || path;
  };

   
  const handleUpdateNLPConfig = async (path: string, value: any)  // eslint-disable-line @typescript-eslint/no-explicit-any
 => {
    const label = getNLPConfigLabel(path);
    await updateConfigMutation.mutateAsync(
      {
        path: `nlp.${path}`,
        value,
      },
      {
        onSuccess: () => {
          toast.success(`NLP ${label} updated successfully`);
        },
        onError: (error) => {
          toast.error(
            `Failed to update NLP ${label}: ${error instanceof Error ? error.message : "Unknown error"}`,
          );
        },
      },
    );
  };

   
  const handleUpdateLLMConfig = async (path: string, value: any)  // eslint-disable-line @typescript-eslint/no-explicit-any
 => {
    const label = getLLMConfigLabel(path);
    await updateConfigMutation.mutateAsync(
      {
        path: `llm.${path}`,
        value,
      },
      {
        onSuccess: () => {
          toast.success(`LLM ${label} updated successfully`);
        },
        onError: (error) => {
          toast.error(
            `Failed to update LLM ${label}: ${error instanceof Error ? error.message : "Unknown error"}`,
          );
        },
      },
    );
  };

  if (isLoadingConfig || isLoadingModels) {
    return (
      <div className="p-6">
        <ConfigBreadcrumbs items={[{ label: "Processing" }]} />
        <CsMainTitle>Processing Configuration</CsMainTitle>
        <div className="py-8 text-center">Loading configuration...</div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <ConfigBreadcrumbs items={[{ label: "Processing" }]} />
      <CsMainTitle>Processing Configuration</CsMainTitle>

      <div className="mb-6">
        <p className="text-gray-600">
          Configure NLP processing and pipeline defaults for knowledge graph
          operations.
        </p>
      </div>

      <Tabs aria-label="Processing Configuration" variant="underline">
        {/* NLP Configuration Tab */}
        <Tabs.Item title="NLP Configuration" icon={FileText}>
          <NLPConfigurationSection
            config={configuration?.data?.nlp}
            onUpdate={handleUpdateNLPConfig}
            isUpdating={updateConfigMutation.isPending}
          />
        </Tabs.Item>

        {/* Pipeline Defaults Tab */}
        <Tabs.Item title="Pipeline Defaults" icon={Brain}>
          <PipelineDefaultsSection
            config={configuration?.data?.llm}
            enabledModels={enabledModels || []}
            onUpdate={handleUpdateLLMConfig}
            isUpdating={updateConfigMutation.isPending}
          />
        </Tabs.Item>
      </Tabs>
    </div>
  );
}

// NLP Configuration Section Component
function NLPConfigurationSection({
  config,
  isUpdating,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any;
   
  onUpdate: (path: string, value: any)  // eslint-disable-line @typescript-eslint/no-explicit-any
 => void;
  isUpdating: boolean;
}) {
  if (!config) {
    return <div>No NLP configuration available</div>;
  }

  const currentModel =
    NLP_MODELS.find((m) => m.value === config.model_name) || NLP_MODELS[0];
  const enabledRelations = config.concepcy_relations || [];

  return (
    <div className="space-y-6">
      {/* spaCy Model Configuration */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Settings className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">spaCy Model Configuration</h3>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="nlp_model">spaCy Model</Label>
            <Select
              id="nlp_model"
              value={config.model_name || "en_core_web_lg"}
              onChange={(e) => onUpdate("model_name", e.target.value)}
              disabled={isUpdating}
            >
              {NLP_MODELS.map((model) => (
                <option key={model.value} value={model.value}>
                  {model.label} ({model.size})
                </option>
              ))}
            </Select>
            <p className="mt-1 text-sm text-gray-600">
              Currently using:{" "}
              <span className="font-medium">{currentModel.label}</span> (
              {currentModel.size})
            </p>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="auto_download">Auto-download Models</Label>
              <p className="text-sm text-gray-600">
                Automatically download missing spaCy models
              </p>
            </div>
            <Checkbox
              id="auto_download"
              checked={config.auto_download_models ?? true}
              onChange={(e) =>
                onUpdate("auto_download_models", e.target.checked)
              }
              disabled={isUpdating}
            />
          </div>

          <div>
            <Label htmlFor="download_timeout">Download Timeout (seconds)</Label>
            <TextInput
              id="download_timeout"
              type="number"
              value={config.download_timeout || 600}
              onChange={(e) =>
                onUpdate("download_timeout", parseInt(e.target.value))
              }
              disabled={isUpdating}
            />
          </div>
        </div>
      </Card>

      {/* Text Processing Limits */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Timer className="h-5 w-5 text-green-600" />
          <h3 className="text-lg font-semibold">Text Processing Limits</h3>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="max_text_length">
              Max Text Length (characters)
            </Label>
            <TextInput
              id="max_text_length"
              type="number"
              value={config.max_text_length || 512}
              onChange={(e) =>
                onUpdate("max_text_length", parseInt(e.target.value))
              }
              disabled={isUpdating}
            />
            <p className="mt-1 text-sm text-gray-600">
              Longer texts will be truncated
            </p>
          </div>

          <div>
            <Label htmlFor="request_timeout">Request Timeout (seconds)</Label>
            <TextInput
              id="request_timeout"
              type="number"
              value={config.request_timeout || 30}
              onChange={(e) =>
                onUpdate("request_timeout", parseInt(e.target.value))
              }
              disabled={isUpdating}
            />
          </div>
        </div>

        <div className="mt-4">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="filter_missing_text">Filter Missing Text</Label>
              <p className="text-sm text-gray-600">
                Skip processing nodes with empty text
              </p>
            </div>
            <Checkbox
              id="filter_missing_text"
              checked={config.filter_missing_text ?? true}
              onChange={(e) =>
                onUpdate("filter_missing_text", e.target.checked)
              }
              disabled={isUpdating}
            />
          </div>
        </div>
      </Card>

      {/* ConceptNet Relations */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Zap className="h-5 w-5 text-purple-600" />
          <h3 className="text-lg font-semibold">ConceptNet Relations</h3>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="edge_weight_filter">Edge Weight Filter</Label>
            <TextInput
              id="edge_weight_filter"
              type="number"
              step="0.1"
              value={config.edge_weight_filter || 1.5}
              onChange={(e) =>
                onUpdate("edge_weight_filter", parseFloat(e.target.value))
              }
              disabled={isUpdating}
            />
            <p className="mt-1 text-sm text-gray-600">
              Minimum edge weight for ConceptNet relations
            </p>
          </div>

          <div>
            <Label>Enabled Relations</Label>
            <div className="mt-2 grid grid-cols-2 gap-3 md:grid-cols-3">
              {CONCEPTNET_RELATIONS.map((relation) => {
                const isEnabled = enabledRelations.includes(relation);
                return (
                  <div key={relation} className="flex items-center gap-2">
                    <Checkbox
                      id={`relation_${relation}`}
                      checked={isEnabled}
                      onChange={(e) => {
                        const newRelations = e.target.checked
                          ? [...enabledRelations, relation]
                          : enabledRelations.filter(
                              (r: string) => r !== relation,
                            );
                        onUpdate("concepcy_relations", newRelations);
                      }}
                      disabled={isUpdating}
                    />
                    <Label htmlFor={`relation_${relation}`} className="text-sm">
                      {relation}
                    </Label>
                  </div>
                );
              })}
            </div>
            <p className="mt-2 text-sm text-gray-600">
              {enabledRelations.length} of {CONCEPTNET_RELATIONS.length}{" "}
              relations enabled
            </p>
          </div>
        </div>
      </Card>

      {/* Additional Settings */}
      <Card>
        <h3 className="mb-4 text-lg font-semibold">Additional Settings</h3>
        <div className="space-y-4">
          <div>
            <Label htmlFor="sense2vec_path">Sense2Vec Model Path</Label>
            <TextInput
              id="sense2vec_path"
              value={config.sense2vec_path || "./downloads/s2v_reddit_2015_md"}
              disabled
            />
            <p className="mt-1 text-sm text-gray-600">
              Path to Sense2Vec model for semantic similarity
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}

// Pipeline Defaults Section Component
function PipelineDefaultsSection({
  config,
  enabledModels,
  isUpdating,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  enabledModels: any[];
   
  onUpdate: (path: string, value: any)  // eslint-disable-line @typescript-eslint/no-explicit-any
 => void;
  isUpdating: boolean;
}) {
  if (!config) {
    return <div>No LLM configuration available</div>;
  }

  const currentModel = enabledModels.find(
    (m) => m.model_name === config.model_name,
  );

  return (
    <div className="space-y-6">
      <Alert color="info">
        <Brain className="h-4 w-4" />
        <span className="ml-2">
          These settings provide defaults for new pipeline flavors. Individual
          flavors can override these settings.
        </span>
      </Alert>

      {/* Default Model Selection */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Brain className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">Default LLM Model</h3>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="default_model">Default Model</Label>
            <Select
              id="default_model"
              value={config.model_name || "gpt-3.5-turbo"}
              onChange={(e) => onUpdate("model_name", e.target.value)}
              disabled={isUpdating}
            >
              {enabledModels.length === 0 ? (
                <option value="">No enabled models available</option>
              ) : (
                enabledModels.map((model) => (
                  <option key={model.model_name} value={model.model_name}>
                    {model.display_name} ({model.provider_type})
                  </option>
                ))
              )}
            </Select>
            {currentModel && (
              <div className="mt-2 flex items-center gap-2">
                <Badge color="info" size="sm">
                  {currentModel.provider_type}
                </Badge>
                <Badge
                  color={
                    currentModel.cost_tier === "low"
                      ? "success"
                      : currentModel.cost_tier === "medium"
                        ? "warning"
                        : "failure"
                  }
                  size="sm"
                >
                  {currentModel.cost_tier} cost
                </Badge>
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Default Parameters */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Settings className="h-5 w-5 text-green-600" />
          <h3 className="text-lg font-semibold">Default Parameters</h3>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="temperature">Temperature</Label>
            <TextInput
              id="temperature"
              type="number"
              step="0.1"
              min="0"
              max="2"
              value={config.temperature ?? 0.0}
              onChange={(e) =>
                onUpdate("temperature", parseFloat(e.target.value))
              }
              disabled={isUpdating}
            />
            <p className="mt-1 text-sm text-gray-600">
              Controls randomness (0.0 = deterministic, 2.0 = very random)
            </p>
          </div>

          <div>
            <Label htmlFor="max_tokens">Max Tokens</Label>
            <TextInput
              id="max_tokens"
              type="number"
              value={config.max_tokens || ""}
              placeholder="Auto (model default)"
              onChange={(e) =>
                onUpdate(
                  "max_tokens",
                  e.target.value ? parseInt(e.target.value) : null,
                )
              }
              disabled={isUpdating}
            />
            <p className="mt-1 text-sm text-gray-600">
              Maximum tokens to generate (leave empty for model default)
            </p>
          </div>
        </div>
      </Card>

      {/* Processing Settings */}
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <Timer className="h-5 w-5 text-orange-600" />
          <h3 className="text-lg font-semibold">Processing Settings</h3>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <Label htmlFor="llm_timeout">Request Timeout (seconds)</Label>
            <TextInput
              id="llm_timeout"
              type="number"
              value={config.timeout || 30}
              onChange={(e) => onUpdate("timeout", parseInt(e.target.value))}
              disabled={isUpdating}
            />
          </div>

          <div>
            <Label htmlFor="max_text_length">
              Max Input Length (characters)
            </Label>
            <TextInput
              id="max_text_length"
              type="number"
              value={config.max_text_length || 1000}
              onChange={(e) =>
                onUpdate("max_text_length", parseInt(e.target.value))
              }
              disabled={isUpdating}
            />
          </div>

          <div>
            <Label htmlFor="retry_attempts">Retry Attempts</Label>
            <TextInput
              id="retry_attempts"
              type="number"
              min="0"
              max="10"
              value={config.retry_attempts || 3}
              onChange={(e) =>
                onUpdate("retry_attempts", parseInt(e.target.value))
              }
              disabled={isUpdating}
            />
          </div>
        </div>
      </Card>

      {enabledModels.length === 0 && (
        <Alert color="warning">
          <AlertTriangle className="h-4 w-4" />
          <span className="ml-2">
            No LLM models are currently enabled. Visit the LLM Models
            configuration to enable models.
          </span>
        </Alert>
      )}
    </div>
  );
}
