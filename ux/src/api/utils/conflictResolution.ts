/**
 * Conflict Resolution Utilities
 *
 * Utilities for detecting and resolving version conflicts when updating resources.
 * Implements optimistic locking and stale data detection.
 */

import { toast } from "@/utils/toast";
import { API_CONFIG } from "../config";
import { isConflictError } from "../errors/errorHandlers";
import { apiLogger } from "./logger";

export interface VersionedResource {
  id: string;
  version: number;
   
  [key: string]: any;
}

export interface ConflictResolutionOptions {
  /**
   * Whether to automatically refetch the latest data on conflict
   * @default true
   */
  autoRefetch?: boolean;

  /**
   * Whether to show a toast notification on conflict
   * @default true
   */
  showToast?: boolean;

  /**
   * Custom message to display on conflict
   */
  customMessage?: string;

  /**
   * Callback to execute when conflict is detected
   */
  onConflict?: (error: Error) => void;

  /**
   * Callback to execute after refetch completes
   */
  onRefetchComplete?: (data: any) => void;  
}

/**
 * Checks if an error is a version conflict error
 */
export const isVersionConflict = (error: unknown): boolean => {
  if (isConflictError(error)) {
    return true;
  }

  // Check for version conflict indicators in error message
  if (error instanceof Error) {
    const message = error.message.toLowerCase();
    return (
      message.includes("conflict") ||
      message.includes("stale") ||
      message.includes("version") ||
      message.includes("modified")
    );
  }

  return false;
};

/**
 * Handles version conflicts by optionally refetching data and notifying the user
 */
export const handleVersionConflict = async (
  error: unknown,
   
  refetch: () => Promise<any>,
  options: ConflictResolutionOptions = {},
): Promise<void> => {
  const {
    autoRefetch = API_CONFIG.refetchOnConflict,
    showToast = true,
    customMessage,
    onConflict,
    onRefetchComplete,
  } = options;

  // Log the conflict
  apiLogger.warn("Version conflict detected", { error });

  // Execute conflict callback if provided
  if (onConflict) {
    onConflict(error as Error);
  }

  // Show user notification
  if (showToast) {
    const message =
      customMessage ||
      "The data has been modified by another user. Refreshing to get latest version.";

    toast.warning(message);
  }

  // Automatically refetch if enabled
  if (autoRefetch) {
    try {
      // Add a small delay before refetching to avoid race conditions
      await new Promise((resolve) =>
        setTimeout(resolve, API_CONFIG.conflictRetryDelay),
      );

      const freshData = await refetch();

      if (onRefetchComplete) {
        onRefetchComplete(freshData);
      }

      if (showToast) {
        toast.success("Data refreshed successfully");
      }
    } catch (refetchError) {
      apiLogger.error("Failed to refetch after conflict", { refetchError });

      if (showToast) {
        toast.error("Failed to refresh data. Please try again manually.");
      }
    }
  }
};

/**
 * Validates that the local version matches the server version before mutation
 */
export const validateVersion = (
  localResource: VersionedResource,
  serverResource: VersionedResource,
): boolean => {
  if (localResource.id !== serverResource.id) {
    throw new Error("Resource ID mismatch");
  }

  return localResource.version === serverResource.version;
};

/**
 * Higher-order function that wraps a mutation with conflict detection
 */
export const withConflictDetection = <T extends VersionedResource, R>(
  mutationFn: (resource: T) => Promise<R>,
  refetchFn: () => Promise<T>,
  options: ConflictResolutionOptions = {},
) => {
  return async (resource: T): Promise<R> => {
    try {
      return await mutationFn(resource);
    } catch (error) {
      if (isVersionConflict(error)) {
        await handleVersionConflict(error, refetchFn, options);

        // Re-throw the error so the caller can handle it appropriately
        throw error;
      }

      // Re-throw non-conflict errors
      throw error;
    }
  };
};

/**
 * Compares two versioned resources and returns the differences
 */
export const detectChanges = <T extends VersionedResource>(
  local: T,
  remote: T,
): {
  hasChanges: boolean;
  versionMismatch: boolean;
  changedFields: string[];
} => {
  const versionMismatch = local.version !== remote.version;
  const changedFields: string[] = [];

  // Compare all fields except version and id
  const fields = new Set([...Object.keys(local), ...Object.keys(remote)]);

  for (const field of fields) {
    if (field === "id" || field === "version") {
      continue;
    }

    const localValue = JSON.stringify(local[field]);
    const remoteValue = JSON.stringify(remote[field]);

    if (localValue !== remoteValue) {
      changedFields.push(field);
    }
  }

  return {
    hasChanges: changedFields.length > 0,
    versionMismatch,
    changedFields,
  };
};

/**
 * Creates a user-friendly message describing the conflicts
 */
export const formatConflictMessage = (changedFields: string[]): string => {
  if (changedFields.length === 0) {
    return "No conflicts detected";
  }

  if (changedFields.length === 1) {
    return `The "${changedFields[0]}" field was modified`;
  }

  const fieldList = changedFields.slice(0, 3).join(", ");
  const remaining = changedFields.length - 3;

  if (remaining > 0) {
    return `${fieldList} and ${remaining} other field${remaining > 1 ? "s were" : " was"} modified`;
  }

  return `${fieldList} were modified`;
};
