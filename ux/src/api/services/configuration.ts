/**
 * Configuration Service
 *
 * Service for managing application configuration
 */

import { BaseService } from "./base";

export interface ConfigurationData {
  server: {
    host: string;
    port: number;
    reload: boolean;
    cors_origins: string[];
    access_log: boolean;
    log_level: string;
  };
  database: {
    default_url: string;
    default_dataset_filename: string;
    schema_org_path: string;
    reference_cache_path: string;
    operations_path: string;
    check_same_thread: boolean;
    pool_timeout: number;
  };
  llm: {
    model_name: string;
    temperature: number;
    max_tokens: number | null;
    timeout: number;
    max_text_length: number;
    retry_attempts: number;
  };
  nlp: {
    model_name: string;
    max_text_length: number;
    concepcy_relations: string[];
    filter_missing_text: boolean;
    edge_weight_filter: number;
    request_timeout: number;
    auto_download_models: boolean;
    download_timeout: number;
  };
  reference_sources: {
    default_language: string;
    search_timeout: number;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    [key: string]: any;
  };
  proxy_server: {
    host: string;
    port: number;
    enabled: boolean;
    database_path: string;
    max_cache_entries: number;
    default_cache_ttl: number;
    default_max_response_size: number;
    default_requests_per_hour: number;
    progressive_max_delay: number;
  };
  logging: {
    level: string;
    enable_console: boolean;
    enable_file: boolean;
    file_path: string;
    format: string;
    date_format: string;
    max_file_size: number;
    backup_count: number;
  };
  security: {
    require_secure_key: boolean;
    secure_key: string | null;
    log_security_events: boolean;
    api_key_header: string;
  };
}

export interface ConfigurationResponse {
  success: boolean;
  data: ConfigurationData;
  errors: string[];
}

export interface ConfigUpdateRequest {
  path: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  value: any;
}

export interface ReferenceSource {
  enabled: boolean;
  upstream_url: string;
  use_proxy: boolean;
  timeout: number;
  max_retries: number;
  rate_limit: {
    requests_per_hour: number;
    progressive_delay: boolean;
    max_delay: number;
  };
  custom_headers: Record<string, string>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  custom_params: Record<string, any>;
}

export interface ReferenceSourcesResponse {
  [sourceName: string]: ReferenceSource;
}

export interface ReferenceSourceStatus {
  name: string;
  enabled: boolean;
  upstream_url: string;
  use_proxy: boolean;
  timeout: number;
  status: "healthy" | "error" | "disabled";
  last_check?: string;
}

export interface ReferenceSourcesStatusResponse {
  sources: ReferenceSourceStatus[];
}

export class ConfigurationService extends BaseService {
  /**
   * Get full configuration
   */
  async getConfiguration(): Promise<ConfigurationResponse> {
    return this.withErrorContext(async () => {
      return this.getResource<ConfigurationResponse>("/api/config/");
    }, "getting configuration");
  }

  /**
   * Get specific configuration value by path
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async getConfigurationValue(path: string): Promise<any> {
    this.validateRequired(path, "path");

    return this.withErrorContext(async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return this.getResource<any>(`/api/config/${encodeURIComponent(path)}`);
    }, `getting configuration value for ${path}`);
  }

  /**
   * Update configuration value
   */
   
  async updateConfigurationValue(path: string, value: any)  // eslint-disable-line @typescript-eslint/no-explicit-any
: Promise<void> {
    this.validateRequired(path, "path");

    return this.withErrorContext(async () => {
      await this.request<void>({
        url: "/api/config/",
        method: "PATCH",
        data: { path, value },
      });
    }, `updating configuration value for ${path}`);
  }

  /**
   * Get configuration schema
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async getConfigurationSchema(): Promise<any> {
    return this.withErrorContext(async () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return this.getResource<any>("/api/config/schema/");
    }, "getting configuration schema");
  }

  /**
   * Validate configuration
   */
  async validateConfiguration(): Promise<{ valid: boolean; errors: string[] }> {
    return this.withErrorContext(async () => {
      return this.getResource<{ valid: boolean; errors: string[] }>(
        "/api/config/validate",
      );
    }, "validating configuration");
  }

  /**
   * Reload configuration from file
   */
  async reloadConfiguration(): Promise<void> {
    return this.withErrorContext(async () => {
      await this.request<void>({
        url: "/api/config/reload",
        method: "POST",
      });
    }, "reloading configuration");
  }

  /**
   * Reset configuration to defaults
   */
  async resetConfiguration(): Promise<void> {
    return this.withErrorContext(async () => {
      await this.request<void>({
        url: "/api/config/reset",
        method: "POST",
      });
    }, "resetting configuration");
  }

  /**
   * Get reference sources configuration
   */
  async getReferenceSourcesConfig(): Promise<ReferenceSourcesResponse> {
    return this.withErrorContext(async () => {
      return this.getResource<ReferenceSourcesResponse>(
        "/api/config/reference-sources",
      );
    }, "getting reference sources configuration");
  }

  /**
   * Get reference sources status
   */
  async getReferenceSourcesStatus(): Promise<ReferenceSourcesStatusResponse> {
    return this.withErrorContext(async () => {
      return this.getResource<ReferenceSourcesStatusResponse>(
        "/api/config/reference-sources/status",
      );
    }, "getting reference sources status");
  }

  /**
   * Get specific reference source configuration
   */
  async getReferenceSourceConfig(sourceName: string): Promise<ReferenceSource> {
    this.validateRequired(sourceName, "sourceName");

    return this.withErrorContext(async () => {
      return this.getResource<ReferenceSource>(
        `/api/config/reference-sources/${encodeURIComponent(sourceName)}`,
      );
    }, `getting reference source configuration for ${sourceName}`);
  }

  /**
   * Update reference source configuration
   */
  async updateReferenceSourceConfig(
    sourceName: string,
    path: string,
     
    value: any,  // eslint-disable-line @typescript-eslint/no-explicit-any

  ): Promise<void> {
    this.validateRequired(sourceName, "sourceName");
    this.validateRequired(path, "path");

    return this.withErrorContext(async () => {
      await this.request<void>({
        url: `/api/config/reference-sources/${encodeURIComponent(sourceName)}`,
        method: "PATCH",
        data: { path, value },
      });
    }, `updating reference source configuration for ${sourceName}`);
  }
}
