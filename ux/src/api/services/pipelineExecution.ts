/**
 * Pipeline Execution Service
 *
 * Service for executing LLM pipelines using the new unified pipeline execution system
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type { components } from "@/api/client/types";

// Type aliases for the new pipeline execution system
export type GenericPipelineExecutionRequest =
  components["schemas"]["GenericPipelineExecutionRequest"];
export type GenericPipelineExecutionResponse =
  components["schemas"]["GenericPipelineExecutionResponse"];
export type { PipelineType } from "./pipelineFlavors";

// Legacy compatibility types for easier migration
export interface LegacyTermDefinitionRequest {
  term: string;
  domain_title?: string;
  domain_definition?: string;
  parent_term_title?: string;
  parent_term_definition?: string;
  parent_relationship_predicate?: string;
  component_terms?: Array<{
    title: string;
    definition?: string;
    relationship_predicate?: string;
  }>;
  dbpedia_context?: Record<string, any>;
  wikidata_context?: Record<string, any>;
  flavor?: string;
}

export interface LegacyDomainDefinitionRequest {
  domain_title: string;
  context?: string;
  flavor?: string;
}

export interface LegacyLayerDefinitionRequest {
  layer_title: string;
  context?: string;
  flavor?: string;
}

// Streaming response chunk interface
export interface StreamingChunk {
  content?: string;
  done?: boolean;
  execution_id?: string;
  error?: string;
}

export class PipelineExecutionService extends BaseService {
  /**
   * Execute a pipeline with the new unified execution system
   */
  async executePipeline(
    request: GenericPipelineExecutionRequest,
  ): Promise<GenericPipelineExecutionResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(request.pipeline_type, "pipeline_type");
      this.validateRequired(request.flavor_id, "flavor_id");
      this.validateRequired(request.context_data, "context_data");

      return this.postResource<GenericPipelineExecutionResponse>(
        `${ENDPOINTS.LLM}/execute_pipeline`,
        request,
      );
    }, "executing pipeline");
  }

  /**
   * Execute a pipeline with streaming response
   * Note: This is a simplified implementation for now - streaming will need custom handling
   */
  async executePipelineStream(
    request: GenericPipelineExecutionRequest,
    onChunk?: (chunk: StreamingChunk) => void,
  ): Promise<GenericPipelineExecutionResponse> {
    // For now, fall back to non-streaming execution
    // TODO: Implement proper streaming with server-sent events
    console.warn('Streaming not yet implemented, falling back to regular execution');
    return this.executePipeline(request);
  }

  /**
   * Legacy compatibility: Execute term definition suggestion
   */
  async executeTermDefinition(
    request: LegacyTermDefinitionRequest,
  ): Promise<GenericPipelineExecutionResponse> {
    const pipelineRequest: GenericPipelineExecutionRequest = {
      pipeline_type: 'suggest_term_definition',
      flavor_id: request.flavor || 'default',
      context_data: {
        term: request.term,
        domain_title: request.domain_title,
        domain_definition: request.domain_definition,
        parent_term_title: request.parent_term_title,
        parent_term_definition: request.parent_term_definition,
        parent_relationship_predicate: request.parent_relationship_predicate,
        component_terms: request.component_terms,
        dbpedia_context: request.dbpedia_context,
        wikidata_context: request.wikidata_context,
      },
    };

    return this.executePipeline(pipelineRequest);
  }

  /**
   * Legacy compatibility: Execute domain definition suggestion
   */
  async executeDomainDefinition(
    request: LegacyDomainDefinitionRequest,
  ): Promise<GenericPipelineExecutionResponse> {
    const pipelineRequest: GenericPipelineExecutionRequest = {
      pipeline_type: 'suggest_domain_definition',
      flavor_id: request.flavor || 'default',
      context_data: {
        domain_title: request.domain_title,
        context: request.context,
      },
    };

    return this.executePipeline(pipelineRequest);
  }

  /**
   * Legacy compatibility: Execute layer definition suggestion
   */
  async executeLayerDefinition(
    request: LegacyLayerDefinitionRequest,
  ): Promise<GenericPipelineExecutionResponse> {
    const pipelineRequest: GenericPipelineExecutionRequest = {
      pipeline_type: 'suggest_layer_definition',
      flavor_id: request.flavor || 'default',
      context_data: {
        layer_title: request.layer_title,
        context: request.context,
      },
    };

    return this.executePipeline(pipelineRequest);
  }

  /**
   * Convert new generic response to legacy term definition response format
   */
  convertToLegacyTermResponse(response: GenericPipelineExecutionResponse): any {
    // Parse the response_content as JSON if it's a string
    let parsedResult: any = response.response_content;
    if (typeof response.response_content === 'string') {
      try {
        parsedResult = JSON.parse(response.response_content);
      } catch {
        // If parsing fails, treat as plain text definition
        parsedResult = { definition: response.response_content };
      }
    }

    return {
      definition: parsedResult?.definition || response.response_content,
      reasoning: parsedResult?.reasoning,
      discrepancies: parsedResult?.discrepancies,
      execution_id: response.execution_id,
      token_usage: response.token_usage,
    };
  }

  /**
   * Convert new generic response to legacy domain definition response format
   */
  convertToLegacyDomainResponse(response: GenericPipelineExecutionResponse): any {
    let parsedResult: any = response.response_content;
    if (typeof response.response_content === 'string') {
      try {
        parsedResult = JSON.parse(response.response_content);
      } catch {
        parsedResult = { definition: response.response_content };
      }
    }

    return {
      definition: parsedResult?.definition || response.response_content,
      reasoning: parsedResult?.reasoning,
      execution_id: response.execution_id,
      token_usage: response.token_usage,
    };
  }

  /**
   * Convert new generic response to legacy layer definition response format
   */
  convertToLegacyLayerResponse(response: GenericPipelineExecutionResponse): any {
    let parsedResult: any = response.response_content;
    if (typeof response.response_content === 'string') {
      try {
        parsedResult = JSON.parse(response.response_content);
      } catch {
        parsedResult = { definition: response.response_content };
      }
    }

    return {
      definition: parsedResult?.definition || response.response_content,
      reasoning: parsedResult?.reasoning,
      execution_id: response.execution_id,
      token_usage: response.token_usage,
    };
  }
}

// Export singleton instance
export const pipelineExecutionService = new PipelineExecutionService();