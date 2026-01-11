/**
 * Structure Node Selector Component
 *
 * Unified dropdown selector for choosing any structure node (layer, domain, or term)
 */

import React, { useMemo } from "react";

import { StructureNode, NodeType } from "@/api/types/structureNodes";
import { PortalRecordSelector, FieldMap } from "@/components/node_selectors/portal_record_selector";
import { useStructureNodes } from "@/api/hooks/structure_nodes/useStructureNodes";

export interface StructureNodeSelectorProps {
  onSelect?: (node: StructureNode | undefined) => void;
  value?: string;
  excludeNodeIds?: string[]; // Prevent selection of specific nodes (e.g., current node)
  nodeType?: NodeType; // Optional filter by node type
  placeholder?: string;
  disabled?: boolean;
  "data-testid"?: string;
}

export const StructureNodeSelector: React.FC<StructureNodeSelectorProps> = ({
  onSelect,
  value,
  excludeNodeIds = [],
  nodeType,
  placeholder = "Select node...",
  disabled = false,
  "data-testid": dataTestId,
}) => {
  // Fetch all nodes or filter by type
  const { data: nodes, isLoading, error } = useStructureNodes(
    nodeType ? { node_type: nodeType } : undefined
  );

  // Filter out excluded nodes
  const filteredNodes = useMemo(() => {
    if (!nodes) return [];
    if (excludeNodeIds.length === 0) return nodes;
    return nodes.filter((node) => !excludeNodeIds.includes(node.id));
  }, [nodes, excludeNodeIds]);

  // Field map for PortalRecordSelector
  const fieldMap: FieldMap<StructureNode> = {
    value: "id",
    title: "title",
    definition: "definition",
  };

  return (
    <PortalRecordSelector
      records={filteredNodes}
      loading={isLoading}
      error={error ? "Failed to load nodes" : null}
      fieldMap={fieldMap}
      onSelect={(r) => onSelect && onSelect(r as StructureNode | undefined)}
      value={value}
      placeholder={placeholder}
      disabled={disabled}
      data-testid={dataTestId}
    />
  );
};
