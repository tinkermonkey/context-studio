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
    case NodeType.LAYER:
      return `/app/taxonomies/${nodeId}`;
    case NodeType.CONCEPT_SCHEME:
    case NodeType.DOMAIN:
      return `/app/concept-schemes/${nodeId}`;
    case NodeType.CLASS:
    case NodeType.TERM:
    case NodeType.INDIVIDUAL:
      return `/app/classes/${nodeId}`;
    default:
      return `/app/classes/${nodeId}`;
  }
}
