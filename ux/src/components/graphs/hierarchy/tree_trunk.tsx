import React from "react";
import { ChartStyles } from "./tree_styles";
import { HierarchyNode } from "./tree_data";

interface TreeTrunkProps {
  rootNode?: HierarchyNode;
}

const TreeTrunk: React.FC<TreeTrunkProps> = ({ rootNode }) => {
  // Use the root node's actual calculated position, or fall back to default margins
  const x = rootNode?.x ?? 10;
  const y = rootNode?.y ?? 30;

  return (
    <g>
      <circle cx={x} cy={y} r={10} style={ChartStyles.mainNode} />
    </g>
  );
};

export default TreeTrunk;
