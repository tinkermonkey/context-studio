/**
 * RAG Experiments Service
 *
 * Service for RAG pipeline experimentation, test paragraph management,
 * and pipeline performance comparison
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type {
  CreateTestParagraphRequest,
  UpdateTestParagraphRequest,
  TestParagraphResponse,
  TestParagraphListResponse,
  PipelineComparisonResponse,
  PipelineComparisonItem,
  PipelineComparisonSummary,
} from "./missingTypes";

// Re-export types for use in hooks and components
export type {
  CreateTestParagraphRequest,
  UpdateTestParagraphRequest,
  TestParagraphResponse,
  TestParagraphListResponse,
  PipelineComparisonResponse,
  PipelineComparisonItem,
  PipelineComparisonSummary,
};

// Type definitions for RAG experiments
export type CreateAnnotationRequest = Record<string, unknown>;
export type RunPipelineTestRequest = Record<string, unknown>;
export type AnnotationResponse = Record<string, unknown>;

export interface PipelineRunResult {
  paragraph_id?: string;
  pipeline_name?: string;
  status?: string;
  result?: Record<string, unknown>;
  [key: string]: unknown;
}

export type RunPipelineTestResponse = Record<string, unknown> & {
  results?: PipelineRunResult[];
};

export type PipelineRunResultResponse = Record<string, unknown>;

export type PipelineRunDetailsResponse = Record<string, unknown>;
export type ScoringDetailsResponse = Record<string, unknown>;

// Response types for RAG experiment operations
type CreateParagraphResponse = TestParagraphResponse;
type ListParagraphsResponse = Record<string, unknown> & {
  paragraphs?: TestParagraphResponse[];
  total?: number;
};
type GetParagraphResponse = TestParagraphResponse;
type UpdateParagraphResponse = TestParagraphResponse;
type CreateAnnotationResponse = Record<string, unknown>;
type RunTestResponse = Record<string, unknown>;
type GetComparisonResponse = PipelineComparisonResponse;
type GetRunDetailsResponse = Record<string, unknown>;

export interface ListParagraphsParams {
  limit?: number;
  offset?: number;
}

export interface GetComparisonParams {
  paragraphId: string;
  pipelineNames?: string[];
}

export class RAGExperimentsService extends BaseService {
  /**
   * Create a new test paragraph
   * @param text The paragraph text content
   * @param notes Optional notes about the paragraph
   * @returns Created test paragraph with empty annotations array
   */
  async createTestParagraph(
    text: string,
    notes?: string,
  ): Promise<CreateParagraphResponse> {
    const sanitizedText = this.sanitizeString(text, "text");
    const sanitizedNotes = notes
      ? this.sanitizeString(notes, "notes")
      : undefined;

    return this.withErrorContext(async () => {
      const response = await this.postResource<CreateParagraphResponse>(
        ENDPOINTS.RAG_EXPERIMENTS.PARAGRAPHS,
        {
          text: sanitizedText,
          notes: sanitizedNotes,
        } as CreateTestParagraphRequest,
      );
      return response;
    }, "creating test paragraph");
  }

  /**
   * List test paragraphs with pagination
   * @param params Pagination parameters
   * @returns Paginated list of test paragraphs with annotations
   */
  async listTestParagraphs(
    params: ListParagraphsParams = {},
  ): Promise<ListParagraphsResponse> {
    const { limit = 100, offset = 0 } = params;

    return this.withErrorContext(async () => {
      const response = await this.getResource<ListParagraphsResponse>(
        ENDPOINTS.RAG_EXPERIMENTS.PARAGRAPHS,
        { limit, offset },
      );
      return response;
    }, "listing test paragraphs");
  }

  /**
   * Get a specific test paragraph by ID
   * @param paragraphId Test paragraph ID
   * @returns Test paragraph with all annotations
   */
  async getTestParagraph(paragraphId: string): Promise<GetParagraphResponse> {
    this.validateRequired(paragraphId, "paragraphId");

    return this.withErrorContext(async () => {
      const response = await this.getResource<GetParagraphResponse>(
        ENDPOINTS.RAG_EXPERIMENTS.PARAGRAPH(paragraphId),
      );
      return response;
    }, "getting test paragraph");
  }

  /**
   * Update a test paragraph
   * @param paragraphId Test paragraph ID
   * @param text New text content (optional)
   * @param notes New notes (optional)
   * @returns Updated test paragraph
   */
  async updateTestParagraph(
    paragraphId: string,
    text?: string,
    notes?: string,
  ): Promise<UpdateParagraphResponse> {
    this.validateRequired(paragraphId, "paragraphId");

    const sanitizedText = text ? this.sanitizeString(text, "text") : undefined;
    const sanitizedNotes = notes
      ? this.sanitizeString(notes, "notes")
      : undefined;

    return this.withErrorContext(async () => {
      const response = await this.putResource<UpdateParagraphResponse>(
        ENDPOINTS.RAG_EXPERIMENTS.PARAGRAPH(paragraphId),
        {
          text: sanitizedText,
          notes: sanitizedNotes,
        } as UpdateTestParagraphRequest,
      );
      return response;
    }, "updating test paragraph");
  }

  /**
   * Delete a test paragraph
   * @param paragraphId Test paragraph ID
   */
  async deleteTestParagraph(paragraphId: string): Promise<void> {
    this.validateRequired(paragraphId, "paragraphId");

    return this.withErrorContext(async () => {
      await this.deleteResource<void>(
        ENDPOINTS.RAG_EXPERIMENTS.PARAGRAPH(paragraphId),
      );
    }, "deleting test paragraph");
  }

  /**
   * Create an annotation for a test paragraph
   * @param paragraphId Test paragraph ID
   * @param startChar Start character position
   * @param endChar End character position
   * @param ontologyClassId Structure node ID to link
   * @returns Created annotation with extracted text
   */
  async createAnnotation(
    paragraphId: string,
    startChar: number,
    endChar: number,
    ontologyClassId: string,
  ): Promise<CreateAnnotationResponse> {
    this.validateRequired(paragraphId, "paragraphId");
    this.validateRequired(ontologyClassId, "ontologyClassId");

    return this.withErrorContext(async () => {
      const response = await this.postResource<CreateAnnotationResponse>(
        ENDPOINTS.RAG_EXPERIMENTS.ANNOTATIONS(paragraphId),
        {
          start_char: startChar,
          end_char: endChar,
          ontology_class_id: ontologyClassId,
        } as CreateAnnotationRequest,
      );
      return response;
    }, "creating annotation");
  }

  /**
   * Delete an annotation
   * @param annotationId Annotation ID
   */
  async deleteAnnotation(annotationId: string): Promise<void> {
    this.validateRequired(annotationId, "annotationId");

    return this.withErrorContext(async () => {
      await this.deleteResource<void>(
        ENDPOINTS.RAG_EXPERIMENTS.DELETE_ANNOTATION(annotationId),
      );
    }, "deleting annotation");
  }

  /**
   * Run pipeline tests against test paragraphs
   * @param paragraphIds List of test paragraph IDs
   * @param pipelineNames List of pipeline names to test
   * @param enableTrace Enable detailed tracing (default: false)
   * @param enableLlmLayer Enable LLM layer (optional)
   * @returns Test results with scoring metrics
   */
  async runPipelineTest(
    paragraphIds: string[],
    pipelineNames: string[],
    enableTrace: boolean = false,
    enableLlmLayer?: boolean,
  ): Promise<RunTestResponse> {
    this.validateRequired(paragraphIds, "paragraphIds");
    this.validateRequired(pipelineNames, "pipelineNames");

    return this.withErrorContext(async () => {
      const response = await this.postResource<RunTestResponse>(
        ENDPOINTS.RAG_EXPERIMENTS.RUN,
        {
          paragraph_ids: paragraphIds,
          pipeline_names: pipelineNames,
          enable_trace: enableTrace,
          enable_llm_layer: enableLlmLayer,
        } as RunPipelineTestRequest,
      );
      return response;
    }, "running pipeline test");
  }

  /**
   * Get pipeline comparison results for a test paragraph
   * @param params Comparison parameters with paragraph ID and optional pipeline filter
   * @returns Comparison of pipeline results sorted by F1 score
   */
  async getPipelineComparison(
    params: GetComparisonParams,
  ): Promise<GetComparisonResponse> {
    const { paragraphId, pipelineNames } = params;
    this.validateRequired(paragraphId, "paragraphId");

    return this.withErrorContext(async () => {
      const queryParams = pipelineNames
        ? { pipeline_names: pipelineNames }
        : undefined;

      const response = await this.getResource<GetComparisonResponse>(
        ENDPOINTS.RAG_EXPERIMENTS.COMPARISON(paragraphId),
        queryParams,
      );
      return response;
    }, "getting pipeline comparison");
  }

  /**
   * Get detailed results for a specific pipeline run
   * @param runId Pipeline run ID
   * @returns Detailed run results with full extraction data
   */
  async getPipelineRunDetails(runId: string): Promise<GetRunDetailsResponse> {
    this.validateRequired(runId, "runId");

    return this.withErrorContext(async () => {
      const response = await this.getResource<GetRunDetailsResponse>(
        ENDPOINTS.RAG_EXPERIMENTS.RUN_DETAILS(runId),
      );
      return response;
    }, "getting pipeline run details");
  }
}

// Export a singleton instance
export const ragExperimentsService = new RAGExperimentsService();
