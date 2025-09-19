import { apiLogger } from "@/api/utils/logger";
import { HierarchyNode } from "@/components/graphs/hierarchy/tree_data";

export interface TreeBuilderInput {
  layers: any[];
  domains: any[];
  terms: any[];
}

/**
 * Transforms API data (layers, domains, terms) into a hierarchical tree structure
 * suitable for visualization components.
 *
 * @param input - Object containing layers, domains, and terms arrays from API
 * @returns HierarchyNode representing the complete hierarchy
 */
export function buildHierarchicalTree(input: TreeBuilderInput): HierarchyNode {
  const { layers, domains, terms } = input;

  if (!layers || !domains || !terms) {
    return {
      id: "dataset",
      title: "No Data Set",
      type: "dataset",
      depth: 0,
      children: [],
    };
  }

  try {
    // Debug: log layers and domains
    //console.log('LAYERS:', layers);
    //console.log('DOMAINS:', domains);

    const rootNode: HierarchyNode = {
      id: "dataset",
      title: "Data Set",
      type: "dataset",
      children: [],
      depth: 0,
    };

    // Group domains by parent_node_id (which is the layer_id for domains) for efficient lookup
    const domainsByLayer = new Map<string, any[]>();
    domains.forEach((domain: any) => {
      // For domains, parent_node_id contains the layer ID
      const layerId = domain.parent_node_id || domain.layer_id;
      if (layerId == null) {
        console.warn("Domain missing parent_node_id (layer_id):", domain);
        return;
      }
      const layerIdStr = String(layerId);
      if (!domainsByLayer.has(layerIdStr)) {
        domainsByLayer.set(layerIdStr, []);
      }
      domainsByLayer.get(layerIdStr)!.push(domain);
    });

    // Build layer nodes with their domains
    rootNode.children = layers
      .filter((layer: any) => layer.id != null)
      .map((layer: any) => {
        const layerIdStr = String(layer.id);
        const layerDomains = domainsByLayer.get(layerIdStr) || [];

        if (layerDomains.length === 0) {
          apiLogger.debug("Layer has no domains", {
            layer,
            availableKeys: Array.from(domainsByLayer.keys()),
          });
        }

        const layerNode: HierarchyNode = {
          id: `${layer.id}`,
          title: layer.title || layer.name || `Layer ${layer.id}`,
          definition: layer.definition || "",
          type: "layer",
          children: [],
          depth: rootNode.depth + 1,
        };

        // Build domain nodes with their terms
        layerNode.children = layerDomains
          .filter((domain: any) => domain.id != null)
          .map((domain: any) => {
            const domainTerms = terms.filter(
              (term: any) => {
                // For terms at domain level, parent_node_id should be the domain ID
                const termParentId = term.parent_node_id || term.domain_id;
                return String(termParentId) === String(domain.id);
              }
            );

            const domainNode: HierarchyNode = {
              id: `${domain.id}`,
              title: domain.title || domain.name || `Domain ${domain.id}`,
              definition: domain.definition || "",
              type: "domain",
              children: [],
              depth: layerNode.depth + 1,
            };

            // Build hierarchical term structure
            const { topLevelTerms } = buildTermHierarchy(domainTerms);
            domainNode.children = topLevelTerms;

            return domainNode;
          });

        return layerNode;
      });

    apiLogger.info("Final tree structure generated", { rootNode });
    return rootNode;
  } catch (err) {
    apiLogger.error("Error transforming data to tree:", { error: err });
    throw new Error("Failed to transform data to tree structure");
  }
}

/**
 * Builds a hierarchical structure from a flat array of terms
 * by organizing them based on parent_term_id relationships.
 *
 * @param terms - Array of term objects with potential parent_term_id relationships
 * @returns Object containing the top-level terms and a map of all terms
 */
function buildTermHierarchy(terms: any[]): {
  topLevelTerms: HierarchyNode[];
  termMap: Map<string, HierarchyNode>;
} {
  const termMap = new Map<string, HierarchyNode>();
  const topLevelTerms: HierarchyNode[] = [];

  // First pass: create all term nodes
  terms.forEach((term: any) => {
    if (!term.id) {
      console.warn("Term missing id:", term);
      return;
    }
    termMap.set(term.id, {
      id: `${term.id}`,
      title: term.title || term.name || `Term ${term.id}`,
      definition: term.definition || "",
      type: "term",
      children: [],
      depth: 0,
    });
  });

  // Second pass: establish parent-child relationships
  terms.forEach((term: any) => {
    const termNode = termMap.get(term.id);
    if (!termNode) return;

    // Check if this term has a parent term (parent_node_id points to another term in this set)
    const parentTermId = term.parent_term_id || (termMap.has(term.parent_node_id) ? term.parent_node_id : null);
    if (parentTermId && termMap.has(parentTermId)) {
      // This term has a parent - add it to parent's children
      const parentNode = termMap.get(parentTermId)!
      if (parentNode.children) {
        parentNode.children.push(termNode);
      }
    } else {
      // This is a top-level term
      topLevelTerms.push(termNode);
    }
  });

  return { topLevelTerms, termMap };
}

/**
 * Filters a hierarchical tree to show only the direct parents and children
 * of a specific term, maintaining the tree structure.
 *
 * @param tree - The complete hierarchical tree
 * @param termId - The ID of the term to focus on
 * @returns A filtered tree containing only relevant nodes
 */
export function filterTreeByTerm(
  tree: HierarchyNode,
  termId: string,
): HierarchyNode {
  if (!termId) {
    return tree;
  }

  try {
    // Find the target term and collect its ancestry
    const { targetNode, ancestry } = findNodeAndAncestry(tree, termId);

    if (!targetNode) {
      apiLogger.warn("Term not found in tree", { termId });
      return {
        id: "filtered-dataset",
        title: "Term Not Found",
        type: "dataset",
        depth: 0,
        children: [],
      };
    }

    // Build filtered tree maintaining structure
    const filteredRoot = buildFilteredTree(tree, targetNode, ancestry);

    apiLogger.info("Tree filtered successfully", {
      termId,
      originalDepth: getMaxDepth(tree),
      filteredDepth: getMaxDepth(filteredRoot),
    });

    return filteredRoot;
  } catch (err) {
    apiLogger.error("Error filtering tree by term", { error: err, termId });
    return tree; // Return original tree on error
  }
}

/**
 * Finds a node by ID and returns the node along with its ancestry path
 */
function findNodeAndAncestry(
  node: HierarchyNode,
  targetId: string,
  ancestry: HierarchyNode[] = [],
): { targetNode: HierarchyNode | null; ancestry: HierarchyNode[] } {
  const currentAncestry = [...ancestry, node];

  if (node.id === targetId) {
    return { targetNode: node, ancestry: currentAncestry };
  }

  // Search in children
  for (const child of node.children || []) {
    const result = findNodeAndAncestry(child, targetId, currentAncestry);
    if (result.targetNode) {
      return result;
    }
  }

  return { targetNode: null, ancestry: [] };
}

/**
 * Builds a filtered tree that includes:
 * - All ancestors of the target node
 * - The target node itself
 * - All direct children of the target node
 * - Siblings of the target node (for context)
 */
function buildFilteredTree(
  originalNode: HierarchyNode,
  targetNode: HierarchyNode,
  ancestry: HierarchyNode[],
): HierarchyNode {
  const isInAncestry = ancestry.some(
    (ancestor) => ancestor.id === originalNode.id,
  );
  const isTarget = originalNode.id === targetNode.id;
  const isDirectChild = targetNode.children?.some(
    (child) => child.id === originalNode.id,
  );
  const isTargetParent = targetNode.children?.some((child) =>
    findNodeInTree(originalNode, child.id),
  );

  // Create a copy of the current node
  const filteredNode: HierarchyNode = {
    ...originalNode,
    children: [],
  };

  if (isTarget) {
    // Include all direct children of target
    filteredNode.children = [...(targetNode.children || [])];
  } else if (isInAncestry || isTargetParent) {
    // For ancestry nodes, filter children to include only relevant paths
    filteredNode.children =
      originalNode.children
        ?.map((child) => {
          const childInAncestry = ancestry.some(
            (ancestor) => ancestor.id === child.id,
          );
          const childIsTarget = child.id === targetNode.id;
          const childHasTargetDescendant =
            findNodeInTree(child, targetNode.id) !== null;
          const childIsSiblingOfTarget = ancestry[
            ancestry.length - 2
          ]?.children?.some((sibling) => sibling.id === child.id);

          if (
            childInAncestry ||
            childIsTarget ||
            childHasTargetDescendant ||
            childIsSiblingOfTarget
          ) {
            return buildFilteredTree(child, targetNode, ancestry);
          }
          return null;
        })
        .filter((child): child is HierarchyNode => child !== null) || [];
  }

  return filteredNode;
}

/**
 * Helper function to find a node by ID within a tree
 */
function findNodeInTree(
  tree: HierarchyNode,
  nodeId: string,
): HierarchyNode | null {
  if (tree.id === nodeId) {
    return tree;
  }

  for (const child of tree.children || []) {
    const found = findNodeInTree(child, nodeId);
    if (found) {
      return found;
    }
  }

  return null;
}

/**
 * Helper function to calculate maximum depth of a tree
 */
function getMaxDepth(node: HierarchyNode): number {
  if (!node.children || node.children.length === 0) {
    return node.depth;
  }

  return Math.max(...node.children.map((child) => getMaxDepth(child)));
}

/**
 * Collects all node IDs from a tree structure recursively
 * This is useful for initializing expand states when all nodes should be expanded
 *
 * @param node - The root node to start collecting from
 * @returns Array of all node IDs in the tree
 */
export function collectAllNodeIds(node: HierarchyNode): string[] {
  const nodeIds: string[] = [node.id];

  if (node.children && node.children.length > 0) {
    for (const child of node.children) {
      nodeIds.push(...collectAllNodeIds(child));
    }
  }

  return nodeIds;
}
