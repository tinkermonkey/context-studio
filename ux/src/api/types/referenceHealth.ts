/**
 * Type definitions for Reference Database Health Check API
 *
 * Phase 4: API Contract Validation
 * Endpoint: /api/reference/ref-db/health
 */

/**
 * Health status of the reference database
 */
export type HealthStatus = "healthy" | "degraded" | "missing" | "error";

/**
 * Reasons why the database might be in a degraded state
 */
export type DegradedReason =
  | "embedding_count_mismatch"
  | "schema_or_model_version_mismatch"
  | "schema_version_table_missing"
  | "vector_query_failed";

/**
 * Reference Database Health Check Response
 *
 * Returned by: GET /api/reference/ref-db/health
 *
 * Status Definitions:
 * - "healthy": node_count == vec_count and versions match expected
 * - "degraded": vec_count mismatch or version mismatch detected
 * - "missing": database file doesn't exist or no nodes found
 * - "error": database operations failed
 */
export interface ReferenceHealthResponse {
  /** Overall health status */
  status: HealthStatus;

  /** Total number of reference nodes in database */
  node_count: number;

  /** Number of nodes with embeddings (title or definition) */
  vec_count: number;

  /** Database schema version (e.g., "1.0.0") */
  schema_version: string | null;

  /** Embedding model version (e.g., "text-embedding-3-small") */
  model_version: string | null;

  /** ISO 8601 timestamp of last import operation */
  last_import_at: string | null;

  /** Size of database file in bytes */
  database_size: number;

  /** Absolute path to database file */
  database_path: string;

  /** Whether database connection is functional */
  connection_healthy: boolean;

  /** ISO 8601 timestamp when health check was performed */
  checked_at: string;

  /** Reason for degraded status (only present when status is "degraded") */
  degraded_reason?: DegradedReason;

  /** Percentage of nodes with embeddings (only present when degraded due to mismatch) */
  embedding_coverage_pct?: number;

  /** Error message (only present when status is "error") */
  error?: string;

  /** Suggested remediation action (only present when status is not "healthy") */
  remediation?: string;
}

/**
 * Type guard to check if health status is healthy
 */
export function isHealthy(
  response: ReferenceHealthResponse,
): response is ReferenceHealthResponse & { status: "healthy" } {
  return response.status === "healthy";
}

/**
 * Type guard to check if health status is degraded
 */
export function isDegraded(
  response: ReferenceHealthResponse,
): response is ReferenceHealthResponse & {
  status: "degraded";
  degraded_reason: DegradedReason;
  remediation: string;
} {
  return response.status === "degraded";
}

/**
 * Type guard to check if health status is missing
 */
export function isMissing(
  response: ReferenceHealthResponse,
): response is ReferenceHealthResponse & {
  status: "missing";
  remediation: string;
} {
  return response.status === "missing";
}

/**
 * Type guard to check if health status is error
 */
export function isError(
  response: ReferenceHealthResponse,
): response is ReferenceHealthResponse & {
  status: "error";
  error: string;
  remediation: string;
} {
  return response.status === "error";
}
