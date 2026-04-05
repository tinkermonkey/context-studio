/**
 * Schema Service
 *
 * Service for managing database schema and migrations
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";

// Type aliases for better readability
export type MigrationStatus = Record<string, unknown>;

export interface MigrateParams extends Record<string, unknown> {
  skip_on_error?: boolean;
}

export interface GenerateMigrationParams extends Record<string, unknown> {
  description: string;
}

export class SchemaService extends BaseService {
  /**
   * Get current schema status and migration information
   */
  async getStatus(): Promise<MigrationStatus> {
    return this.withErrorContext(
      () => this.getResource<MigrationStatus>(`${ENDPOINTS.SCHEMA}/status`),
      "get schema status",
    );
  }

  /**
   * Apply pending migrations to the current dataset
   */
  async migrate(params?: MigrateParams): Promise<unknown> {
    return this.withErrorContext(
      () =>
        this.postResource<unknown>(`${ENDPOINTS.SCHEMA}/migrate`, undefined, {
          params,
        }),
      "migrate schema",
    );
  }

  /**
   * Get migration history for the current dataset
   */
  async getHistory(): Promise<unknown> {
    return this.withErrorContext(
      () => this.getResource<unknown>(`${ENDPOINTS.SCHEMA}/history`),
      "get migration history",
    );
  }

  /**
   * Rollback schema to a specific version
   */
  async rollback(targetVersion: number): Promise<unknown> {
    return this.withErrorContext(() => {
      this.validateRequired(targetVersion, "Target version");
      if (typeof targetVersion !== "number" || targetVersion < 0) {
        throw new Error("Target version must be a non-negative number");
      }
      return this.postResource<unknown>(
        `${ENDPOINTS.SCHEMA}/rollback/${targetVersion}`,
      );
    }, "rollback schema");
  }

  /**
   * Generate a new migration file template
   */
  async generateMigration(params: GenerateMigrationParams): Promise<unknown> {
    return this.withErrorContext(() => {
      this.validateRequired(params, "Migration parameters");
      this.validateRequired(params.description, "Migration description");
      this.sanitizeString((params.description as unknown as string) || '', "Migration description", 255);

      return this.postResource<unknown>(
        `${ENDPOINTS.SCHEMA}/generate-migration`,
        undefined,
        { params },
      );
    }, "generate migration");
  }
}

// Export singleton instance
export const schemaService = new SchemaService();
