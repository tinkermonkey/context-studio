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
import { toast } from "@/utils/toast";

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

  return useMutation<ReferenceLink[], Error, ReferenceLink[]>({
    mutationFn: (referenceLinks: ReferenceLink[]) =>
      structureNodeService.addReferenceLinks(nodeId, referenceLinks),
    onSuccess: (data) => {
      // Update the reference links cache with the server response
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId, { type: "reference_links" }),
        data,
      );

      // Invalidate only the specific node's detail query to refresh the full node data
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId),
      });

      // Show success feedback
      toast.success(`Added ${data.length} reference link(s)`);
    },
    onError: (err, variables) => {
      console.error(`Failed to add reference links to node ${nodeId}:`, err);
      const message = err instanceof Error ? err.message : "Failed to add reference links";
      toast.error(`Failed to add reference links: ${message}. Please try again.`);
    },
    ...options,
  });
};

// Context type for optimistic updates
interface ReferenceLinkContext {
  previousReferenceLinks: ReferenceLink[] | undefined;
}

/**
 * Hook to remove reference links from a structure node
 */
export const useRemoveReferenceLink = (
  nodeId: string,
  options?: UseMutationOptions<ReferenceLink[], Error, ReferenceLink[], ReferenceLinkContext>,
) => {
  const queryClient = useQueryClient();

  return useMutation<ReferenceLink[], Error, ReferenceLink[], ReferenceLinkContext>({
    mutationFn: (referenceLinks: ReferenceLink[]) =>
      structureNodeService.removeReferenceLinks(nodeId, referenceLinks),
    onMutate: async (
      variables: ReferenceLink[],
    ): Promise<ReferenceLinkContext> => {
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
      if (context?.previousReferenceLinks) {
        queryClient.setQueryData(
          createQueryKey(
            QUERY_KEYS.STRUCTURE_NODES,
            nodeId,
            { type: "reference_links" },
          ),
          context.previousReferenceLinks,
        );
      }

      // Show error feedback
      console.error(`Failed to remove reference links from node ${nodeId}:`, err);
      const message = err instanceof Error ? err.message : "Failed to remove reference links";
      toast.error(`Failed to remove reference link: ${message}. Please try again.`);
    },
    onSuccess: (data) => {
      // Update the cache with the server response
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId, { type: "reference_links" }),
        data,
      );

      // Invalidate only the specific node's detail query to refresh the full node data
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId),
      });

      // Show success feedback
      toast.success("Reference link removed successfully");
    },
    ...options,
  });
};
