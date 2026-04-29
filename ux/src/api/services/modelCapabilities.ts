/**
 * Model Capabilities Service
 *
 * Service for querying LLM model capabilities and constraints
 */

import { BaseService } from "./base";
import type {
  ModelCapabilitiesResponse,
  SupportedModelsResponse,
} from "./missingTypes";

// Re-export types for use in hooks and components
export type { ModelCapabilitiesResponse, SupportedModelsResponse };

export interface ModelCapabilities {
  supports_temperature: boolean;
  supports_top_p: boolean;
  supports_top_k: boolean;
  supports_max_tokens: boolean;
  supports_frequency_penalty: boolean;
  supports_presence_penalty: boolean;
  supports_structured_output: boolean;
  supports_function_calling: boolean;
  supports_streaming: boolean;
  max_tokens_limit?: number;
  context_window?: number;
  provider: string;
  model_family: string;
}

export class ModelCapabilitiesService extends BaseService {
  /**
   * List all supported models with their capabilities
   * @param provider Optional provider filter (openai, anthropic, etc.)
   * @returns List of all supported models with capabilities
   */
  async listSupportedModels(
    provider?: string,
  ): Promise<SupportedModelsResponse> {
    return this.withErrorContext(async () => {
      const params = provider
        ? `?provider=${encodeURIComponent(provider)}`
        : "";
      return this.getResource<SupportedModelsResponse>(
        `/api/model-capabilities${params}`,
      );
    }, "listing supported models");
  }

  /**
   * Get capabilities for a specific model
   * @param modelName The name of the model to get capabilities for
   * @returns Model capabilities and constraints
   */
  async getModelCapabilities(
    modelName: string,
  ): Promise<ModelCapabilitiesResponse> {
    this.validateRequired(modelName, "modelName");

    return this.withErrorContext(async () => {
      return this.getResource<ModelCapabilitiesResponse>(
        `/api/model-capabilities/${encodeURIComponent(modelName)}`,
      );
    }, `getting capabilities for model ${modelName}`);
  }

  /**
   * List models by provider
   * @param providerName The provider name (openai, anthropic, etc.)
   * @returns List of models for the specified provider
   */
  async listModelsByProvider(
    providerName: string,
  ): Promise<SupportedModelsResponse> {
    this.validateRequired(providerName, "providerName");

    return this.withErrorContext(async () => {
      return this.getResource<SupportedModelsResponse>(
        `/api/model-capabilities/providers/${encodeURIComponent(providerName)}`,
      );
    }, `listing models for provider ${providerName}`);
  }

  /**
   * Get parsed capabilities with type safety
   * @param modelName The name of the model
   * @returns Typed model capabilities
   */
  async getTypedModelCapabilities(
    modelName: string,
  ): Promise<ModelCapabilities> {
    const response = await this.getModelCapabilities(modelName);

    // Parse the capabilities object which comes as a generic object

    const capabilities = response.capabilities as any;

    return {
      supports_temperature: capabilities.supports_temperature ?? true,
      supports_top_p: capabilities.supports_top_p ?? true,
      supports_top_k: capabilities.supports_top_k ?? false,
      supports_max_tokens: capabilities.supports_max_tokens ?? true,
      supports_frequency_penalty:
        capabilities.supports_frequency_penalty ?? false,
      supports_presence_penalty:
        capabilities.supports_presence_penalty ?? false,
      supports_structured_output:
        capabilities.supports_structured_output ?? false,
      supports_function_calling:
        capabilities.supports_function_calling ?? false,
      supports_streaming: capabilities.supports_streaming ?? true,
      max_tokens_limit: capabilities.max_tokens_limit,
      context_window: capabilities.context_window,
      provider: capabilities.provider ?? "unknown",
      model_family: capabilities.model_family ?? "unknown",
    };
  }

  /**
   * Check if a model supports a specific parameter
   * @param modelName The model name
   * @param parameter The parameter to check
   * @returns Whether the model supports the parameter
   */
  async supportsParameter(
    modelName: string,
    parameter: keyof ModelCapabilities,
  ): Promise<boolean> {
    const capabilities = await this.getTypedModelCapabilities(modelName);
    return Boolean(capabilities[parameter]);
  }

  /**
   * Get models grouped by provider
   * @returns Models grouped by provider
   */
  async getModelsByProvider(): Promise<
    Record<string, ModelCapabilitiesResponse[]>
  > {
    const allModels = await this.listSupportedModels();

    return allModels.models.reduce(
      (acc, model) => {
        const provider = (model.capabilities as any)?.provider ?? "unknown";
        if (!acc[provider]) {
          acc[provider] = [];
        }
        acc[provider].push(model);
        return acc;
      },
      {} as Record<string, ModelCapabilitiesResponse[]>,
    );
  }

  /**
   * Validate LLM configuration against model capabilities
   * @param modelName The model name
   * @param config The LLM configuration to validate
   * @returns Array of validation warnings
   */
  async validateLLMConfig(
    modelName: string,
    config: {
      temperature?: number;
      top_p?: number;
      top_k?: number;
      max_tokens?: number;
      frequency_penalty?: number;
      presence_penalty?: number;
    },
  ): Promise<string[]> {
    const capabilities = await this.getTypedModelCapabilities(modelName);
    const warnings: string[] = [];

    if (config.top_k !== undefined && !capabilities.supports_top_k) {
      warnings.push(`${modelName} doesn't support top_k parameter`);
    }

    if (
      config.frequency_penalty !== undefined &&
      !capabilities.supports_frequency_penalty
    ) {
      warnings.push(`${modelName} doesn't support frequency_penalty parameter`);
    }

    if (
      config.presence_penalty !== undefined &&
      !capabilities.supports_presence_penalty
    ) {
      warnings.push(`${modelName} doesn't support presence_penalty parameter`);
    }

    if (
      config.max_tokens &&
      capabilities.max_tokens_limit &&
      config.max_tokens > capabilities.max_tokens_limit
    ) {
      warnings.push(
        `Max tokens will be capped at ${capabilities.max_tokens_limit} for ${modelName}`,
      );
    }

    return warnings;
  }
}

// Export a singleton instance
export const modelCapabilitiesService = new ModelCapabilitiesService();
