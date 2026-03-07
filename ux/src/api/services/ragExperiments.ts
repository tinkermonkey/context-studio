/**
 * RAG Experiments Service
 *
 * Service for RAG pipeline experimentation, test paragraph management,
 * and pipeline performance comparison
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import { components, operations } from "../client/types";

// Type definitions from OpenAPI schema
export type CreateTestParagraphRequest =
  components["schemas"]["CreateTestParagraphRequest"];
export type UpdateTestParagraphRequest =
  components["schemas"]["UpdateTestParagraphRequest"];
export type CreateAnnotationRequest =
  components["schemas"]["CreateAnnotationRequest"];
export type RunPipelineTestRequest =
  components["schemas"]["RunPipelineTestRequest"];
export type TestParagraphResponse =
  components["schemas"]["TestParagraphResponse"];
export type TestParagraphListResponse =
  components["schemas"]["TestParagraphListResponse"];
export type AnnotationResponse = components["schemas"]["AnnotationResponse"];
export type RunPipelineTestResponse =
  components["schemas"]["RunPipelineTestResponse"];
export type PipelineRunResultResponse =
  components["schemas"]["PipelineRunResultResponse"];
export type PipelineComparisonResponse =
  components["schemas"]["PipelineComparisonResponse"];
export type PipelineRunDetailsResponse =
  components["schemas"]["PipelineRunDetailsResponse"];
export type ScoringDetailsResponse =
  components["schemas"]["ScoringDetailsResponse"];

// Infer response types from operations
type CreateParagraphResponse =
  operations["create_test_paragraph_api_rag_experiments_paragraphs_post"]["responses"]["201"]["content"]["application/json"];
type ListParagraphsResponse =
  operations["list_test_paragraphs_api_rag_experiments_paragraphs_get"]["responses"]["200"]["content"]["application/json"];
type GetParagraphResponse =
  operations["get_test_paragraph_api_rag_experiments_paragraphs__paragraph_id__get"]["responses"]["200"]["content"]["application/json"];
type UpdateParagraphResponse =
  operations["update_test_paragraph_api_rag_experiments_paragraphs__paragraph_id__put"]["responses"]["200"]["content"]["application/json"];
type CreateAnnotationResponse =
  operations["create_annotation_api_rag_experiments_paragraphs__paragraph_id__annotations_post"]["responses"]["201"]["content"]["application/json"];
type RunTestResponse =
  operations["run_pipeline_test_api_rag_experiments_run_post"]["responses"]["200"]["content"]["application/json"];
type GetComparisonResponse =
  operations["get_pipeline_comparison_api_rag_experiments_results_paragraphs__paragraph_id__get"]["responses"]["200"]["content"]["application/json"];
type GetRunDetailsResponse =
  operations["get_pipeline_run_details_api_rag_experiments_results_runs__run_id__get"]["responses"]["200"]["content"]["application/json"];

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
   * @param structureNodeId Structure node ID to link
   * @returns Created annotation with extracted text
   */
  async createAnnotation(
    paragraphId: string,
    startChar: number,
    endChar: number,
    structureNodeId: string,
  ): Promise<CreateAnnotationResponse> {
    this.validateRequired(paragraphId, "paragraphId");
    this.validateRequired(structureNodeId, "structureNodeId");

    return this.withErrorContext(async () => {
      const response = await this.postResource<CreateAnnotationResponse>(
        ENDPOINTS.RAG_EXPERIMENTS.ANNOTATIONS(paragraphId),
        {
          start_char: startChar,
          end_char: endChar,
          structure_node_id: structureNodeId,
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
