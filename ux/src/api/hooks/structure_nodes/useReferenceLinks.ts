/**
 * Reference Links Hooks (DEPRECATED - For UI Backward Compatibility)
 */

import {
  useQuery,
  useMutation,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
import type { ReferenceLink } from "../../types/structureNodes";

/**
 * DEPRECATED: Get reference links for a node
 */
export const useReferenceLinks = (
  nodeId: string,
  options?: UseQueryOptions<ReferenceLink[], Error>,
) => {
  return useQuery({
    queryKey: ["reference_links", nodeId],
    queryFn: async () => {
      console.warn("useReferenceLinks is deprecated.");
      return [];
    },
    enabled: !!nodeId,
    ...options,
  });
};

/**
 * DEPRECATED: Add reference links
 */
export const useAddReferenceLinks = (
  options?: UseMutationOptions<
    ReferenceLink[],
    Error,
    { nodeId: string; referenceLinks: ReferenceLink[] }
  >,
) => {
  return useMutation({
    mutationFn: async () => {
      throw new Error("useAddReferenceLinks is deprecated.");
    },
    ...options,
  });
};

/**
 * DEPRECATED: Remove reference links
 */
export const useRemoveReferenceLinks = (
  options?: UseMutationOptions<
    ReferenceLink[],
    Error,
    { nodeId: string; referenceLinks: ReferenceLink[] }
  >,
) => {
  return useMutation({
    mutationFn: async () => {
      throw new Error("useRemoveReferenceLinks is deprecated.");
    },
    ...options,
  });
};

/**
 * DEPRECATED: Remove a single reference link
 */
export const useRemoveReferenceLink = (
  options?: UseMutationOptions<
    ReferenceLink[],
    Error,
    { nodeId: string; referenceLink: ReferenceLink }
  >,
) => {
  return useMutation({
    mutationFn: async () => {
      throw new Error("useRemoveReferenceLink is deprecated.");
    },
    ...options,
  });
};
