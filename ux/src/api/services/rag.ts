/**
 * RAG Service
 *
 * Service for RAG (Retrieval-Augmented Generation) pipeline operations
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import {
  ExtractRequest,
  ExtractionResult,
  MetricsResponse,
  TraceResponse,
  LayerTraceResponse,
  DeleteTraceResponse,
  UpdateConfigResponse,
} from "./missingTypes";

export interface RAGConfigUpdate {
  timeout_layer_0?: number;
  timeout_layer_1?: number;
  timeout_layer_2?: number;
  timeout_layer_3?: number;
  dedup_similarity_threshold?: number;
  kg_top_k?: number;
}

export class RAGService extends BaseService {
  /**
   * Extract entities from text using the RAG pipeline
   * @param text The text to analyze and extract entities from
   * @param enableTrace Enable detailed tracing for observability (default: false)
   * @param enableLlmLayer Enable Layer 1 LLM extraction (optional, uses config default if not provided)
   * @returns RAG extraction response with entities, metrics, and request ID
   */
  async extractEntities(
    text: string,
    enableTrace: boolean = false,
    enableLlmLayer?: boolean,
  ): Promise<ExtractionResult> {
    const sanitizedText = this.sanitizeString(text, "text");

    return this.withErrorContext(async () => {
      const request: ExtractRequest = {
        text: sanitizedText,
        enable_trace: enableTrace,
        ...(enableLlmLayer !== undefined && { enable_llm_layer: enableLlmLayer }),
      };
      const response = await this.postResource<ExtractionResult>(
        ENDPOINTS.RAG.EXTRACT,
        request,
      );
      return response;
    }, "extracting entities");
  }

  /**
   * Retrieve processing metrics for a specific RAG extraction request
   * @param requestId Unique identifier for the extraction request
   * @returns Processing metrics for all pipeline layers
   */
  async getMetrics(requestId: string): Promise<MetricsResponse> {
    this.validateRequired(requestId, "requestId");

    return this.withErrorContext(async () => {
      const response = await this.getResource<MetricsResponse>(
        ENDPOINTS.RAG.METRICS(requestId),
      );
      return response;
    }, "retrieving metrics");
  }

  /**
   * Retrieve all trace entries for a specific RAG extraction request
   * @param requestId Unique identifier for the extraction request
   * @returns List of trace entries ordered by sentence index and timestamp
   */
  async getTrace(requestId: string): Promise<TraceResponse> {
    this.validateRequired(requestId, "requestId");

    return this.withErrorContext(async () => {
      const response = await this.getResource<TraceResponse>(
        ENDPOINTS.RAG.TRACE(requestId),
      );
      return response;
    }, "retrieving trace");
  }

  /**
   * Retrieve trace entries for a specific layer of a RAG extraction request
   * @param requestId Unique identifier for the extraction request
   * @param layerName Name of the layer (kg_context, llm_extraction, nlp_gap, web_resolution)
   * @returns List of trace entries for the specified layer
   */
  async getTraceByLayer(
    requestId: string,
    layerName: string,
  ): Promise<LayerTraceResponse> {
    this.validateRequired(requestId, "requestId");
    this.validateRequired(layerName, "layerName");

    return this.withErrorContext(async () => {
      const response = await this.getResource<LayerTraceResponse>(
        ENDPOINTS.RAG.TRACE_BY_LAYER(requestId, layerName),
      );
      return response;
    }, `retrieving trace for layer ${layerName}`);
  }

  /**
   * Delete trace data for a specific RAG extraction request
   * @param requestId Unique identifier for the extraction request
   * @returns Deletion confirmation with count of traces deleted
   */
  async deleteTrace(requestId: string): Promise<DeleteTraceResponse> {
    this.validateRequired(requestId, "requestId");

    return this.withErrorContext(async () => {
      const response = await this.deleteResource<DeleteTraceResponse>(
        ENDPOINTS.RAG.TRACE(requestId),
      );
      return response;
    }, "deleting trace data");
  }

  /**
   * Update RAG pipeline configuration settings
   * @param config Configuration updates (timeouts, thresholds, etc.)
   * @returns Updated configuration response
   */
  async updateConfig(config: RAGConfigUpdate): Promise<UpdateConfigResponse> {
    this.validateRequired(config, "config");

    return this.withErrorContext(async () => {
      const response = await this.postResource<UpdateConfigResponse>(
        ENDPOINTS.RAG.CONFIG_UPDATE,
        config,
      );
      return response;
    }, "updating configuration");
  }
}

// Export a singleton instance
export const ragService = new RAGService();
