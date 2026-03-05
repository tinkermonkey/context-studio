import React, { useState, useRef } from "react";
import { Button,
  Label,
  TextInput,
  Textarea,
  Select,
  Alert,
  Spinner,
   } from "flowbite-react";
import { Save, AlertTriangle, Info } from "lucide-react";
import {
  useCreatePipelineFlavor,
  useUpdatePipelineFlavor,
  usePipelineFlavors,
} from "@/api/hooks/pipelineFlavors";
import {
  useTypedModelCapabilities,
  useValidateLLMConfig,
} from "@/api/hooks/modelCapabilities";
import { useEnabledModels } from "@/api/hooks/enabledModels/useEnabledModels";
import type {
  PipelineType,
  PipelineFlavor,
  CreatePipelineFlavorRequest,
  UpdatePipelineFlavorRequest,
} from "@/api/services/pipelineFlavors";

interface PipelineFlavorEditorProps {
  pipeline: PipelineType;
  flavor?: PipelineFlavor | null;
  onClose: () => void;
}

// Legacy providers for fallback
const FALLBACK_LLM_PROVIDERS = [
  { value: "native_openai", label: "OpenAI" },
  { value: "native_anthropic", label: "Anthropic" },
  { value: "native_google", label: "Google" },
  { value: "openrouter", label: "OpenRouter" },
];

const FALLBACK_MODELS: Record<string, string[]> = {
  native_openai: [
    "gpt-5",
    "gpt-5-turbo",
    "gpt-5-preview",
    "gpt-5-mini",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4o-turbo",
    "gpt-4o-latest",
    "gpt-4-turbo",
    "gpt-4-turbo-preview",
    "gpt-4",
    "gpt-3.5-turbo",
  ],
  native_anthropic: [
    "claude-4-opus",
    "claude-4-sonnet",
    "claude-4-haiku",
    "claude-4-turbo",
    "claude-4",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
  ],
  native_google: [],
  openrouter: [],
};

export const PipelineFlavorEditor: React.FC<PipelineFlavorEditorProps> = ({
  pipeline,
  flavor,
  onClose,
}) => {
  const [formData, setFormData] = useState({
    title: "",
    llm_provider: "",
    llm_model: "",
    system_prompt: "",
    user_prompt: "",
    temperature: 0.7,
    max_tokens: 1000,
    top_p: 1,
    top_k: 40,
    frequency_penalty: 0,
    presence_penalty: 0,
    enabled: true,
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const systemPromptRef = useRef<HTMLTextAreaElement>(
    null,
  ) as React.RefObject<HTMLTextAreaElement>;
  const userPromptRef = useRef<HTMLTextAreaElement>(
    null,
  ) as React.RefObject<HTMLTextAreaElement>;

  // Fetch enabled models and capabilities
  const { data: enabledModelsData } = useEnabledModels();
  const enabledModels = enabledModelsData?.models || [];
  const { data: modelCapabilities } = useTypedModelCapabilities(
    formData.llm_model,
  );
  const { data: configValidationWarnings } = useValidateLLMConfig(
    formData.llm_model,
    {
      temperature: formData.temperature,
      top_p: formData.top_p,
      top_k: formData.top_k,
      frequency_penalty: formData.frequency_penalty,
      presence_penalty: formData.presence_penalty,
      max_tokens: formData.max_tokens,
    },
  );

  const adjustTextAreaHeight = (
    textAreaRef: React.RefObject<HTMLTextAreaElement>,
  ) => {
    if (textAreaRef.current) {
      textAreaRef.current.style.height = "auto";
      textAreaRef.current.style.height = `${textAreaRef.current.scrollHeight}px`;
    }
  };

  // Fetch existing flavors for this pipeline type to get default values
  const shouldFetchDefaults = !flavor; // Only fetch when creating a new flavor
  const { data: existingFlavorsResponse, isLoading: flavorsLoading } =
    usePipelineFlavors(shouldFetchDefaults ? { pipeline } : undefined);

  const createMutation = useCreatePipelineFlavor({
    onSuccess: () => {
      onClose();
    },
    onError: (error) => {
      setErrors({ submit: error.message });
    },
  });

  const updateMutation = useUpdatePipelineFlavor({
    onSuccess: () => {
      onClose();
    },
    onError: (error) => {
      setErrors({ submit: error.message });
    },
  });

  // Populate form when editing existing flavor
  useEffect(() => {
    if (flavor) {
      setFormData({
        title: flavor.title,
        llm_provider: flavor.llm_provider,
        llm_model: flavor.llm_model,
        system_prompt: flavor.system_prompt,
        user_prompt: flavor.user_prompt,
        temperature: flavor.llm_config.temperature,
        max_tokens: flavor.llm_config.max_tokens || 1000,
        top_p: flavor.llm_config.top_p || 1,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
        top_k: (flavor.llm_config as any).top_k || 40,
        frequency_penalty: flavor.llm_config.frequency_penalty || 0,
        presence_penalty: flavor.llm_config.presence_penalty || 0,
        enabled: flavor.enabled,
      });
    }
  }, [flavor]);

  // Populate defaults from existing flavors when creating new flavor
  useEffect(() => {
    if (
      !flavor &&
      existingFlavorsResponse?.flavors &&
      existingFlavorsResponse.flavors.length > 0
    ) {
      // Find the first enabled flavor to use as template
      const enabledFlavors = existingFlavorsResponse.flavors.filter(
        (f) => f.enabled,
      );
      const defaultFlavor =
        enabledFlavors.length > 0
          ? enabledFlavors[0]
          : existingFlavorsResponse.flavors[0];

      setFormData((prev) => ({
        ...prev,
        // Only populate system_prompt and user_prompt from default flavor
        system_prompt: defaultFlavor.system_prompt,
        user_prompt: defaultFlavor.user_prompt,
        // Optionally also copy other LLM settings
        llm_provider: defaultFlavor.llm_provider,
        llm_model: defaultFlavor.llm_model,
        temperature: defaultFlavor.llm_config.temperature,
        max_tokens: defaultFlavor.llm_config.max_tokens || 1000,
        top_p: defaultFlavor.llm_config.top_p || 1,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
        top_k: (defaultFlavor.llm_config as any).top_k || 40,
        frequency_penalty: defaultFlavor.llm_config.frequency_penalty || 0,
        presence_penalty: defaultFlavor.llm_config.presence_penalty || 0,
      }));
    }
  }, [flavor, existingFlavorsResponse]);

  // Adjust textarea heights when content changes
  useEffect(() => {
    adjustTextAreaHeight(systemPromptRef);
    adjustTextAreaHeight(userPromptRef);
  }, [formData.system_prompt, formData.user_prompt]);

  // Initialize provider and model when enabled models are loaded (only for new flavors)
  useEffect(() => {
    if (!flavor && enabledModels.length > 0 && !formData.llm_provider) {
      const providers = getAvailableProviders();
      if (providers.length > 0) {
        const firstProvider = providers[0].value;
        const modelsForProvider = enabledModels.filter(
          (model) => model.provider_type === firstProvider,
        );
        const firstModel =
          modelsForProvider.length > 0 ? modelsForProvider[0].model_name : "";

        setFormData((prev) => ({
          ...prev,
          llm_provider: firstProvider,
          llm_model: firstModel,
        }));
      }
    }
  }, [flavor, enabledModelsData, formData.llm_provider, enabledModels]);

  // Get available providers from enabled models or fallback to static list
  const getAvailableProviders = () => {
    if (enabledModels.length > 0) {
      const providersSet = new Set<string>();
      enabledModels.forEach((model) => {
        if (model.provider_type) {
          providersSet.add(model.provider_type);
        }
      });

      // Map provider types to friendly labels
      const providerLabels: Record<string, string> = {
        native_openai: "OpenAI",
        native_anthropic: "Anthropic",
        native_google: "Google",
        openrouter: "OpenRouter",
      };

      return Array.from(providersSet).map((provider) => ({
        value: provider,
        label: providerLabels[provider] || provider,
      }));
    }
    return FALLBACK_LLM_PROVIDERS;
  };

  // Get available models for the selected provider
  const getAvailableModels = (provider?: string) => {
    const providerToUse = provider || formData.llm_provider;

    if (enabledModels.length > 0) {
      const modelsForProvider = enabledModels.filter(
        (model) => model.provider_type === providerToUse,
      );
      return modelsForProvider.map((model) => model.model_name);
    }

    // Fallback to static model lists
    return FALLBACK_MODELS[providerToUse as keyof typeof FALLBACK_MODELS] || [];
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.title.trim()) {
      newErrors.title = "Title is required";
    }

    if (!formData.llm_provider) {
      newErrors.llm_provider = "LLM provider is required";
    }

    if (!formData.llm_model) {
      newErrors.llm_model = "LLM model is required";
    }

    if (!formData.system_prompt.trim()) {
      newErrors.system_prompt = "System prompt is required";
    }

    if (!formData.user_prompt.trim()) {
      newErrors.user_prompt = "User prompt is required";
    }

    if (formData.temperature < 0 || formData.temperature > 2) {
      newErrors.temperature = "Temperature must be between 0 and 2";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    const llm_config = {
      temperature: formData.temperature,
      max_tokens: formData.max_tokens,
      top_p: formData.top_p,
      top_k: formData.top_k,
      frequency_penalty: formData.frequency_penalty,
      presence_penalty: formData.presence_penalty,
    };

    if (flavor) {
      // Update existing flavor
      const updateData: UpdatePipelineFlavorRequest = {
        title: formData.title,
        llm_provider: formData.llm_provider,
        llm_model: formData.llm_model,
        llm_config,
        system_prompt: formData.system_prompt,
        user_prompt: formData.user_prompt,
        enabled: formData.enabled,
      };

      updateMutation.mutate({ id: flavor.id, data: updateData });
    } else {
      // Create new flavor
      const createData: CreatePipelineFlavorRequest = {
        pipeline,
        title: formData.title,
        llm_provider: formData.llm_provider,
        llm_model: formData.llm_model,
        llm_config,
        system_prompt: formData.system_prompt,
        user_prompt: formData.user_prompt,
        enabled: formData.enabled,
      };

      createMutation.mutate(createData);
    }
  };

  const isLoading =
    createMutation.isPending || updateMutation.isPending || flavorsLoading;
  const isDefaultFlavor = Boolean(flavor && flavor.title === "Default");

  return (
    <div>
      {errors.submit && (
        <Alert color="failure" className="mb-4">
          {errors.submit}
        </Alert>
      )}

      {configValidationWarnings && configValidationWarnings.length > 0 && (
        <Alert color="warning" className="mb-4">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <div>
              <div className="font-medium">Model Configuration Warnings</div>
              <ul className="mt-1 list-inside list-disc text-sm">
                {configValidationWarnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            </div>
          </div>
        </Alert>
      )}

      {modelCapabilities && (
        <Alert color="info" className="mb-4">
          <div className="flex items-start gap-2">
            <Info className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <div>
              <div className="font-medium">Model Capabilities</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {modelCapabilities.supports_structured_output && (
                  <Badge color="green" size="sm">
                    Structured Output
                  </Badge>
                )}
                {modelCapabilities.supports_function_calling && (
                  <Badge color="green" size="sm">
                    Function Calling
                  </Badge>
                )}
                {modelCapabilities.supports_streaming && (
                  <Badge color="green" size="sm">
                    Streaming
                  </Badge>
                )}
                {modelCapabilities.max_tokens_limit && (
                  <Badge color="blue" size="sm">
                    Max Tokens: {modelCapabilities.max_tokens_limit}
                  </Badge>
                )}
                {modelCapabilities.context_window && (
                  <Badge color="blue" size="sm">
                    Context: {modelCapabilities.context_window}
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </Alert>
      )}

      {isDefaultFlavor && (
        <Alert color="info" className="mb-4">
          The Default flavor is read-only and cannot be edited or deleted from
          the UI.
        </Alert>
      )}

      {!flavor &&
        existingFlavorsResponse?.flavors &&
        existingFlavorsResponse.flavors.length > 0 && (
          <Alert color="info" className="mb-4">
            <div className="flex items-center gap-2">
              <span className="font-medium">Defaults populated</span>
              <span>
                System and user prompts have been populated from the default
                flavor for this pipeline type.
              </span>
            </div>
          </Alert>
        )}

      {flavorsLoading && !flavor && (
        <Alert color="blue" className="mb-4">
          <div className="flex items-center gap-2">
            <Spinner size="sm" />
            <span>Loading default values...</span>
          </div>
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="title">Flavor Title</Label>
            <TextInput
              id="title"
              value={formData.title}
              onChange={(e) =>
                setFormData({ ...formData, title: e.target.value })
              }
              color={errors.title ? "failure" : undefined}
              placeholder="e.g., Creative Terms, Technical Definitions"
              required
              disabled={isDefaultFlavor}
            />
            {errors.title && (
              <p className="mt-1 text-sm text-red-600 dark:text-red-400">
                {errors.title}
              </p>
            )}
          </div>

          <div>
            <Label htmlFor="enabled">Status</Label>
            <Select
              id="enabled"
              value={formData.enabled.toString()}
              onChange={(e) =>
                setFormData({ ...formData, enabled: e.target.value === "true" })
              }
              disabled={isDefaultFlavor}
            >
              <option value="true">Enabled</option>
              <option value="false">Disabled</option>
            </Select>
          </div>
        </div>

        {/* LLM Configuration */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="llm_provider">LLM Provider</Label>
            <Select
              id="llm_provider"
              value={formData.llm_provider}
              onChange={(e) => {
                const provider = e.target.value;
                const models = getAvailableModels(provider);
                setFormData((prev) => ({
                  ...prev,
                  llm_provider: provider,
                  llm_model: models[0] || "",
                }));
              }}
              disabled={isDefaultFlavor}
              color={errors.llm_provider ? "failure" : undefined}
            >
              {getAvailableProviders().map((provider) => (
                <option key={provider.value} value={provider.value}>
                  {provider.label}
                </option>
              ))}
            </Select>
            {errors.llm_provider && (
              <p className="mt-1 text-sm text-red-600 dark:text-red-400">
                {errors.llm_provider}
              </p>
            )}
          </div>

          <div>
            <Label htmlFor="llm_model">Model</Label>
            <Select
              id="llm_model"
              value={formData.llm_model}
              onChange={(e) =>
                setFormData({ ...formData, llm_model: e.target.value })
              }
              disabled={isDefaultFlavor}
              color={errors.llm_model ? "failure" : undefined}
            >
              {getAvailableModels().map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </Select>
            {errors.llm_model && (
              <p className="mt-1 text-sm text-red-600 dark:text-red-400">
                {errors.llm_model}
              </p>
            )}
          </div>
        </div>

        {/* LLM Parameters */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
          <div>
            <Label htmlFor="temperature">Temperature</Label>
            <TextInput
              id="temperature"
              type="number"
              value={formData.temperature.toString()}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setFormData({
                  ...formData,
                  temperature: parseFloat(e.target.value) || 0,
                })
              }
              min={0}
              max={2}
              step={0.1}
              color={errors.temperature ? "failure" : undefined}
              disabled={isDefaultFlavor}
            />
            {errors.temperature && (
              <p className="mt-1 text-sm text-red-600 dark:text-red-400">
                {errors.temperature}
              </p>
            )}
          </div>

          <div>
            <Label htmlFor="max_tokens">
              Max Tokens
              {modelCapabilities?.max_tokens_limit && (
                <span className="ml-1 text-sm text-gray-500">
                  (limit: {modelCapabilities.max_tokens_limit})
                </span>
              )}
            </Label>
            <TextInput
              id="max_tokens"
              type="number"
              value={formData.max_tokens.toString()}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setFormData({
                  ...formData,
                  max_tokens: parseInt(e.target.value) || 1000,
                })
              }
              min={1}
              max={modelCapabilities?.max_tokens_limit || 8000}
              disabled={isDefaultFlavor}
            />
          </div>

          <div>
            <Label htmlFor="top_p">Top P</Label>
            <TextInput
              id="top_p"
              type="number"
              value={formData.top_p.toString()}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setFormData({
                  ...formData,
                  top_p: parseFloat(e.target.value) || 1,
                })
              }
              min={0}
              max={1}
              step={0.1}
              disabled={isDefaultFlavor}
            />
          </div>

          {(!modelCapabilities || modelCapabilities.supports_top_k) && (
            <div>
              <Label htmlFor="top_k">Top K</Label>
              <TextInput
                id="top_k"
                type="number"
                value={formData.top_k.toString()}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setFormData({
                    ...formData,
                    top_k: parseInt(e.target.value) || 40,
                  })
                }
                min={1}
                max={100}
                disabled={isDefaultFlavor}
              />
            </div>
          )}

          {(!modelCapabilities ||
            modelCapabilities.supports_frequency_penalty) && (
            <div>
              <Label htmlFor="frequency_penalty">Frequency Penalty</Label>
              <TextInput
                id="frequency_penalty"
                type="number"
                value={formData.frequency_penalty.toString()}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setFormData({
                    ...formData,
                    frequency_penalty: parseFloat(e.target.value) || 0,
                  })
                }
                min={-2}
                max={2}
                step={0.1}
                disabled={isDefaultFlavor}
              />
            </div>
          )}

          {(!modelCapabilities ||
            modelCapabilities.supports_presence_penalty) && (
            <div>
              <Label htmlFor="presence_penalty">Presence Penalty</Label>
              <TextInput
                id="presence_penalty"
                type="number"
                value={formData.presence_penalty.toString()}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setFormData({
                    ...formData,
                    presence_penalty: parseFloat(e.target.value) || 0,
                  })
                }
                min={-2}
                max={2}
                step={0.1}
                disabled={isDefaultFlavor}
              />
            </div>
          )}
        </div>

        {/* Prompts */}
        <div className="space-y-4">
          <div>
            <Label htmlFor="system_prompt">System Prompt</Label>
            <Textarea
              id="system_prompt"
              ref={systemPromptRef}
              value={formData.system_prompt}
              onChange={(e) => {
                setFormData({ ...formData, system_prompt: e.target.value });
                setTimeout(() => adjustTextAreaHeight(systemPromptRef), 0);
              }}
              color={errors.system_prompt ? "failure" : undefined}
              placeholder="Define the role and context for the AI assistant..."
              disabled={isDefaultFlavor}
              style={{ minHeight: "100px", resize: "none" }}
            />
            {errors.system_prompt && (
              <p className="mt-1 text-sm text-red-600 dark:text-red-400">
                {errors.system_prompt}
              </p>
            )}
          </div>

          <div>
            <Label htmlFor="user_prompt">User Prompt Template</Label>
            <Textarea
              id="user_prompt"
              ref={userPromptRef}
              value={formData.user_prompt}
              onChange={(e) => {
                setFormData({ ...formData, user_prompt: e.target.value });
                setTimeout(() => adjustTextAreaHeight(userPromptRef), 0);
              }}
              color={errors.user_prompt ? "failure" : undefined}
              placeholder="Template for user requests (use variables like {title}, {context}, etc.)..."
              disabled={isDefaultFlavor}
              style={{ minHeight: "100px", resize: "none" }}
            />
            {errors.user_prompt && (
              <p className="mt-1 text-sm text-red-600 dark:text-red-400">
                {errors.user_prompt}
              </p>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 border-t border-gray-200 pt-4 dark:border-gray-700">
          {!isDefaultFlavor ? (
            <>
              <Button type="submit" color="blue" disabled={isLoading}>
                {isLoading ? (
                  <Spinner size="sm" className="mr-2" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                {flavor ? "Update" : "Create"} Flavor
              </Button>
              <Button type="button" color="gray" onClick={onClose}>
                Cancel
              </Button>
            </>
          ) : (
            <Button type="button" color="gray" onClick={onClose}>
              Close
            </Button>
          )}
        </div>
      </form>
    </div>
  );
};
