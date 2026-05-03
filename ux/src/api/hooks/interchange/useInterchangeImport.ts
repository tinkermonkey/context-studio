/**
 * Interchange Import Mutation Hook
 *
 * Hook for importing ontology data from a file
 * Handles cache invalidation for entity caches on commit
 */

import { useMutation, useQueryClient, UseMutationOptions } from "@tanstack/react-query";
import {
  interchangeService,
  ImportPlanResponse,
  ImportRunCommitResponse,
  ResolutionRecord,
} from "../../services/interchange";
import { QUERY_KEYS } from "../../config";

/**
 * Utility function to invalidate all entity caches
 */
const invalidateEntityCaches = (queryClient: ReturnType<typeof useQueryClient>) => {
  const entityKeys = [
    QUERY_KEYS.TAXONOMIES,
    QUERY_KEYS.CONCEPT_SCHEMES,
    QUERY_KEYS.ONTOLOGY_CLASSES,
    QUERY_KEYS.INDIVIDUALS,
    QUERY_KEYS.RELATIONSHIPS,
    QUERY_KEYS.PROPERTY_DEFINITIONS,
  ];

  entityKeys.forEach((key) => {
    queryClient.invalidateQueries({ queryKey: [key] });
  });

  // Also invalidate interchange runs cache
  queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.INTERCHANGE_RUNS] });
};

/**
 * Hook to import ontology data
 * On commit (dry_run=false), invalidates all entity and interchange run caches
 */
export const useInterchangeImport = (
  options?: UseMutationOptions<
    ImportPlanResponse | ImportRunCommitResponse,
    Error,
    { format: string; file: File; dry_run: boolean; resolutions?: ResolutionRecord[] }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ format, file, dry_run, resolutions }) =>
      interchangeService.importFile(format, file, dry_run, resolutions),
    onSuccess: (_response, variables) => {
      // Only invalidate entity caches if this is a commit (dry_run=false)
      if (!variables.dry_run) {
        invalidateEntityCaches(queryClient);
      }
    },
    ...options,
  });
};
