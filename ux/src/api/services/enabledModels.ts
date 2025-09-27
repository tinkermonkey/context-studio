/**
 * Enabled Models Service
 *
 * Service for managing enabled LLM models and provider configurations
 */

import { BaseService } from "./base";

export type ProviderType = 'native_openai' | 'native_anthropic' | 'native_google' | 'openrouter';
export type CostTier = 'low' | 'medium' | 'high';

export interface EnabledModelConfig {
  model_name: string;
  provider_type: ProviderType;
  display_name: string;
  enabled: boolean;
  api_key_env_var: string;
  custom_endpoint: string | null;
  model_override: string | null;
  description: string;
  cost_tier: CostTier;
  tags: string[];
}

export interface EnabledModelsResponse {
  models: EnabledModelConfig[];
  total_count: number;
}

export interface ProviderSummary {
  total_models: number;
  enabled_models: number;
  models: string[];
}

export interface ProvidersStatusResponse {
  providers: Record<ProviderType, ProviderSummary>;
}

export interface ModelCreateRequest {
  model_name: string;
  provider_type: ProviderType;
  display_name: string;
  enabled: boolean;
  api_key_env_var: string;
  custom_endpoint?: string | null;
  model_override?: string | null;
  description: string;
  cost_tier: CostTier;
  tags: string[];
}

export interface ModelUpdateRequest {
  display_name?: string;
  enabled?: boolean;
  api_key_env_var?: string;
  custom_endpoint?: string | null;
  model_override?: string | null;
  description?: string;
  cost_tier?: CostTier;
  tags?: string[];
}

export class EnabledModelsService extends BaseService {
  /**
   * List enabled models with optional filtering
   */
  async listEnabledModels(params?: {
    enabled_only?: boolean;
    provider_type?: ProviderType;
    tag?: string;
  }): Promise<EnabledModelsResponse> {
    return this.withErrorContext(async () => {
      const searchParams = new URLSearchParams();
      if (params?.enabled_only) searchParams.set('enabled_only', 'true');
      if (params?.provider_type) searchParams.set('provider_type', params.provider_type);
      if (params?.tag) searchParams.set('tag', params.tag);

      const query = searchParams.toString();
      const url = query ? `/api/enabled-models?${query}` : '/api/enabled-models';

      return this.getResource<EnabledModelsResponse>(url);
    }, "listing enabled models");
  }

  /**
   * Get specific enabled model configuration
   */
  async getEnabledModel(modelName: string): Promise<EnabledModelConfig> {
    this.validateRequired(modelName, "modelName");

    return this.withErrorContext(async () => {
      return this.getResource<EnabledModelConfig>(`/api/enabled-models/${encodeURIComponent(modelName)}`);
    }, `getting enabled model ${modelName}`);
  }

  /**
   * Create new enabled model
   */
  async createEnabledModel(config: ModelCreateRequest): Promise<EnabledModelConfig> {
    this.validateRequired(config.model_name, "model_name");
    this.validateRequired(config.provider_type, "provider_type");
    this.validateRequired(config.display_name, "display_name");

    return this.withErrorContext(async () => {
      return this.request<EnabledModelConfig>({
        url: "/api/enabled-models",
        method: "POST",
        data: config
      });
    }, `creating enabled model ${config.model_name}`);
  }

  /**
   * Update enabled model configuration
   */
  async updateEnabledModel(modelName: string, updates: ModelUpdateRequest): Promise<EnabledModelConfig> {
    this.validateRequired(modelName, "modelName");

    return this.withErrorContext(async () => {
      return this.request<EnabledModelConfig>({
        url: `/api/enabled-models/${encodeURIComponent(modelName)}`,
        method: "PUT",
        data: updates
      });
    }, `updating enabled model ${modelName}`);
  }

  /**
   * Delete enabled model
   */
  async deleteEnabledModel(modelName: string): Promise<void> {
    this.validateRequired(modelName, "modelName");

    return this.withErrorContext(async () => {
      await this.request<void>({
        url: `/api/enabled-models/${encodeURIComponent(modelName)}`,
        method: "DELETE"
      });
    }, `deleting enabled model ${modelName}`);
  }

  /**
   * Enable a model
   */
  async enableModel(modelName: string): Promise<void> {
    this.validateRequired(modelName, "modelName");

    return this.withErrorContext(async () => {
      await this.request<void>({
        url: `/api/enabled-models/${encodeURIComponent(modelName)}/enable`,
        method: "POST"
      });
    }, `enabling model ${modelName}`);
  }

  /**
   * Disable a model
   */
  async disableModel(modelName: string): Promise<void> {
    this.validateRequired(modelName, "modelName");

    return this.withErrorContext(async () => {
      await this.request<void>({
        url: `/api/enabled-models/${encodeURIComponent(modelName)}/disable`,
        method: "POST"
      });
    }, `disabling model ${modelName}`);
  }

  /**
   * Toggle model enabled state
   */
  async toggleModel(modelName: string, enabled: boolean): Promise<void> {
    return enabled ? this.enableModel(modelName) : this.disableModel(modelName);
  }

  /**
   * Get provider summary
   */
  async getProvidersStatus(): Promise<ProvidersStatusResponse> {
    return this.withErrorContext(async () => {
      return this.getResource<ProvidersStatusResponse>("/api/enabled-models/providers/summary");
    }, "getting providers status");
  }

  /**
   * Get models grouped by provider
   */
  async getModelsByProvider(): Promise<Record<ProviderType, EnabledModelConfig[]>> {
    const response = await this.listEnabledModels();

    return response.models.reduce((acc, model) => {
      const provider = model.provider_type;
      if (!acc[provider]) {
        acc[provider] = [];
      }
      acc[provider].push(model);
      return acc;
    }, {} as Record<ProviderType, EnabledModelConfig[]>);
  }

  /**
   * Get enabled models only
   */
  async getEnabledModelsOnly(): Promise<EnabledModelConfig[]> {
    const response = await this.listEnabledModels({ enabled_only: true });
    return response.models;
  }

  /**
   * Get models by tag
   */
  async getModelsByTag(tag: string): Promise<EnabledModelConfig[]> {
    const response = await this.listEnabledModels({ tag });
    return response.models;
  }

  /**
   * Get models by cost tier
   */
  async getModelsByCostTier(costTier: CostTier): Promise<EnabledModelConfig[]> {
    const response = await this.listEnabledModels();
    return response.models.filter(model => model.cost_tier === costTier);
  }

  /**
   * Validate provider configuration
   */
  async validateProviderConfig(providerType: ProviderType): Promise<{
    valid: boolean;
    issues: string[];
  }> {
    // This would need to be implemented on the backend
    // For now, return a placeholder
    return {
      valid: true,
      issues: []
    };
  }
}

// Export a singleton instance
export const enabledModelsService = new EnabledModelsService();