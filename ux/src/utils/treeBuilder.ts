import { apiLogger } from "@/api/utils/logger";
import { HierarchyNode } from "@/components/graphs/tree_chart/tree_data";

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
      x: 0,
      y: 0,
      width: 0,
      height: 0,
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
      x: 0,
      y: 0,
      width: 0,
      height: 0,
      depth: 0,
      children: [],
    };

    // Combine all nodes into a single array for generic processing
    const allNodes = [
      ...layers.map((n: any) => ({ ...n, node_type: n.node_type || "layer" })),

      ...domains.map((n: any) => ({
        ...n,
        node_type: n.node_type || "domain",
      })),

      ...terms.map((n: any) => ({ ...n, node_type: n.node_type || "term" })),
    ];

    // Build the hierarchy generically
    const nodeHierarchy = buildNodeHierarchy(allNodes);

    // Attach top-level nodes (layers) to root
    rootNode.children = nodeHierarchy.topLevelNodes;

    apiLogger.info("Final tree structure generated", { rootNode });
    return rootNode;
  } catch (err) {
    apiLogger.error("Error transforming data to tree:", { error: err });
    throw new Error("Failed to transform data to tree structure", {
      cause: err,
    });
  }
}

/**
 * Builds a hierarchical structure from a flat array of nodes
 * by organizing them based on parent_node_id relationships.
 * This is completely node-type agnostic and can be used for any hierarchical data.
 *
 * @param nodes - Array of all node objects (layers, domains, terms, etc.)
 * @returns Object containing the top-level nodes and a map of all nodes
 */

export function buildNodeHierarchy(nodes: any[]): {
  topLevelNodes: HierarchyNode[];
  nodeMap: Map<string, HierarchyNode>;
} {
  const nodeMap = new Map<string, HierarchyNode>();
  const topLevelNodes: HierarchyNode[] = [];

  // First pass: create all node entries

  nodes.forEach((node: any) => {
    if (!node.id) {
      console.warn("Node missing id:", node);
      return;
    }

    const hierarchyNode: HierarchyNode = {
      id: `${node.id}`,
      title: node.title || node.name || `Node ${node.id}`,
      definition: node.definition || "",
      type: node.node_type || "unknown",
      x: 0,
      y: 0,
      width: 0,
      height: 0,
      depth: 0,
      children: [],
    };

    nodeMap.set(node.id, hierarchyNode);
  });

  // Second pass: establish parent-child relationships

  nodes.forEach((node: any) => {
    const hierarchyNode = nodeMap.get(node.id);
    if (!hierarchyNode) return;

    const parentId = node.parent_node_id;

    if (parentId && nodeMap.has(parentId)) {
      // This node has a parent - add it to parent's children
      const parentNode = nodeMap.get(parentId)!;
      if (parentNode.children) {
        parentNode.children.push(hierarchyNode);
        // Set depth based on parent
        hierarchyNode.depth = parentNode.depth + 1;
      }
    } else {
      // This is a top-level node (no parent or parent not in set)
      topLevelNodes.push(hierarchyNode);
      hierarchyNode.depth = 0;
    }
  });

  return { topLevelNodes, nodeMap };
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
        x: 0,
        y: 0,
        width: 0,
        height: 0,
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

  const _isDirectChild = targetNode.children?.some(
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

/**
 * Collects node IDs from a tree structure, stopping at a specified node type
 * This is useful for initializing expand states when you want to expand only to a certain level
 *
 * @param node - The root node to start collecting from
 * @param stopAtType - The node type to stop at (nodes of this type will be included but not their children)
 * @returns Array of node IDs up to and including the stop type
 */
export function collectNodeIdsUpToType(
  node: HierarchyNode,
  stopAtType: string,
): string[] {
  const nodeIds: string[] = [node.id];

  // If we've reached the stop type, include this node but don't recurse into children
  if (node.type === stopAtType) {
    return nodeIds;
  }

  // Otherwise, recurse into children
  if (node.children && node.children.length > 0) {
    for (const child of node.children) {
      nodeIds.push(...collectNodeIdsUpToType(child, stopAtType));
    }
  }

  return nodeIds;
}
