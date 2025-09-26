import React, { useState, useEffect, useRef } from "react";
import {
  Button,
  Card,
  Label,
  TextInput,
  Textarea,
  Select,
  Alert,
  Spinner,
} from "flowbite-react";
import { ArrowLeft, Save } from "lucide-react";
import {
  useCreatePipelineFlavor,
  useUpdatePipelineFlavor,
  usePipelineFlavors,
} from "@/api/hooks/pipelineFlavors";
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

const LLM_PROVIDERS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "ollama", label: "Ollama" },
  { value: "azure", label: "Azure OpenAI" },
];

const OPENAI_MODELS = [
  "gpt-5",
  "gpt-5-mini",
  "gpt-5-nano",
  "gpt-4o",
  "gpt-4o-mini",
  "gpt-4-turbo",
  "gpt-3.5-turbo",
  "o3-mini",
  "o3",
  "o4-mini",
  "o4",
];

const ANTHROPIC_MODELS = [
  "claude-3-5-sonnet-20241022",
  "claude-3-5-haiku-20241022",
  "claude-3-opus-20240229",
];

export const PipelineFlavorEditor: React.FC<PipelineFlavorEditorProps> = ({
  pipeline,
  flavor,
  onClose,
}) => {
  const [formData, setFormData] = useState({
    title: "",
    llm_provider: "openai",
    llm_model: "gpt-4o-mini",
    system_prompt: "",
    user_prompt: "",
    temperature: 0.7,
    max_tokens: 1000,
    top_p: 1,
    frequency_penalty: 0,
    presence_penalty: 0,
    enabled: true,
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const systemPromptRef = useRef<HTMLTextAreaElement>(null) as React.RefObject<HTMLTextAreaElement>;
  const userPromptRef = useRef<HTMLTextAreaElement>(null) as React.RefObject<HTMLTextAreaElement>;

  const adjustTextAreaHeight = (textAreaRef: React.RefObject<HTMLTextAreaElement>) => {
    if (textAreaRef.current) {
      textAreaRef.current.style.height = 'auto';
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

  const getAvailableModels = () => {
    switch (formData.llm_provider) {
      case "openai":
      case "azure":
        return OPENAI_MODELS;
      case "anthropic":
        return ANTHROPIC_MODELS;
      case "ollama":
        return ["llama3.2", "llama3.1", "mistral", "codellama"];
      default:
        return [];
    }
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.title.trim()) {
      newErrors.title = "Title is required";
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
    <Card>

      {errors.submit && (
        <Alert color="failure" className="mb-4">
          {errors.submit}
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
                const models = getAvailableModels();
                setFormData({
                  ...formData,
                  llm_provider: provider,
                  llm_model: models[0] || "",
                });
              }}
              disabled={isDefaultFlavor}
            >
              {LLM_PROVIDERS.map((provider) => (
                <option key={provider.value} value={provider.value}>
                  {provider.label}
                </option>
              ))}
            </Select>
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
            >
              {getAvailableModels().map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {/* LLM Parameters */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
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
            <Label htmlFor="max_tokens">Max Tokens</Label>
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
              max={8000}
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
              style={{ minHeight: '100px', resize: 'none' }}
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
              style={{ minHeight: '100px', resize: 'none' }}
            />
            {errors.user_prompt && (
              <p className="mt-1 text-sm text-red-600 dark:text-red-400">
                {errors.user_prompt}
              </p>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 border-t border-gray-200 pt-4 dark:border-gray-700 justify-end">
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
    </Card>
  );
};
