/**
 * Schema Service
 * 
 * Service for managing database schema and migrations
 */

import { BaseService } from './base';
import { ENDPOINTS } from '../config';
import type { components } from '../client/types';

// Type aliases for better readability
export type MigrationStatus = components['schemas']['MigrationStatus'];

export interface MigrationHistoryEntry {
  version: number;
  description: string;
  applied_at: string;
  filename: string;
}

export class SchemaService extends BaseService {
  /**
   * Get current schema status and migration information
   */
  async getStatus(): Promise<MigrationStatus> {
    return this.getResource<MigrationStatus>(`${ENDPOINTS.SCHEMA}/status`);
  }

  /**
   * Apply pending migrations to the current dataset
   */
  async migrate(skipOnError: boolean = false): Promise<{ success: boolean; message: string }> {
    return this.postResource<{ success: boolean; message: string }>(
      `${ENDPOINTS.SCHEMA}/migrate`,
      {},
      { params: { skip_on_error: skipOnError } }
    );
  }

  /**
   * Get migration history for the current dataset
   */
  async getHistory(): Promise<MigrationHistoryEntry[]> {
    return this.getResource<MigrationHistoryEntry[]>(`${ENDPOINTS.SCHEMA}/history`);
  }

  /**
   * Rollback schema to a specific version
   */
  async rollback(targetVersion: number): Promise<{ success: boolean; message: string }> {
    return this.postResource<{ success: boolean; message: string }>(
      `${ENDPOINTS.SCHEMA}/rollback/${targetVersion}`,
      {}
    );
  }

  /**
   * Generate a new migration file template
   */
  async generateMigration(description: string): Promise<{ filepath: string; content: string }> {
    return this.postResource<{ filepath: string; content: string }>(
      `${ENDPOINTS.SCHEMA}/generate-migration`,
      {},
      { params: { description } }
    );
  }
}

// Export singleton instance
export const schemaService = new SchemaService();
