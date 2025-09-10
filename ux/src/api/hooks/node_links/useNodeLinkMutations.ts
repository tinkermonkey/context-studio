/**
 * Node Links Mutation Hooks
 * 
 * React Query mutation hooks for structure node links (replaces term relationships)
 */

import { useMutation, useQueryClient, UseMutationOptions } from '@tanstack/react-query';
import { nodeLinkService } from '../../services/nodeLinks';
import { QUERY_KEYS } from '../../config';
import { createQueryKey } from '../../utils/queryClient';
import {
  StructureNodeLink,
  StructureNodeLinkCreate
} from '../../types/structureNodes';
import { nodeLinkQueryKeys } from './useNodeLinks';

/**
 * Hook to create a new structure node link
 */
export const useCreateNodeLink = (
  options?: UseMutationOptions<StructureNodeLink, Error, StructureNodeLinkCreate>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: StructureNodeLinkCreate) => nodeLinkService.create(data),
    onSuccess: (data, variables) => {
      // Invalidate all node links queries
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.NODE_LINKS],
      });
      
      // Add the new link to the cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.NODE_LINKS, data.id),
        data
      );

      // Invalidate specific node queries
      queryClient.invalidateQueries({
        queryKey: nodeLinkQueryKeys.byNode(variables.source_node_id),
      });
      queryClient.invalidateQueries({
        queryKey: nodeLinkQueryKeys.byNode(variables.target_node_id),
      });
      queryClient.invalidateQueries({
        queryKey: nodeLinkQueryKeys.fromNode(variables.source_node_id),
      });
      queryClient.invalidateQueries({
        queryKey: nodeLinkQueryKeys.toNode(variables.target_node_id),
      });

      // Invalidate predicate-specific queries
      queryClient.invalidateQueries({
        queryKey: nodeLinkQueryKeys.byPredicate(variables.predicate),
      });

      // Invalidate between-nodes queries
      queryClient.invalidateQueries({
        queryKey: nodeLinkQueryKeys.betweenNodes(variables.source_node_id, variables.target_node_id),
      });
    },
    ...options,
  });
};

/**
 * Hook to delete a structure node link
 */
export const useDeleteNodeLink = (
  options?: UseMutationOptions<void, Error, string>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => nodeLinkService.delete(id),
    onMutate: async (id: string) => {
      // Get the link being deleted for cache invalidation
      const linkToDelete = queryClient.getQueryData<StructureNodeLink>(
        createQueryKey(QUERY_KEYS.NODE_LINKS, id)
      );
      
      return { linkToDelete };
    },
    onSuccess: (_, id, context) => {
      // Remove the link from cache
      queryClient.removeQueries({
        queryKey: createQueryKey(QUERY_KEYS.NODE_LINKS, id),
      });
      
      // Invalidate all node links queries
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.NODE_LINKS],
      });

      // Invalidate specific node queries if we have the deleted link data
      const contextData = context as { linkToDelete?: StructureNodeLink };
      if (contextData?.linkToDelete) {
        const link = contextData.linkToDelete;
        
        queryClient.invalidateQueries({
          queryKey: nodeLinkQueryKeys.byNode(link.source_node_id),
        });
        queryClient.invalidateQueries({
          queryKey: nodeLinkQueryKeys.byNode(link.target_node_id),
        });
        queryClient.invalidateQueries({
          queryKey: nodeLinkQueryKeys.fromNode(link.source_node_id),
        });
        queryClient.invalidateQueries({
          queryKey: nodeLinkQueryKeys.toNode(link.target_node_id),
        });

        // Invalidate predicate-specific queries
        queryClient.invalidateQueries({
          queryKey: nodeLinkQueryKeys.byPredicate(link.predicate),
        });

        // Invalidate between-nodes queries
        queryClient.invalidateQueries({
          queryKey: nodeLinkQueryKeys.betweenNodes(link.source_node_id, link.target_node_id),
        });
      }
    },
    ...options,
  });
};

// Legacy compatibility mutation hooks for term relationships

/**
 * Hook to create a term relationship (backward compatibility wrapper)
 * @deprecated Use useCreateNodeLink instead
 */
export const useCreateTermRelationship = (
  options?: UseMutationOptions<StructureNodeLink, Error, {
    source_term_id: string;
    target_term_id: string;
    predicate: string;
    predicate_id?: string;
  }>
) => {
  const createNodeLink = useCreateNodeLink();
  
  return useMutation({
    mutationFn: ({ source_term_id, target_term_id, predicate, predicate_id }) => 
      createNodeLink.mutateAsync({
        source_node_id: source_term_id,
        target_node_id: target_term_id,
        predicate,
        predicate_id
      }),
    ...options,
  });
};

/**
 * Hook to delete a term relationship (backward compatibility wrapper)
 * @deprecated Use useDeleteNodeLink instead
 */
export const useDeleteTermRelationship = (
  options?: UseMutationOptions<void, Error, string>
) => {
  return useDeleteNodeLink(options);
};

// Convenience hooks for common patterns

/**
 * Hook to create a link between two terms with a specific predicate
 */
export const useCreateTermLink = (
  options?: UseMutationOptions<StructureNodeLink, Error, {
    sourceTermId: string;
    targetTermId: string;
    predicate: string;
    predicateId?: string;
  }>
) => {
  const createNodeLink = useCreateNodeLink();
  
  return useMutation({
    mutationFn: ({ sourceTermId, targetTermId, predicate, predicateId }) => 
      createNodeLink.mutateAsync({
        source_node_id: sourceTermId,
        target_node_id: targetTermId,
        predicate,
        predicate_id: predicateId
      }),
    ...options,
  });
};

/**
 * Hook to remove all links for a specific node
 */
export const useDeleteNodeLinks = (
  options?: UseMutationOptions<void, Error, string>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (nodeId: string) => {
      // First get all links for this node
      const links = await nodeLinkService.getNodeLinks(nodeId);
      
      // Delete all links in parallel
      await Promise.all(links.map(link => nodeLinkService.delete(link.id)));
    },
    onSuccess: (_, nodeId) => {
      // Invalidate all node links queries
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.NODE_LINKS],
      });

      // Invalidate specific node queries
      queryClient.invalidateQueries({
        queryKey: nodeLinkQueryKeys.byNode(nodeId),
      });
      queryClient.invalidateQueries({
        queryKey: nodeLinkQueryKeys.fromNode(nodeId),
      });
      queryClient.invalidateQueries({
        queryKey: nodeLinkQueryKeys.toNode(nodeId),
      });
    },
    ...options,
  });
};