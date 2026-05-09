// Expand state management for tree nodes
export type ExpandState = Map<string, boolean>;

const defaultExpandState = false;

/**
 * Toggle the expand state of a node
 * @param expandState Current expand state map
 * @param nodeId Node ID to toggle
 * @returns New expand state map
 */
export function toggleExpandState(
  expandState: ExpandState,
  nodeId: string,
): ExpandState {
  const newState = new Map(expandState);
  if (newState.has(nodeId)) {
    newState.set(nodeId, !newState.get(nodeId));
  } else {
    newState.set(nodeId, !defaultExpandState);
  }
  return newState;
}

/**
 * Set the expand state of a specific node
 * @param expandState Current expand state map
 * @param nodeId Node ID to set
 * @param nodeExpanded Whether the node should be expanded
 */
export function toggleNodeExpansion(
  expandState: ExpandState,
  nodeId: string,
  nodeExpanded: boolean,
) {
  expandState.set(nodeId, nodeExpanded);
}
