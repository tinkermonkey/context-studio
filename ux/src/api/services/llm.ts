/**
 * LLM Service
 *
 * Service for Large Language Model operations including definition suggestions
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type { components } from "@/api/client/types";

// Type aliases for better readability - using the latest OpenAPI schema
export type DefinitionSuggestionRequest =
  components["schemas"]["DefinitionSuggestionRequest"];
export type DefinitionSuggestionResponse =
  components["schemas"]["DefinitionSuggestionResponse"];
export type DomainDefinitionRequest =
  components["schemas"]["DomainDefinitionRequest"];
export type DomainDefinitionResponse =
  components["schemas"]["DomainDefinitionResponse"];
export type LayerDefinitionRequest =
  components["schemas"]["LayerDefinitionRequest"];
export type LayerDefinitionResponse =
  components["schemas"]["LayerDefinitionResponse"];
export type ComponentTerm = components["schemas"]["ComponentTerm"];

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
  model_info: Record<string, any>;
  timestamp: string;
}

export class LLMService extends BaseService {
  /**
   * Generate a term definition suggestion based on provided context using LLM
   * @param request The term definition suggestion request containing term and context
   * @returns Term definition suggestion with reasoning
   */
  async suggestTermDefinition(
    request: DefinitionSuggestionRequest,
  ): Promise<DefinitionSuggestionResponse> {
    this.validateRequired(request.term, "term");
    const sanitizedTerm = this.sanitizeString(request.term, "term");

    return this.withErrorContext(async () => {
      const response = await this.postResource<LLMSuccessResponse>(
        `${ENDPOINTS.LLM}/suggest_term_definition`,
        {
          ...request,
          term: sanitizedTerm,
        },
      );
      return response.data;
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
    this.validateRequired(request.domain_title, "domain_title");
    const sanitizedTitle = this.sanitizeString(
      request.domain_title,
      "domain_title",
    );

    return this.withErrorContext(async () => {
      const response = await this.postResource<{
        success: boolean;
        data: DomainDefinitionResponse;
      }>(`${ENDPOINTS.LLM}/suggest_domain_definition`, {
        ...request,
        domain_title: sanitizedTitle,
      });
      return response.data;
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
    this.validateRequired(request.layer_title, "layer_title");
    const sanitizedTitle = this.sanitizeString(
      request.layer_title,
      "layer_title",
    );

    return this.withErrorContext(async () => {
      const response = await this.postResource<{
        success: boolean;
        data: LayerDefinitionResponse;
      }>(`${ENDPOINTS.LLM}/suggest_layer_definition`, {
        ...request,
        layer_title: sanitizedTitle,
      });
      return response.data;
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
    return this.suggestTermDefinition({ term });
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
    });
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
    });
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
    });
  }

  /**
   * Generate domain definition with minimal context (just domain title)
   * @param domainTitle The domain title to generate a definition for
   * @returns Domain definition suggestion
   */
  async generateSimpleDomainDefinition(
    domainTitle: string,
  ): Promise<DomainDefinitionResponse> {
    return this.suggestDomainDefinition({ domain_title: domainTitle });
  }

  /**
   * Generate layer definition with minimal context (just layer title)
   * @param layerTitle The layer title to generate a definition for
   * @returns Layer definition suggestion
   */
  async generateSimpleLayerDefinition(
    layerTitle: string,
  ): Promise<LayerDefinitionResponse> {
    return this.suggestLayerDefinition({ layer_title: layerTitle });
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
    dbpediaContext?: Record<string, any>,
    wikidataContext?: Record<string, any>,
  ): Promise<DefinitionSuggestionResponse> {
    return this.suggestTermDefinition({
      term,
      dbpedia_context: dbpediaContext,
      wikidata_context: wikidataContext,
    });
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
    dbpediaContext?: Record<string, any>,
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
