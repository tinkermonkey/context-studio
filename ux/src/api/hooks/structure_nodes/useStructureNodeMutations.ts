/**
 * Structure Node Mutation Hooks (DEPRECATED - For UI Backward Compatibility)
 *
 * These hooks are deprecated and exist only for backward compatibility.
 */

import { UseMutationOptions, useMutation } from "@tanstack/react-query";
import type {
  StructureNode,
  StructureNodeCreate,
  StructureNodeUpdate,
  MoveNodesRequest,
  MoveNodesResponse,
} from "../../types/structureNodes";

/**
 * DEPRECATED: Hook to create a new structure node
 */
export const useCreateStructureNode = (
  options?: UseMutationOptions<StructureNode, Error, StructureNodeCreate>,
) => {
  return useMutation({
    mutationFn: async () => {
      console.warn(
        "useCreateStructureNode is deprecated. Use entity-specific hooks instead.",
      );
      throw new Error(
        "useCreateStructureNode is deprecated. Use useCreateTaxonomy, useCreateConceptScheme, etc.",
      );
    },
    ...options,
  });
};

/**
 * DEPRECATED: Hook to update a structure node
 */
export const useUpdateStructureNode = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    { id: string; data: StructureNodeUpdate }
  >,
) => {
  return useMutation({
    mutationFn: async () => {
      console.warn(
        "useUpdateStructureNode is deprecated. Use entity-specific hooks instead.",
      );
      throw new Error(
        "useUpdateStructureNode is deprecated. Use useUpdateTaxonomy, useUpdateConceptScheme, etc.",
      );
    },
    ...options,
  });
};

/**
 * DEPRECATED: Hook to delete a structure node
 */
export const useDeleteStructureNode = (
  options?: UseMutationOptions<void, Error, string>,
) => {
  return useMutation({
    mutationFn: async () => {
      console.warn(
        "useDeleteStructureNode is deprecated. Use entity-specific hooks instead.",
      );
      throw new Error(
        "useDeleteStructureNode is deprecated. Use useDeleteTaxonomy, useDeleteConceptScheme, etc.",
      );
    },
    ...options,
  });
};

/**
 * DEPRECATED: Hook to move structure nodes
 */
export const useMoveStructureNodes = (
  options?: UseMutationOptions<MoveNodesResponse, Error, MoveNodesRequest>,
) => {
  return useMutation({
    mutationFn: async () => {
      console.warn("useMoveStructureNodes is deprecated.");
      throw new Error("useMoveStructureNodes is deprecated.");
    },
    ...options,
  });
};

/**
 * DEPRECATED: Hook to create a layer
 */
export const useCreateLayer = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    Omit<StructureNodeCreate, "node_type" | "parent_node_id">
  >,
) => {
  return useMutation({
    mutationFn: async () => {
      console.warn("useCreateLayer is deprecated. Use useCreateTaxonomy() instead.");
      throw new Error("useCreateLayer is deprecated.");
    },
    ...options,
  });
};

/**
 * DEPRECATED: Hook to create a domain
 */
export const useCreateDomain = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    { layerId: string; data: Omit<StructureNodeCreate, "node_type" | "parent_node_id"> }
  >,
) => {
  return useMutation({
    mutationFn: async () => {
      console.warn("useCreateDomain is deprecated. Use useCreateConceptScheme() instead.");
      throw new Error("useCreateDomain is deprecated.");
    },
    ...options,
  });
};

/**
 * DEPRECATED: Hook to create a term
 */
export const useCreateTerm = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    { parentId: string; data: Omit<StructureNodeCreate, "node_type" | "parent_node_id"> }
  >,
) => {
  return useMutation({
    mutationFn: async () => {
      console.warn("useCreateTerm is deprecated. Use useCreateOntologyClass() instead.");
      throw new Error("useCreateTerm is deprecated.");
    },
    ...options,
  });
};

/**
 * DEPRECATED: Hook to update a layer
 */
export const useUpdateLayer = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    { id: string; data: StructureNodeUpdate }
  >,
) => {
  return useMutation({
    mutationFn: async () => {
      console.warn("useUpdateLayer is deprecated. Use useUpdateTaxonomy() instead.");
      throw new Error("useUpdateLayer is deprecated.");
    },
    ...options,
  });
};

/**
 * DEPRECATED: Hook to update a domain
 */
export const useUpdateDomain = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    { id: string; data: StructureNodeUpdate }
  >,
) => {
  return useMutation({
    mutationFn: async () => {
      console.warn("useUpdateDomain is deprecated. Use useUpdateConceptScheme() instead.");
      throw new Error("useUpdateDomain is deprecated.");
    },
    ...options,
  });
};

/**
 * DEPRECATED: Hook to update a term
 */
export const useUpdateTerm = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    { id: string; data: StructureNodeUpdate }
  >,
) => {
  return useMutation({
    mutationFn: async () => {
      console.warn("useUpdateTerm is deprecated. Use useUpdateOntologyClass() instead.");
      throw new Error("useUpdateTerm is deprecated.");
    },
    ...options,
  });
};
