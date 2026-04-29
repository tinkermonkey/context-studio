/**
 * Structure Node Selector Component
 *
 * Unified dropdown selector for choosing any structure node (layer, domain, or term)
 */

import React, { useMemo } from "react";

import { OntologyClass, NodeType } from "@/api/types/ontology";
import {
  PortalRecordSelector,
  FieldMap,
} from "@/components/node_selectors/portal_record_selector";
import { useOntologyClasses } from "@/api/hooks/ontologyClasses/useOntologyClasses";

export interface OntologyClassSelectorProps {
  onSelect?: (node: OntologyClass | undefined) => void;
  value?: string;
  excludeNodeIds?: string[]; // Prevent selection of specific nodes (e.g., current node)
  nodeType?: NodeType; // Optional filter by node type
  placeholder?: string;
  disabled?: boolean;
  "data-testid"?: string;
}

export const OntologyClassSelector: React.FC<OntologyClassSelectorProps> = ({
  onSelect,
  value,
  excludeNodeIds = [],
  nodeType,
  placeholder = "Select node...",
  disabled = false,
  "data-testid": dataTestId,
}) => {
  // Fetch all nodes or filter by type
  const {
    data: nodes,
    isLoading,
    error,
  } = useOntologyClasses(nodeType ? { node_type: nodeType } : undefined);

  // Filter out excluded nodes
  const filteredNodes = useMemo(() => {
    if (!nodes) return [];
    if (excludeNodeIds.length === 0) return nodes;
    return nodes.filter((node) => !excludeNodeIds.includes(node.id));
  }, [nodes, excludeNodeIds]);

  // Field map for PortalRecordSelector
  const fieldMap: FieldMap<OntologyClass> = {
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
      onSelect={(r) => onSelect && onSelect(r as OntologyClass | undefined)}
      value={value}
      placeholder={placeholder}
      disabled={disabled}
      data-testid={dataTestId}
    />
  );
};
