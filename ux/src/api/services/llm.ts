/**
 * LLM Service
 *
 * Service for Large Language Model operations including definition suggestions
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type {
  PipelineExecutionRequest,
  PipelineExecutionResponse,
} from "./missingTypes";
import { pipelineExecutionService } from "./pipelineExecution";

// Type aliases for better readability - using the latest OpenAPI schema
export type DefinitionSuggestionRequest = PipelineExecutionRequest;
export type DefinitionSuggestionResponse = PipelineExecutionResponse;
export type DomainDefinitionRequest = PipelineExecutionRequest;
export type DomainDefinitionResponse = PipelineExecutionResponse;
export type LayerDefinitionRequest = PipelineExecutionRequest;
export type LayerDefinitionResponse = PipelineExecutionResponse;

// Re-export request/response types
export type { PipelineExecutionRequest, PipelineExecutionResponse };

// Legacy compatibility: Define ComponentTerm locally since it may not exist in new schema
export interface ComponentTerm {
  title: string;
  definition?: string;
  relationship_predicate?: string;
}

// Legacy interface for backward compatibility
export interface SelectedRelation {
  predicate: string;
  object: string;
  weight: number;
  text?: string;
}

export interface LLMSuccessResponse {
  success: boolean;
  data: DefinitionSuggestionResponse;
}

export interface LLMErrorResponse {
  success: boolean;
  error: string;
  error_type: string;
  details?: string;
}

export interface LLMHealthResponse {
  status: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  model_info: Record<string, any>;
  timestamp: string;
}

export class LLMService extends BaseService {
  /**
   * Execute a pipeline using the new generic execution system
   */
  private async executePipeline(
    request: DefinitionSuggestionRequest,
  ): Promise<DefinitionSuggestionResponse> {
    return pipelineExecutionService.executePipeline(request);
  }

  /**
   * Generate a term definition suggestion based on provided context using LLM
   * @param request The term definition suggestion request containing term and context
   * @returns Term definition suggestion with reasoning
   */
  async suggestTermDefinition(
    request: DefinitionSuggestionRequest,
  ): Promise<DefinitionSuggestionResponse> {
    return this.withErrorContext(async () => {
      // For backwards compatibility, support legacy request format
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      if ((request as any).term !== undefined) {
        // Legacy request format - validate and convert to new format
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const legacyRequest = request as any;
        const newRequest: DefinitionSuggestionRequest = {
          pipeline_type: "suggest_term_definition",
          flavor_id: legacyRequest.flavor || "default",
          context_data: {
            term: this.sanitizeString(String(legacyRequest.term || ""), "term"),
            domain_title: legacyRequest.domain_title,
            domain_definition: legacyRequest.domain_definition,
            parent_term_title: legacyRequest.parent_term_title,
            parent_term_definition: legacyRequest.parent_term_definition,
            parent_relationship_predicate:
              legacyRequest.parent_relationship_predicate,
            component_terms: legacyRequest.component_terms,
            dbpedia_context: legacyRequest.dbpedia_context,
            wikidata_context: legacyRequest.wikidata_context,
          },
        };
        return this.executePipeline(newRequest);
      }

      // New format - validate required fields
      this.validateRequired(request.pipeline_type, "pipeline_type");
      this.validateRequired(request.flavor_id, "flavor_id");
      this.validateRequired(request.context_data, "context_data");

      return this.executePipeline(request);
    }, "suggesting term definition");
  }

  /**
   * Generate a domain definition suggestion based on provided context using LLM
   * @param request The domain definition suggestion request containing domain and context
   * @returns Domain definition suggestion with reasoning
   */
  async suggestDomainDefinition(
    request: DomainDefinitionRequest,
  ): Promise<DomainDefinitionResponse> {
    return this.withErrorContext(async () => {
      // For backwards compatibility, support legacy request format
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      if ((request as any).domain_title) {
        // Legacy request format - convert to new format
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const legacyRequest = request as any;
        const newRequest: DomainDefinitionRequest = {
          pipeline_type: "suggest_domain_definition",
          flavor_id: legacyRequest.flavor || "default",
          context_data: {
            domain_title: this.sanitizeString(
              legacyRequest.domain_title,
              "domain_title",
            ),
            context: legacyRequest.context,
          },
        };
        return this.executePipeline(newRequest);
      }

      // New format - use directly
      this.validateRequired(request.pipeline_type, "pipeline_type");
      this.validateRequired(request.flavor_id, "flavor_id");
      this.validateRequired(request.context_data, "context_data");
      return this.executePipeline(request);
    }, "suggesting domain definition");
  }

  /**
   * Generate a layer definition suggestion based on provided context using LLM
   * @param request The layer definition suggestion request containing layer and context
   * @returns Layer definition suggestion with reasoning
   */
  async suggestLayerDefinition(
    request: LayerDefinitionRequest,
  ): Promise<LayerDefinitionResponse> {
    return this.withErrorContext(async () => {
      // For backwards compatibility, support legacy request format
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      if ((request as any).layer_title) {
        // Legacy request format - convert to new format
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const legacyRequest = request as any;
        const newRequest: LayerDefinitionRequest = {
          pipeline_type: "suggest_layer_definition",
          flavor_id: legacyRequest.flavor || "default",
          context_data: {
            layer_title: this.sanitizeString(
              legacyRequest.layer_title,
              "layer_title",
            ),
            context: legacyRequest.context,
          },
        };
        return this.executePipeline(newRequest);
      }

      // New format - use directly
      this.validateRequired(request.pipeline_type, "pipeline_type");
      this.validateRequired(request.flavor_id, "flavor_id");
      this.validateRequired(request.context_data, "context_data");
      return this.executePipeline(request);
    }, "suggesting layer definition");
  }

  /**
   * @deprecated Use suggestTermDefinition instead
   * Generate a definition suggestion based on provided context using LLM
   * @param request The definition suggestion request containing term and context
   * @returns Definition suggestion with reasoning
   */
  async suggestDefinition(
    request: DefinitionSuggestionRequest,
  ): Promise<DefinitionSuggestionResponse> {
    console.warn(
      "suggestDefinition is deprecated, use suggestTermDefinition instead",
    );
    return this.suggestTermDefinition(request);
  }

  /**
   * Check the health status of the LLM service
   * @returns Health status information
   */
  async healthCheck(): Promise<LLMHealthResponse> {
    return this.withErrorContext(
      () => this.getResource<LLMHealthResponse>(`${ENDPOINTS.LLM}/health`),
      "checking LLM health",
    );
  }

  /**
   * Generate term definition with minimal context (just term)
   * @param term The term to generate a definition for
   * @returns Term definition suggestion
   */
  async generateSimpleTermDefinition(
    term: string,
  ): Promise<DefinitionSuggestionResponse> {
    return this.suggestTermDefinition({ term } as any); // eslint-disable-line @typescript-eslint/no-explicit-any
  }

  /**
   * Generate term definition with domain context
   * @param term The term to define
   * @param domainTitle Title of the domain
   * @param domainDefinition Definition of the domain
   * @returns Term definition suggestion with domain context
   */
  async generateTermDefinitionWithDomain(
    term: string,
    domainTitle: string,
    domainDefinition?: string,
  ): Promise<DefinitionSuggestionResponse> {
    return this.suggestTermDefinition({
      term,
      domain_title: domainTitle,
      domain_definition: domainDefinition,
    } as any); // eslint-disable-line @typescript-eslint/no-explicit-any
  }

  /**
   * Generate term definition with hierarchical context
   * @param term The term to define
   * @param parentTermTitle Title of the parent term
   * @param parentTermDefinition Definition of the parent term
   * @param relationshipPredicate Relationship predicate to parent
   * @returns Term definition suggestion with hierarchical context
   */
  async generateTermDefinitionWithParent(
    term: string,
    parentTermTitle: string,
    parentTermDefinition?: string,
    relationshipPredicate?: string,
  ): Promise<DefinitionSuggestionResponse> {
    return this.suggestTermDefinition({
      term,
      parent_term_title: parentTermTitle,
      parent_term_definition: parentTermDefinition,
      parent_relationship_predicate: relationshipPredicate,
    } as any); // eslint-disable-line @typescript-eslint/no-explicit-any
  }

  /**
   * Generate term definition with component terms context
   * @param term The term to define
   * @param componentTerms Array of component terms with their context
   * @returns Term definition suggestion with component context
   */
  async generateTermDefinitionWithComponents(
    term: string,
    componentTerms: ComponentTerm[],
  ): Promise<DefinitionSuggestionResponse> {
    return this.suggestTermDefinition({
      term,
      component_terms: componentTerms,
    } as any); // eslint-disable-line @typescript-eslint/no-explicit-any
  }

  /**
   * Generate domain definition with minimal context (just domain title)
   * @param domainTitle The domain title to generate a definition for
   * @returns Domain definition suggestion
   */
  async generateSimpleDomainDefinition(
    domainTitle: string,
  ): Promise<DomainDefinitionResponse> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return this.suggestDomainDefinition({ domain_title: domainTitle } as any);
  }

  /**
   * Generate layer definition with minimal context (just layer title)
   * @param layerTitle The layer title to generate a definition for
   * @returns Layer definition suggestion
   */
  async generateSimpleLayerDefinition(
    layerTitle: string,
  ): Promise<LayerDefinitionResponse> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return this.suggestLayerDefinition({ layer_title: layerTitle } as any);
  }

  /**
   * @deprecated Use generateSimpleTermDefinition instead
   * Generate definition with minimal context (just term)
   */
  async generateSimpleDefinition(
    term: string,
  ): Promise<DefinitionSuggestionResponse> {
    console.warn(
      "generateSimpleDefinition is deprecated, use generateSimpleTermDefinition instead",
    );
    return this.generateSimpleTermDefinition(term);
  }

  /**
   * @deprecated Use generateTermDefinitionWithDomain instead
   * Generate definition with domain context
   */
  async generateDefinitionWithDomain(
    term: string,
    domainTitle: string,
    domainDefinition?: string,
  ): Promise<DefinitionSuggestionResponse> {
    console.warn(
      "generateDefinitionWithDomain is deprecated, use generateTermDefinitionWithDomain instead",
    );
    return this.generateTermDefinitionWithDomain(
      term,
      domainTitle,
      domainDefinition,
    );
  }

  /**
   * @deprecated Use generateTermDefinitionWithParent instead
   * Generate definition with hierarchical context
   */
  async generateDefinitionWithParent(
    term: string,
    parentTermTitle: string,
    parentTermDefinition?: string,
    relationshipPredicate?: string,
  ): Promise<DefinitionSuggestionResponse> {
    console.warn(
      "generateDefinitionWithParent is deprecated, use generateTermDefinitionWithParent instead",
    );
    return this.generateTermDefinitionWithParent(
      term,
      parentTermTitle,
      parentTermDefinition,
      relationshipPredicate,
    );
  }

  /**
   * @deprecated Use generateTermDefinitionWithComponents instead
   * Generate definition with component terms context
   */
  async generateDefinitionWithComponents(
    term: string,
    componentTerms: ComponentTerm[],
  ): Promise<DefinitionSuggestionResponse> {
    console.warn(
      "generateDefinitionWithComponents is deprecated, use generateTermDefinitionWithComponents instead",
    );
    return this.generateTermDefinitionWithComponents(term, componentTerms);
  }

  /**
   * Generate definition with external reference context
   * @param term The term to define
   * @param dbpediaContext DBpedia context information
   * @param wikidataContext Wikidata context information
   * @returns Definition suggestion with external reference context
   */
  async generateTermDefinitionWithReferences(
    term: string,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    dbpediaContext?: Record<string, any>,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    wikidataContext?: Record<string, any>,
  ): Promise<DefinitionSuggestionResponse> {
    return this.suggestTermDefinition({
      term,
      dbpedia_context: dbpediaContext,
      wikidata_context: wikidataContext,
    } as any); // eslint-disable-line @typescript-eslint/no-explicit-any
  }

  /**
   * Generate comprehensive term definition with all available context
   * @param request Complete term definition suggestion request
   * @returns Term definition suggestion with full context analysis
   */
  async generateComprehensiveTermDefinition(
    request: DefinitionSuggestionRequest,
  ): Promise<DefinitionSuggestionResponse> {
    return this.suggestTermDefinition(request);
  }

  /**
   * @deprecated Use generateTermDefinitionWithReferences instead
   * Generate definition with external reference context
   */
  async generateDefinitionWithReferences(
    term: string,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    dbpediaContext?: Record<string, any>,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    wikidataContext?: Record<string, any>,
  ): Promise<DefinitionSuggestionResponse> {
    console.warn(
      "generateDefinitionWithReferences is deprecated, use generateTermDefinitionWithReferences instead",
    );
    return this.generateTermDefinitionWithReferences(
      term,
      dbpediaContext,
      wikidataContext,
    );
  }

  /**
   * @deprecated Use generateComprehensiveTermDefinition instead
   * Generate comprehensive definition with all available context
   */
  async generateComprehensiveDefinition(
    request: DefinitionSuggestionRequest,
  ): Promise<DefinitionSuggestionResponse> {
    console.warn(
      "generateComprehensiveDefinition is deprecated, use generateComprehensiveTermDefinition instead",
    );
    return this.generateComprehensiveTermDefinition(request);
  }
}

// Export a singleton instance
export const llmService = new LLMService();
