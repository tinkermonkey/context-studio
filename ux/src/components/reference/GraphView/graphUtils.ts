/**
 * Graph Utilities for Predicate Grouping and Tree Structure
 *
 * This module provides functionality for analyzing and transforming graph data
 * to create meaningful hierarchical structures with predicate grouping.
 */

import { UnifiedNode, UnifiedSearchLink } from "@/api/types/unified";

export interface NodePosition {
  id: string;
  x: number;
  y: number;
}

export interface GraphDimensions {
  width: number;
  height: number;
}

export interface HierarchyNode {
  id: string;
  type: "data" | "predicate";
  source?: string;
  radius: number;
  x?: number;
  y?: number;
  predicate?: string;
  subjectId?: string;
  originalNode?: UnifiedNode;
  children?: HierarchyNode[];
  parent?: HierarchyNode;
  depth?: number;
}

export interface HierarchyLink {
  source: HierarchyNode;
  target: HierarchyNode;
  type: "subject-predicate" | "predicate-object";
  predicate?: string;
  weight: number;
}

export interface GroupedTreeStructure {
  nodes: HierarchyNode[];
  links: HierarchyLink[];
}

/**
 * Build a grouped tree structure where predicates become intermediate nodes
 * This creates a more meaningful hierarchy for search results
 */
export function buildGroupedTreeStructure(
  nodes: UnifiedNode[],
  links: UnifiedSearchLink[],
): GroupedTreeStructure {
  const nodeMap = new Map<string, HierarchyNode>();
  const hierarchyLinks: HierarchyLink[] = [];
  const predicateNodeMap = new Map<string, string>();

  // Create data nodes
  nodes.forEach((node) => {
    nodeMap.set(node.id, {
      id: node.id,
      type: "data",
      source: node.source,
      radius: 20,
      originalNode: node,
      children: [],
    });
  });

  // Group links by subject-predicate pairs
  const subjectPredicateGroups = new Map<string, UnifiedSearchLink[]>();
  links.forEach((link) => {
    const key = `${link.subject}|||${link.predicate}`; // Use ||| as separator to avoid conflicts
    if (!subjectPredicateGroups.has(key)) {
      subjectPredicateGroups.set(key, []);
    }
    subjectPredicateGroups.get(key)!.push(link);
  });

  // Group links by predicate-object pairs for potential future use
  const predicateObjectGroups = new Map<string, UnifiedSearchLink[]>();
  links.forEach((link) => {
    const key = `${link.predicate}|||${link.object}`;
    if (!predicateObjectGroups.has(key)) {
      predicateObjectGroups.set(key, []);
    }
    predicateObjectGroups.get(key)!.push(link);
  });

  // Create predicate nodes and hierarchy relationships for subject-predicate groups
  subjectPredicateGroups.forEach((groupLinks, key) => {
    const [subjectId, predicate] = key.split("|||");
    const subjectNode = nodeMap.get(subjectId);

    if (!subjectNode) return;

    // Create predicate node if it doesn't already exist
    const predicateObjectKey = `${predicate}|||${groupLinks[0].object}`;
    const existingPredicateNodeId =
      predicateNodeMap.get(key) || predicateNodeMap.get(predicateObjectKey);
    let predicateNode: HierarchyNode;

    if (existingPredicateNodeId) {
      predicateNode = nodeMap.get(existingPredicateNodeId)!;
    } else {
      const subjectPredicateNodeId = `pred-${key}`;
      predicateNode = {
        id: subjectPredicateNodeId,
        type: "predicate",
        radius: 8,
        predicate,
        subjectId,
        parent: subjectNode,
        children: [],
        depth: 1,
      };

      console.log(
        `Creating predicate node: ${subjectId} -[${predicate}]-> ${groupLinks[0].object}`,
      );

      nodeMap.set(subjectPredicateNodeId, predicateNode);
      predicateNodeMap.set(key, subjectPredicateNodeId);
      predicateNodeMap.set(predicateObjectKey, subjectPredicateNodeId);
      subjectNode.children!.push(predicateNode);

      // Create hierarchy link from subject to predicate
      hierarchyLinks.push({
        source: subjectNode,
        target: predicateNode,
        type: "subject-predicate",
        weight: 1,
      });

      // Link predicate to all objects
      groupLinks.forEach((link) => {
        const objectNode = nodeMap.get(link.object);
        if (objectNode) {
          // Register the predicate node so it can be reused for predicate-object grouping
          const predicateObjectKey = `${link.predicate}|||${link.object}`;
          predicateNodeMap.set(predicateObjectKey, predicateNode.id);
          hierarchyLinks.push({
            source: predicateNode,
            target: objectNode,
            type: "predicate-object",
            weight: link.weight || 1,
          });
        }
      });
    }
  });

  // Create predicate nodes and hierarchy relationships for predicate-object groups
  predicateObjectGroups.forEach((groupLinks, key) => {
    const [predicate, objectId] = key.split("|||");
    const objectNode = nodeMap.get(objectId);

    if (!objectNode) return;

    // Create predicate node if it doesn't already exist
    const existingPredicateNodeId = predicateNodeMap.get(key);
    let predicateNode: HierarchyNode;

    if (existingPredicateNodeId) {
      predicateNode = nodeMap.get(existingPredicateNodeId)!;
    } else {
      const predicateNodeId = `pred-${key}`;
      predicateNode = {
        id: predicateNodeId,
        type: "predicate",
        radius: 8,
        predicate,
        subjectId: groupLinks[0].subject,
        parent: nodeMap.get(groupLinks[0].subject),
        children: [],
        depth: 1,
      };

      nodeMap.set(predicateNodeId, predicateNode);
      predicateNodeMap.set(key, predicateNodeId);
      nodeMap.get(groupLinks[0].subject)?.children!.push(predicateNode);

      // Create hierarchy link from predicate node to object
      hierarchyLinks.push({
        source: predicateNode,
        target: objectNode,
        type: "predicate-object",
        weight: 1,
      });
    }

    // Link predicate to all objects
    groupLinks.forEach((link) => {
      const subjectNode = nodeMap.get(link.subject);
      if (predicateNode && subjectNode) {
        hierarchyLinks.push({
          source: subjectNode,
          target: predicateNode,
          type: "subject-predicate",
          weight: link.weight || 1,
        });
      }
    });
  });

  return { nodes: Array.from(nodeMap.values()), links: hierarchyLinks };
}

/**
 * Convert grouped structure to Reagraph format
 */
export function convertToReagraphFormat(
  groupedStructure: GroupedTreeStructure,
  sourceMetadata: Record<string, { color: string }>,
) {
  const colorMap: Record<string, string> = {
    blue: "#3B82F6",
    orange: "#F97316",
    purple: "#8B5CF6",
    red: "#EF4444",
    gray: "#6B7280",
  };

  const nodes = groupedStructure.nodes.map((node) => {
    if (node.type === "predicate") {
      return {
        id: node.id,
        label: node.predicate || "unknown",
        fill: "#A7D7F0", // Powder blue for predicates
        size: node.radius,
        data: node,
      };
    } else {
      // Data node
      const sourceColor =
        sourceMetadata[node.originalNode?.source || ""]?.color || "gray";
      return {
        id: node.id,
        label: node.originalNode?.title || node.id,
        fill: colorMap[sourceColor] || colorMap.gray,
        size: node.radius,
        data: node.originalNode,
      };
    }
  });

  const edges = groupedStructure.links.map((link, index) => ({
    id: `link-${index}`,
    source: link.source.id,
    target: link.target.id,
    label: link.type === "subject-predicate" ? "" : link.predicate,
    data: link,
  }));

  return { nodes, edges };
}

/**
 * Analyze graph structure for layout suitability
 */
 
export function analyzeGraphStructure(nodes: any[], edges: any[]) {
  if (edges.length === 0) {
    return {
      hasMultipleRoots: false,
      hasCycles: false,
      isTreeLike: true,
      hasNoRoot: false,
    };
  }

  // Build adjacency lists
  const inDegree = new Map<string, number>();
  const outDegree = new Map<string, number>();
  const adjacencyList = new Map<string, string[]>();

  // Initialize for all nodes
  nodes.forEach((node) => {
    inDegree.set(node.id, 0);
    outDegree.set(node.id, 0);
    adjacencyList.set(node.id, []);
  });

  // Count degrees
  edges.forEach((edge) => {
    inDegree.set(edge.target, (inDegree.get(edge.target) || 0) + 1);
    outDegree.set(edge.source, (outDegree.get(edge.source) || 0) + 1);
    adjacencyList.get(edge.source)?.push(edge.target);
  });

  // Find potential roots (nodes with in-degree 0)
  const roots = Array.from(inDegree.entries())
    .filter(([, degree]) => degree === 0)
    .map(([nodeId]) => nodeId);

  const hasMultipleRoots = roots.length > 1;
  const hasNoRoot = roots.length === 0;

  // Simple cycle detection using DFS
  const visited = new Set<string>();
  const recursionStack = new Set<string>();
  let hasCycles = false;

  const detectCycle = (nodeId: string): boolean => {
    if (recursionStack.has(nodeId)) return true;
    if (visited.has(nodeId)) return false;

    visited.add(nodeId);
    recursionStack.add(nodeId);

    const neighbors = adjacencyList.get(nodeId) || [];
    for (const neighbor of neighbors) {
      if (detectCycle(neighbor)) {
        return true;
      }
    }

    recursionStack.delete(nodeId);
    return false;
  };

  for (const nodeId of nodes.map((n) => n.id)) {
    if (!visited.has(nodeId)) {
      if (detectCycle(nodeId)) {
        hasCycles = true;
        break;
      }
    }
  }

  const isTreeLike = !hasMultipleRoots && !hasNoRoot && !hasCycles;

  return { hasMultipleRoots, hasCycles, isTreeLike, hasNoRoot };
}
