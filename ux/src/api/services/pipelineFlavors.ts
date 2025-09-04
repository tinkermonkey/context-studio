/**
 * Pipeline Flavors Service
 * 
 * Service for managing LLM pipeline configuration flavors
 */

import { BaseService } from './base';
import { ENDPOINTS } from '../config';
import type { components } from '@/api/client/types';

// Type aliases for better readability
export type PipelineFlavor = components['schemas']['PipelineFlavor'];
export type CreatePipelineFlavorRequest = components['schemas']['CreatePipelineFlavorRequest'];
export type UpdatePipelineFlavorRequest = components['schemas']['UpdatePipelineFlavorRequest'];
export type PipelineFlavorListResponse = components['schemas']['PipelineFlavorListResponse'];
export type PipelineType = components['schemas']['PipelineType'];

export interface ListFlavorsParams extends Record<string, unknown> {
  pipeline?: PipelineType;
}

export class PipelineFlavorService extends BaseService {
  /**
   * List all pipeline flavors
   */
  async list(params?: ListFlavorsParams): Promise<PipelineFlavorListResponse> {
    return this.withErrorContext(
      () => this.getResource<PipelineFlavorListResponse>(ENDPOINTS.PIPELINE_FLAVORS, params),
      'list pipeline flavors'
    );
  }

  /**
   * Create a new pipeline flavor
   */
  async create(data: CreatePipelineFlavorRequest): Promise<PipelineFlavor> {
    return this.withErrorContext(
      () => {
        this.validateRequired(data, 'Pipeline flavor data');
        this.validateRequired(data.pipeline, 'Pipeline type');
        this.validateRequired(data.title, 'Flavor title');
        this.validateRequired(data.llm_provider, 'LLM provider');
        this.validateRequired(data.llm_model, 'LLM model');
        this.validateRequired(data.system_prompt, 'System prompt');
        this.validateRequired(data.user_prompt, 'User prompt');
        
        this.sanitizeString(data.title, 'Flavor title', 255);
        this.sanitizeString(data.llm_provider, 'LLM provider', 100);
        this.sanitizeString(data.llm_model, 'LLM model', 255);
        this.sanitizeString(data.system_prompt, 'System prompt', 10000);
        this.sanitizeString(data.user_prompt, 'User prompt', 10000);
        
        return this.postResource<PipelineFlavor>(ENDPOINTS.PIPELINE_FLAVORS, data);
      },
      'create pipeline flavor'
    );
  }

  /**
   * Get a specific pipeline flavor by ID
   */
  async get(flavorId: string): Promise<PipelineFlavor> {
    return this.withErrorContext(
      () => {
        this.validateRequired(flavorId, 'Flavor ID');
        return this.getResource<PipelineFlavor>(`${ENDPOINTS.PIPELINE_FLAVORS}/${flavorId}`);
      },
      'get pipeline flavor'
    );
  }

  /**
   * Update an existing pipeline flavor
   */
  async update(flavorId: string, data: UpdatePipelineFlavorRequest): Promise<PipelineFlavor> {
    return this.withErrorContext(
      () => {
        this.validateRequired(flavorId, 'Flavor ID');
        this.validateRequired(data, 'Pipeline flavor update data');
        
        if (data.title) {
          this.sanitizeString(data.title, 'Flavor title', 255);
        }
        if (data.llm_provider) {
          this.sanitizeString(data.llm_provider, 'LLM provider', 100);
        }
        if (data.llm_model) {
          this.sanitizeString(data.llm_model, 'LLM model', 255);
        }
        if (data.system_prompt) {
          this.sanitizeString(data.system_prompt, 'System prompt', 10000);
        }
        if (data.user_prompt) {
          this.sanitizeString(data.user_prompt, 'User prompt', 10000);
        }
        
        return this.putResource<PipelineFlavor>(`${ENDPOINTS.PIPELINE_FLAVORS}/${flavorId}`, data);
      },
      'update pipeline flavor'
    );
  }

  /**
   * Delete a pipeline flavor
   */
  async delete(flavorId: string): Promise<void> {
    return this.withErrorContext(
      () => {
        this.validateRequired(flavorId, 'Flavor ID');
        return this.deleteResource<void>(`${ENDPOINTS.PIPELINE_FLAVORS}/${flavorId}`);
      },
      'delete pipeline flavor'
    );
  }
}

// Export singleton instance
export const pipelineFlavorService = new PipelineFlavorService();
