import React, {
  useCallback,
  useMemo,
  useEffect,
  useRef,
  useState,
} from "react";
import { type ChartData } from "./tree_data";
import { ChartStyles } from "./tree_chart_styles";
import TreeTrunk from "./tree_trunk";
import { TreeChartNode } from "./tree_chart_node";
import { useMeasurementSvg, useMeasurementHtml } from "./useMeasurementElement";
import { calculateLayout } from "./tree_chart_layout";
import { usePersistedExpandState } from "./usePersistedExpandState";
import { Alert } from "flowbite-react";
import { useNavigate } from "@tanstack/react-router";

interface TreeChartProps {
  chartData: ChartData;
  /**
   * Optional initial expand state - if provided, these node IDs will be expanded by default
   * This takes precedence over persisted expand state from session storage
   */
  initialExpandState?: string[];
  /**
   * Optional term ID to highlight in the tree
   */
  highlightedTermId?: string;
  /**
   * Optional view identifier for persisting expand state
   * If not provided, expand state will not be persisted to session storage
   */
  viewId?: string;
}
const TreeChart: React.FC<TreeChartProps> = ({
  chartData,
  initialExpandState,
  highlightedTermId,
  viewId,
}) => {
  // Container ref to measure width
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(0);
  const [containerHeight, setContainerHeight] = useState<number>(0);

  // Track hovered node for layout adjustments
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  // Track whether initial render is complete to enable transitions
  const [enableTransitions, setEnableTransitions] = useState(false);

  // Use persisted expand state and scroll management hook
  const {
    expandState,
    handleNodeToggle,
    restoreScrollPosition,
    setInitialExpandState,
  } = usePersistedExpandState(viewId);

  // Enable transitions after initial render to avoid animation on page load
  useEffect(() => {
    // Use requestAnimationFrame to ensure DOM is painted before enabling transitions
    const rafId = requestAnimationFrame(() => {
      setTimeout(() => {
        setEnableTransitions(true);
      }, 500);
    });
    return () => cancelAnimationFrame(rafId);
  }, []);

  // Set initial expand state when initialExpandState prop changes
  useEffect(() => {
    if (initialExpandState && initialExpandState.length > 0) {
      const initialState = new Map<string, boolean>();
      initialExpandState.forEach((nodeId) => {
        initialState.set(nodeId, true);
      });
      setInitialExpandState(initialState);
    }
  }, [initialExpandState, setInitialExpandState]);

  // Initialize and manage the measurement SVG lifecycle
  useMeasurementSvg();

  // Initialize and manage the measurement HTML lifecycle
  useMeasurementHtml();

  // Router navigation hook
  const navigate = useNavigate();

  // Measure container width on mount and resize
  useEffect(() => {
    const measureDimensions = () => {
      if (containerRef.current) {
        const width = containerRef.current.clientWidth;
        const height = containerRef.current.clientHeight;
        //console.log("Container dimensions measured:", { width, height });
        setContainerWidth(width);
        setContainerHeight(height);
      }
    };

    // Initial measurement
    measureDimensions();

    // Add resize listener
    const resizeObserver = new ResizeObserver(measureDimensions);
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

  // Calculate the layout with current expanded state and container dimensions
  const { root, dimensions } = useMemo(() => {
    // Only pass container width if it's been measured (> 0)
    const maxWidth = containerWidth > 0 ? containerWidth : undefined;
    return calculateLayout(
      chartData,
      expandState,
      undefined,
      undefined,
      maxWidth,
      hoveredNodeId,
    );
  }, [chartData, expandState, containerWidth, hoveredNodeId]);

  // Calculate the actual height needed for the chart content
  const chartHeight = useMemo(() => {
    // Use the calculated dimensions height from layout calculation
    // The layout algorithm now correctly accounts for expanded/collapsed states
    return dimensions.height;
  }, [dimensions.height]);

  // Restore scroll position when component mounts or layout changes
  useEffect(() => {
    // Small delay to ensure DOM is fully rendered
    const timeoutId = setTimeout(() => {
      restoreScrollPosition();
    }, 100);

    return () => clearTimeout(timeoutId);
  }, [restoreScrollPosition, dimensions]);

  // Node hover handlers
  const handleNodeHover = useCallback((nodeId: string | null) => {
    setHoveredNodeId(nodeId);
  }, []);

  // Node click handler to navigate to the node's details
  const handleNodeClick = useCallback((node: any) => {
    if (node.type === "term" || node.type === "domain" || node.type === "layer") {
      navigate({ to: `/app/structure_nodes/${node.id}` });
    } else {
      console.warn("Clicked on unknown node:", node);
    }
  }, [navigate]);

  return (
    <div
      ref={containerRef}
      style={{
        ...ChartStyles.chartContainer,
        position: "relative", // Enable relative positioning for the container
        minHeight: chartHeight, // Ensure container has minimum height for the chart
        transition: "min-height 0.2s ease-in-out", // Animate height changes
      }}
    >
      {/* SVG Layer with embedded definitions via foreignObject */}
      <svg
        width={dimensions.width}
        height={chartHeight}
        style={{
          display: "block", // Remove default inline spacing
          transition: "height 0.2s ease-in-out", // Animate height changes
        }}
      >
        {/* Render all children of the root node */}
        {root.children.map((child: any, index: number) => (
          <TreeChartNode
            key={child.id || index}
            node={child}
            parentNode={root}
            onToggle={handleNodeToggle}
            onNodeClick={handleNodeClick}
            onNodeHover={handleNodeHover}
            highlightedTermId={highlightedTermId}
            enableTransitions={enableTransitions}
          />
        ))}
        <TreeTrunk rootNode={root} />
      </svg>
    </div>
  );
};

export { TreeChart };
