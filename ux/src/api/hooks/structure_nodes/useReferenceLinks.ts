/**
 * Reference Links Query and Mutation Hooks
 *
 * React Query hooks for managing reference links on structure nodes
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
import { structureNodeService } from "@/api/services/structureNodes";
import { QUERY_KEYS } from "@/api/config";
import { createQueryKey } from "@/api/utils/queryClient";
import { ReferenceLink } from "@/api/types/structureNodes";

/**
 * Hook to fetch reference links for a structure node
 */
export const useReferenceLinks = (
  nodeId: string,
  options?: UseQueryOptions<ReferenceLink[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.STRUCTURE_NODES,
      nodeId,
      { type: "reference_links" },
    ),
    queryFn: () => structureNodeService.getReferenceLinks(nodeId),
    enabled: !!nodeId,
    ...options,
  });
};

/**
 * Hook to add reference links to a structure node
 * Handles deduplication at the API layer
 */
export const useAddReferenceLinks = (
  nodeId: string,
  options?: UseMutationOptions<ReferenceLink[], Error, ReferenceLink[]>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (referenceLinks: ReferenceLink[]) =>
      structureNodeService.addReferenceLinks(nodeId, referenceLinks),
    onSuccess: (data) => {
      // Update the reference links cache with the server response
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId, { type: "reference_links" }),
        data,
      );

      // Invalidate the structure node detail query to refresh the full node data
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId),
      });

      // Invalidate the structure nodes list to ensure consistency
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.STRUCTURE_NODES],
      });
    },
    ...options,
  });
};

/**
 * Hook to remove reference links from a structure node
 */
export const useRemoveReferenceLinks = (
  nodeId: string,
  options?: UseMutationOptions<ReferenceLink[], Error, ReferenceLink[]>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (referenceLinks: ReferenceLink[]) =>
      structureNodeService.removeReferenceLinks(nodeId, referenceLinks),
    onMutate: async (
      variables: ReferenceLink[],
    ): Promise<{ previousReferenceLinks: ReferenceLink[] | undefined }> => {
      // Cancel any outgoing refetches
      const queryKey = createQueryKey(
        QUERY_KEYS.STRUCTURE_NODES,
        nodeId,
        { type: "reference_links" },
      );

      await queryClient.cancelQueries({ queryKey });

      // Snapshot the previous value for rollback
      const previousReferenceLinks = queryClient.getQueryData<ReferenceLink[]>(queryKey);

      // Optimistically remove the links
      if (previousReferenceLinks) {
        const updatedLinks = previousReferenceLinks.filter(
          (link) =>
            !variables.some(
              (toRemove) =>
                toRemove.source === link.source &&
                toRemove.external_id === link.external_id,
            ),
        );

        queryClient.setQueryData(queryKey, updatedLinks);
      }

      return { previousReferenceLinks };
    },
    onError: (err, variables, context) => {
      // Rollback to the previous value on error
      const ctx = context as { previousReferenceLinks?: ReferenceLink[] };
      if (ctx?.previousReferenceLinks) {
        queryClient.setQueryData(
          createQueryKey(
            QUERY_KEYS.STRUCTURE_NODES,
            nodeId,
            { type: "reference_links" },
          ),
          ctx.previousReferenceLinks,
        );
      }
    },
    onSuccess: (data) => {
      // Update the cache with the server response
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId, { type: "reference_links" }),
        data,
      );

      // Invalidate the structure node detail query to refresh the full node data
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId),
      });

      // Invalidate the structure nodes list to ensure consistency
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.STRUCTURE_NODES],
      });
    },
    ...options,
  });
};
