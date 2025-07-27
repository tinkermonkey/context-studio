import React, { useCallback, useMemo, useEffect } from "react";
import { type ChartData } from "./tree_data";
import { ChartStyles } from "./tree_styles";
import TreeTrunk from "./tree_trunk";
import { TreeNode } from "./tree_node";
import { useMeasurementSvg } from "./useMeasurementSvg";
import { calculateLayout } from "./tree_chart_layout";
import { usePersistedExpandState } from "./usePersistedExpandState";
import { Alert } from "flowbite-react";
import { useNavigate } from "@tanstack/react-router";

interface TreeChartProps {
  chartData: ChartData;
}
const TreeChart: React.FC<TreeChartProps> = ({ chartData }) => {
  // Use persisted expand state and scroll management hook
  const { 
    expandState, 
    handleNodeToggle, 
    restoreScrollPosition 
  } = usePersistedExpandState();

  // Initialize and manage the measurement SVG lifecycle
  useMeasurementSvg();

  // Router navigation hook
  const navigate = useNavigate();

  // Early return with alert if no chart data is provided
  if (!chartData) {
    return (
        <Alert color="warning">
          No chart data provided. Please provide valid chart data to render the
          tree.
        </Alert>
    );
  }

  // Calculate the layout with current expanded state
  const { root, dimensions } = useMemo(() => {
    return calculateLayout(chartData, expandState);
  }, [chartData, expandState]);

  // Restore scroll position when component mounts or layout changes
  useEffect(() => {
    // Small delay to ensure DOM is fully rendered
    const timeoutId = setTimeout(() => {
      restoreScrollPosition();
    }, 100);
    
    return () => clearTimeout(timeoutId);
  }, [restoreScrollPosition, dimensions]);

  // Node click handler to navigate to the node's details
  const handleNodeClick = useCallback((node: any) => {
    if (node.type === "term") {
      navigate({ to: `/app/nodes/term/${node.id}` });
    } else if (node.type === "domain") {
      navigate({ to: `/app/nodes/domain/${node.id}` });
    } else if (node.type === "layer") {
      navigate({ to: `/app/nodes/layer/${node.id}` });
    } else {
      console.warn("Clicked on unknown node:", node);
    }
  }, []);

  return (
    <div style={ChartStyles.chartContainer}>
      <svg width={dimensions.width} height={dimensions.height}>
        {/* Render all children of the root node */}
        {root.children.map((child: any, index: number) => (
          <TreeNode
            key={child.id || index}
            node={child}
            parentNode={root}
            onToggle={handleNodeToggle}
            onNodeClick={handleNodeClick}
          />
        ))}
        <TreeTrunk />
      </svg>
    </div>
  );
};

export { TreeChart };
