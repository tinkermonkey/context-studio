import { NodeType } from "@/api/types/ontology";

/**
 * Get the route path for a node based on its type
 *
 * Maps node types to their corresponding detail page routes
 */
export function getNodePath(nodeId: string, nodeType?: string): string {
  if (!nodeType) return `/app/classes/${nodeId}`;

  switch (nodeType) {
    case NodeType.TAXONOMY:
      return `/app/taxonomies/${nodeId}`;
    case NodeType.CONCEPT_SCHEME:
      return `/app/concept-schemes/${nodeId}`;
    case NodeType.CLASS:
    case NodeType.INDIVIDUAL:
      return `/app/classes/${nodeId}`;
    default:
      return `/app/classes/${nodeId}`;
  }
}
