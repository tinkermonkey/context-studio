/**
 * Streaming Reference Service
 *
 * Service for real-time searching across multiple reference sources
 * Calls individual source endpoints in parallel and streams results as they arrive
 */

import { BaseService } from "./base";
import {
  UnifiedSearchRequest,
  SourceType,
  MultiSourceSearchResponse,
  UnifiedReferenceError,
} from "../types/unified";
import {
  StreamingSearchState,
  StreamingSearchOptions,
  StreamingSearchControl,
  StreamingUpdateCallback,
  createInitialStreamingState,
  updateStreamingState,
  getEnabledSources,
  SOURCE_ENDPOINTS,
  StreamingSearchError,
} from "../types/streamingReference";

export class StreamingReferenceService extends BaseService {
  /**
   * Search all enabled reference sources in parallel with real-time updates
   */
  async searchStreaming(
    request: UnifiedSearchRequest,
    options: StreamingSearchOptions = {},
  ): Promise<StreamingSearchControl> {
    return this.withErrorContext(async () => {
      this.validateSearchRequest(request);

      const {
        onSourceUpdate,
        onStateChange,
        timeout = 30000,
        retryAttempts = 1,
      } = options;

      const enabledSources = getEnabledSources();
      if (enabledSources.length === 0) {
        throw new StreamingSearchError(
          "No enabled reference sources available",
        );
      }

      let state = createInitialStreamingState(request);
      const abortController = new AbortController();
      let isActive = true;

      // Emit initial state
      onStateChange?.(state);

      // Start search for each enabled source
      const sourcePromises = enabledSources.map((source) =>
        this.searchSingleSource(
          source,
          request,
          abortController.signal,
          timeout,
          retryAttempts,
          (update) => {
            if (!isActive) return;

            state = updateStreamingState(state, update);
            onSourceUpdate?.(update);
            onStateChange?.(state);
          },
        ),
      );

      // Don't await all promises - let them resolve individually
      // But track completion for cleanup
      Promise.allSettled(sourcePromises).then(() => {
        if (isActive && !state.isComplete) {
          // Mark as complete if all sources have finished
          state = { ...state, isComplete: true, endTime: Date.now() };
          onStateChange?.(state);
        }
      });

      return {
        cancel: () => {
          isActive = false;
          abortController.abort();
        },
        getState: () => state,
        isActive,
      };
    }, "streaming search");
  }

  /**
   * Search a single reference source
   */
  private async searchSingleSource(
    source: SourceType,
    request: UnifiedSearchRequest,
    signal: AbortSignal,
    timeoutMs: number,
    retryAttempts: number,
    onUpdate: StreamingUpdateCallback,
  ): Promise<void> {
    const config = SOURCE_ENDPOINTS[source];
    if (!config.enabled) {
      return;
    }

    // Emit loading status
    onUpdate({
      source,
      status: "loading",
      results: [],
      links: [],
    });

    for (let attempt = 0; attempt <= retryAttempts; attempt++) {
      if (signal.aborted) {
        return;
      }

      try {
        const startTime = Date.now();

        // Create timeout for this specific request
        const timeoutController = new AbortController();
        const timeoutId = setTimeout(
          () => timeoutController.abort(),
          timeoutMs,
        );

        // Combine abort signals
        const combinedSignal = this.combineAbortSignals(
          signal,
          timeoutController.signal,
        );

        const response = await this.searchSourceEndpoint(
          source,
          request,
          combinedSignal,
        );

        clearTimeout(timeoutId);
        const executionTime = Date.now() - startTime;

        // Convert response to our format and emit success
        onUpdate({
          source,
          status: "completed",
          results: response.results || [],
          links: response.links || [],
          execution_time_ms: executionTime,
          total_results:
            response.total_results || response.results?.length || 0,
        });

        return; // Success - exit retry loop
      } catch (error) {
        if (signal.aborted) {
          return;
        }

        if (error instanceof Error && error.name === "AbortError") {
          // Timeout occurred
          onUpdate({
            source,
            status: "error",
            error: `Search timed out after ${timeoutMs}ms`,
            results: [],
            links: [],
          });
          return;
        }

        // If this was the last attempt, emit error
        if (attempt === retryAttempts) {
          onUpdate({
            source,
            status: "error",
            error: this.formatSourceError(error as Error, source),
            results: [],
            links: [],
          });
          return;
        }

        // Wait before retry (exponential backoff)
        await this.delay(Math.min(1000 * Math.pow(2, attempt), 5000));
      }
    }
  }

  /**
   * Search a specific source endpoint
   */
  private async searchSourceEndpoint(
    source: SourceType,
    request: UnifiedSearchRequest,
    signal: AbortSignal,
  ): Promise<MultiSourceSearchResponse> {
    const config = SOURCE_ENDPOINTS[source];

    // Build request parameters for individual source endpoint format
    const params = {
      query: request.query,
      limit: request.limit || 20,
      offset: request.offset || 0,
    };

    try {
      // All source endpoints now return normalized MultiSourceSearchResponse format
      const response = await this.request<MultiSourceSearchResponse>({
        method: "GET",
        url: config.endpoint,
        params,
        signal,
        timeout: config.timeout || 5000,
      });

      return response;
    } catch (error) {
      throw new StreamingSearchError(
        `Failed to search ${source}`,
        source,
        error as Error,
      );
    }
  }

  /**
   * Search all sources and return a Promise that resolves when all complete
   */
  async searchAllSources(
    request: UnifiedSearchRequest,
    options: StreamingSearchOptions = {},
  ): Promise<StreamingSearchState> {
    return new Promise((resolve, reject) => {
      this.searchStreaming(request, {
        ...options,
        onStateChange: (state) => {
          options.onStateChange?.(state);

          if (state.isComplete) {
            resolve(state);
          }
        },
      })
        .then((control) => {
          // Handle the case where search completes synchronously
          if (control.getState().isComplete) {
            resolve(control.getState());
          }
        })
        .catch(reject);
    });
  }

  /**
   * Get available sources with their status
   */
  async getSourceStatus(): Promise<Record<SourceType, boolean>> {
    const sources = getEnabledSources();

    const status: Record<SourceType, boolean> = {} as any;

    // For now, just return enabled status
    // Could be enhanced to actually ping each endpoint
    sources.forEach((source) => {
      status[source] = SOURCE_ENDPOINTS[source].enabled;
    });

    return status;
  }

  /**
   * Validate search request
   */
  private validateSearchRequest(request: UnifiedSearchRequest): void {
    this.validateRequired(request, "Search request");
    this.validateRequired(request.query, "Search query");
    this.sanitizeString(request.query, "Search query", 1000);

    if (request.query.trim().length < 2) {
      throw new UnifiedReferenceError(
        "Search query must be at least 2 characters",
      );
    }
  }

  /**
   * Format error message for a specific source
   */
  private formatSourceError(error: Error, source: SourceType): string {
    if (error.message.includes("404")) {
      return `${source} search endpoint not available`;
    }
    if (error.message.includes("timeout")) {
      return `${source} search timed out`;
    }
    if (error.message.includes("Network Error")) {
      return `Unable to connect to ${source}`;
    }
    return `${source} search failed: ${error.message}`;
  }

  /**
   * Combine multiple abort signals
   */
  private combineAbortSignals(...signals: AbortSignal[]): AbortSignal {
    const controller = new AbortController();

    signals.forEach((signal) => {
      if (signal.aborted) {
        controller.abort();
      } else {
        signal.addEventListener("abort", () => controller.abort(), {
          once: true,
        });
      }
    });

    return controller.signal;
  }

  /**
   * Delay utility for retries
   */
  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// Export singleton instance
export const streamingReferenceService = new StreamingReferenceService();
