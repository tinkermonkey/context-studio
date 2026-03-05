/**
 * NLP Service
 *
 * Service for natural language processing operations
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";

// Type definitions based on OpenAPI schema
export interface TokenData {
  text: string;
  lemma?: string;
  pos?: string;
  tag?: string;
  start?: number;
  end?: number;
  concepcy?: ConcepcyData;
  wordnet?: WordNetData;
}

export interface EntityData {
  text: string;
  label?: string;
  kb_id?: string;
  dbpedia?: DBpediaData;
}

export interface ConcepcyData {
  related_terms?: string[];
  score?: number;
}

export interface WordNetData {
  synsets?: object[];
  lemmas?: object[];
  definitions?: string[];
}

export interface DBpediaData {
  uri?: string;
  label?: string;
  similarity?: number;
  raw_result?: unknown;
}

export interface NLPAnalysisResponse {
  text: string;
  tokens?: TokenData[];
  entities?: EntityData[];
}

export interface NLPSuccessResponse {
  success: boolean;
  data: NLPAnalysisResponse;
}

export interface NLPErrorResponse {
  success: boolean;
  error: string;
}

export interface NLPAnalysisRequest {
  text: string;
}

// Proxy configuration and monitoring types
export interface ProxyConfiguration {
  [key: string]: boolean;
}

export interface ProxyConfigureResponse {
  success: boolean;
  message: string;
  configuration: ProxyConfiguration;
}

export interface ProxyStatusResponse {
  proxy_running: boolean;
  configuration: ProxyConfiguration;
  uptime?: number;
}

export interface ProxyMonitoringResponse {
  cache?: {
    total_entries: number;
    total_size_bytes: number;
    hit_rate: number;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    domains: Record<string, any>;
  };
  upstream?: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    overall: any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    domains: Record<string, any>;
  };
  database?: {
    db_file_path: string;
    db_file_size_bytes: number;
    db_health: string;
  };
  proxy?: {
    uptime_seconds: number;
    active_threads: number;
    recent_errors: string[];
  };
  throttling?: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    overall: any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    domains: Record<string, any>;
  };
}

export class NLPService extends BaseService {
  /**
   * Analyze text using NLP pipeline
   * @param text The text to analyze
   * @returns NLP analysis results including tokens and entities
   */
  async analyzeText(text: string): Promise<NLPAnalysisResponse> {
    const sanitizedText = this.sanitizeString(text, "text");

    return this.withErrorContext(async () => {
      const response = await this.postResource<NLPSuccessResponse>(
        ENDPOINTS.NLP,
        { text: sanitizedText },
      );
      return response.data;
    }, "analyzing text");
  }

  /**
   * Extract tokens from text
   * @param text The text to tokenize
   * @returns Array of token data
   */
  async extractTokens(text: string): Promise<TokenData[]> {
    const result = await this.analyzeText(text);
    return result.tokens || [];
  }

  /**
   * Extract entities from text
   * @param text The text to extract entities from
   * @returns Array of entity data
   */
  async extractEntities(text: string): Promise<EntityData[]> {
    const result = await this.analyzeText(text);
    return result.entities || [];
  }

  /**
   * Get comprehensive analysis with both tokens and entities
   * @param text The text to analyze
   * @returns Complete NLP analysis
   */
  async getComprehensiveAnalysis(text: string): Promise<NLPAnalysisResponse> {
    return this.analyzeText(text);
  }

  /**
   * Configure proxy settings
   * @param config Proxy configuration object
   * @returns Configuration response
   */
  async configureProxy(
    config: ProxyConfiguration,
  ): Promise<ProxyConfigureResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(config, "Proxy configuration");
      return this.postResource<ProxyConfigureResponse>(
        `${ENDPOINTS.NLP}/proxy/configure`,
        config,
      );
    }, "configure NLP proxy");
  }

  /**
   * Get proxy status
   * @returns Current proxy status
   */
  async getProxyStatus(): Promise<ProxyStatusResponse> {
    return this.getResource<ProxyStatusResponse>(
      `${ENDPOINTS.NLP}/proxy/status`,
    );
  }

  /**
   * Get proxy monitoring stats
   * @returns Monitoring statistics or null if proxy is not running
   */
  async getProxyMonitoring(): Promise<ProxyMonitoringResponse | null> {
    return this.getResource<ProxyMonitoringResponse | null>(
      `${ENDPOINTS.NLP}/proxy/monitor`,
    );
  }
}

// Export a singleton instance
export const nlpService = new NLPService();
