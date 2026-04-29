/**
 * Node Links Hooks (Legacy - For UI Backward Compatibility)
 *
 * DEPRECATED: This module exists only for backward compatibility with existing UI components.
 * Use the new entity-specific hooks instead: useRelationships, useRelationship, etc.
 */

export {
  useNodeLinks,
  useNodeLinksPage,
  useNodeLink,
} from "./useNodeLinks";

export {
  useCreateNodeLink,
  useDeleteNodeLink,
} from "./useNodeLinkMutations";
