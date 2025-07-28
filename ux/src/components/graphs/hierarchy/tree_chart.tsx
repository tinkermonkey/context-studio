import React, { useCallback, useMemo, useEffect, useRef, useState } from "react";
import { type ChartData } from "./tree_data";
import { ChartStyles } from "./tree_styles";
import TreeTrunk from "./tree_trunk";
import { TreeNode } from "./tree_node";
import { TreeNodeDefinition } from "@/components/graphs/hierarchy/tree_node_definition";
import { useMeasurementSvg, useMeasurementHtml } from "./useMeasurementElement";
import { calculateLayout } from "./tree_chart_layout";
import { usePersistedExpandState } from "./usePersistedExpandState";
import { Alert } from "flowbite-react";
import { useNavigate } from "@tanstack/react-router";

interface TreeChartProps {
  chartData: ChartData;
}
const TreeChart: React.FC<TreeChartProps> = ({ chartData }) => {
  // Container ref to measure width
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(0);

  // Use persisted expand state and scroll management hook
  const { 
    expandState, 
    handleNodeToggle, 
    restoreScrollPosition 
  } = usePersistedExpandState();

  // Initialize and manage the measurement SVG lifecycle
  useMeasurementSvg();

  // Initialize and manage the measurement HTML lifecycle
  useMeasurementHtml();

  // Router navigation hook
  const navigate = useNavigate();

  // Measure container width on mount and resize
  useEffect(() => {
    const measureWidth = () => {
      if (containerRef.current) {
        const width = containerRef.current.clientWidth;
        console.log("Container width measured:", width);
        setContainerWidth(width);
      }
    };

    // Initial measurement
    measureWidth();

    // Add resize listener
    const resizeObserver = new ResizeObserver(measureWidth);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  // Early return with alert if no chart data is provided
  if (!chartData) {
    return (
        <Alert color="warning">
          No chart data provided. Please provide valid chart data to render the
          tree.
        </Alert>
    );
  }

  // Calculate the layout with current expanded state and container width
  const { root, dimensions } = useMemo(() => {
    // Only pass containerWidth if it's been measured (> 0)
    const maxWidth = containerWidth > 0 ? containerWidth : undefined;
    return calculateLayout(chartData, expandState, undefined, undefined, maxWidth);
  }, [chartData, expandState, containerWidth]);

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
    <div ref={containerRef} style={{
      ...ChartStyles.chartContainer,
      position: 'relative' // Enable relative positioning for the container
    }}>
      {/* SVG Layer */}
      <svg 
        width={dimensions.width} 
        height={dimensions.height}
        style={{ display: 'block' }} // Remove default inline spacing
      >
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
      
      {/* HTML Overlay Layer - positioned exactly over the SVG */}
      <div 
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: dimensions.width,
          height: dimensions.height,
          pointerEvents: 'none', // Allow clicks to pass through to SVG by default
          zIndex: 10 // Ensure overlay is above SVG
        }}
      >
        {root.children.map((child: any, index: number) => (
          <TreeNodeDefinition
            key={child.id || index}
            node={child}
            parentNode={root}
            onToggle={handleNodeToggle}
            onNodeClick={handleNodeClick}
            maxWidth={dimensions.width}
          />
        ))}
      </div>
    </div>
  );
};

export { TreeChart };
