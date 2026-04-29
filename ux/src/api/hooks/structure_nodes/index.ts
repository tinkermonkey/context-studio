/**
 * Structure Nodes Hooks (Legacy - For UI Backward Compatibility)
 *
 * DEPRECATED: This module exists only for backward compatibility with existing UI components.
 * These hooks should be refactored to use the new entity-specific hooks:
 * - useTaxonomies, useTaxonomy, useCreateTaxonomy, etc. for taxonomies
 * - useConceptSchemes, useConceptScheme, useCreateConceptScheme, etc. for schemes
 * - useOntologyClasses, useOntologyClass, useCreateOntologyClass, etc. for classes
 * - useRelationships, useRelationship, useCreateRelationship, etc. for relationships
 * - usePropertyDefinitions, usePropertyDefinition, useCreatePropertyDefinition, etc. for properties
 */

export {
  useStructureNodes,
  useStructureNodesPage,
  useStructureNode,
  useLayerNodes,
  useDomainNodes,
  useTermNodes,
  useStructureNodeFind,
} from "./useStructureNodes";

export {
  useCreateStructureNode,
  useUpdateStructureNode,
  useDeleteStructureNode,
  useMoveStructureNodes,
} from "./useStructureNodeMutations";

export {
  useNodeAttributes,
  useSetNodeAttributes,
  useRemoveNodeAttribute,
} from "./useNodeAttributes";

export {
  useReferenceLinks,
  useAddReferenceLinks,
  useRemoveReferenceLinks,
} from "./useReferenceLinks";

export {
  useWordSenses,
  useUpdateWordSenses,
} from "./useWordSenses";
