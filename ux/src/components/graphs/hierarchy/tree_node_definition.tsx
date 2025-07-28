import React from "react";
import type { HierarchyNode } from "./tree_data";
import { ChartStyles, EdgeColors } from "./tree_styles";

interface TreeNodeDefinitionProps {
  node: HierarchyNode;
  parentNode?: HierarchyNode;
  onToggle?: (nodeId: string) => void;
  onNodeClick?: (node: HierarchyNode) => void;
  maxWidth: number; 
}

const TreeNodeDefinition: React.FC<TreeNodeDefinitionProps> = ({
  node,
  parentNode,
  onToggle,
  onNodeClick,
  maxWidth,
}) => {
  const nodeX = node.x ?? 0;
  const nodeY = node.y ?? 0;
  const textWidth = node.textWidth ?? 0;
  const nodeDefinitionHeight = node.definitionHeight ?? ChartStyles.nodeLabel.height;
  const nodeDefinitionWidth = node.definitionWidth ?? maxWidth - 10 - nodeX - textWidth

  return (
    <>
      <div
        style={{
          position: "absolute",
          left: nodeX + textWidth+ 10,
          top: nodeY - ChartStyles.nodeLabel.height,
          width: nodeDefinitionWidth,
          height: nodeDefinitionHeight,
          backgroundColor: "#fff", // Use a light red for visibility
          pointerEvents: "auto", // Allow this element to capture clicks
        }}
      >
        <div style={{ ...ChartStyles.nodeDefinition }}>
          {node.definition}
        </div>
      </div>
      {node.expanded &&
        node.children.map((child, index) => (
          <TreeNodeDefinition
            key={child.id || index}
            node={child}
            parentNode={node}
            onToggle={onToggle}
            onNodeClick={onNodeClick}
            maxWidth={maxWidth}
          />
        ))}
    </>
  );
};

export { TreeNodeDefinition };
