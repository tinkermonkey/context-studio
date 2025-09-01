/**
 * LLM Service
 * 
 * Service for Large Language Model operations including definition suggestions
 */

import { BaseService } from './base';
import { ENDPOINTS } from '../config';

// Type definitions based on OpenAPI schema

export interface SelectedRelation {
  predicate: string;
  object: string;
  weight: number;
  text?: string;
}

export interface ComponentTerm {
  text: string;
  selected_definitions?: string[];
  selected_relations?: SelectedRelation[];
}

export interface DefinitionSuggestionRequest {
  term: string;
  domain_title?: string;
  domain_definition?: string;
  parent_term_title?: string;
  parent_term_definition?: string;
  parent_relationship_predicate?: string;
  component_terms?: ComponentTerm[];
  current_definition?: string;
  dbpedia_context?: Record<string, any>;
  wikidata_context?: Record<string, any>;
}

export interface DefinitionSuggestionResponse {
  definition: string;
  reasoning: string;
  discrepancies?: string;
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
   * Generate a definition suggestion based on provided context using LLM
   * @param request The definition suggestion request containing term and context
   * @returns Definition suggestion with reasoning
   */
  async suggestDefinition(request: DefinitionSuggestionRequest): Promise<DefinitionSuggestionResponse> {
    this.validateRequired(request.term, 'term');
    const sanitizedTerm = this.sanitizeString(request.term, 'term');
    
    return this.withErrorContext(
      async () => {
        const response = await this.postResource<LLMSuccessResponse>(
          `${ENDPOINTS.LLM}/suggest_definition`,
          {
            ...request,
            term: sanitizedTerm,
          }
        );
        return response.data;
      },
      'suggesting definition'
    );
  }

  /**
   * Check the health status of the LLM service
   * @returns Health status information
   */
  async healthCheck(): Promise<LLMHealthResponse> {
    return this.withErrorContext(
      () => this.getResource<LLMHealthResponse>(`${ENDPOINTS.LLM}/health`),
      'checking LLM health'
    );
  }

  /**
   * Generate definition with minimal context (just term)
   * @param term The term to generate a definition for
   * @returns Definition suggestion
   */
  async generateSimpleDefinition(term: string): Promise<DefinitionSuggestionResponse> {
    return this.suggestDefinition({ term });
  }

  /**
   * Generate definition with domain context
   * @param term The term to define
   * @param domainTitle Title of the domain
   * @param domainDefinition Definition of the domain
   * @returns Definition suggestion with domain context
   */
  async generateDefinitionWithDomain(
    term: string,
    domainTitle: string,
    domainDefinition?: string
  ): Promise<DefinitionSuggestionResponse> {
    return this.suggestDefinition({
      term,
      domain_title: domainTitle,
      domain_definition: domainDefinition,
    });
  }

  /**
   * Generate definition with hierarchical context
   * @param term The term to define
   * @param parentTermTitle Title of the parent term
   * @param parentTermDefinition Definition of the parent term
   * @param relationshipPredicate Relationship predicate to parent
   * @returns Definition suggestion with hierarchical context
   */
  async generateDefinitionWithParent(
    term: string,
    parentTermTitle: string,
    parentTermDefinition?: string,
    relationshipPredicate?: string
  ): Promise<DefinitionSuggestionResponse> {
    return this.suggestDefinition({
      term,
      parent_term_title: parentTermTitle,
      parent_term_definition: parentTermDefinition,
      parent_relationship_predicate: relationshipPredicate,
    });
  }

  /**
   * Generate definition with component terms context
   * @param term The term to define
   * @param componentTerms Array of component terms with their context
   * @returns Definition suggestion with component context
   */
  async generateDefinitionWithComponents(
    term: string,
    componentTerms: ComponentTerm[]
  ): Promise<DefinitionSuggestionResponse> {
    return this.suggestDefinition({
      term,
      component_terms: componentTerms,
    });
  }

  /**
   * Generate definition with external reference context
   * @param term The term to define
   * @param dbpediaContext DBpedia context information
   * @param wikidataContext Wikidata context information
   * @returns Definition suggestion with external reference context
   */
  async generateDefinitionWithReferences(
    term: string,
    dbpediaContext?: Record<string, any>,
    wikidataContext?: Record<string, any>
  ): Promise<DefinitionSuggestionResponse> {
    return this.suggestDefinition({
      term,
      dbpedia_context: dbpediaContext,
      wikidata_context: wikidataContext,
    });
  }

  /**
   * Generate comprehensive definition with all available context
   * @param request Complete definition suggestion request
   * @returns Definition suggestion with full context analysis
   */
  async generateComprehensiveDefinition(
    request: DefinitionSuggestionRequest
  ): Promise<DefinitionSuggestionResponse> {
    return this.suggestDefinition(request);
  }
}

// Export a singleton instance
export const llmService = new LLMService();
