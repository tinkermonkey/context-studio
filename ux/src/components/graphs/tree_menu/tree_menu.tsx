import React, {
  useCallback,
  useMemo,
  useEffect,
  useRef,
  useState,
} from "react";
import { type ChartData } from "../tree_chart/tree_data";
import { chartStyles } from "./config";
import { TreeNode } from "./tree_menu_node";
import {
  useMeasurementSvg,
  useMeasurementHtml,
} from "../tree_chart/useMeasurementElement";
import { calculateLayout, clearTextHeightCache } from "./layout";
import { usePersistedExpandState } from "../tree_chart/usePersistedExpandState";
import { Alert } from "flowbite-react";
import { useNavigate } from "@tanstack/react-router";

interface TreeMenuProps {
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
   * Optional callback when a node is clicked
   */
  onNodeClick?: (node: any) => void;
  /**
   * Optional view identifier for persisting expand state
   * If not provided, expand state will not be persisted to session storage
   */
  viewId?: string;
  /**
   * Optional container width to constrain the tree menu
   * If not provided, the component will measure its own container
   */
  containerWidth?: number;
  /**
   * Whether to show node definitions
   * Default: false
   */
  showDefinitions?: boolean;
  /**
   * Width for titles when showing definitions
   * Can be a number (pixels) or percentage (0-1)
   * Default: 0.2 (20% of container width)
   */
  titleWidth?: number;
}
const TreeMenu: React.FC<TreeMenuProps> = ({
  chartData,
  initialExpandState,
  highlightedTermId,
  onNodeClick,
  viewId,
  containerWidth: propContainerWidth,
  showDefinitions = false,
  titleWidth = 0.2,
}) => {
  // Container ref to measure width
  const containerRef = useRef<HTMLDivElement>(null);
  const [measuredWidth, setMeasuredWidth] = useState<number>(0);
  const [containerHeight, setContainerHeight] = useState<number>(0);
  const [isReady, setIsReady] = useState<boolean>(false);

  // Use prop width if provided, otherwise use measured width
  const containerWidth = propContainerWidth || measuredWidth;

  // Use persisted expand state and scroll management hook
  const {
    expandState,
    handleNodeToggle,
    restoreScrollPosition,
    setInitialExpandState,
  } = usePersistedExpandState(viewId);

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

  // Measure container width on mount and resize (only if not provided via props)
  useEffect(() => {
    // Skip measurement if width is provided via props
    if (propContainerWidth) {
      return;
    }

    const measureDimensions = () => {
      if (containerRef.current) {
        const width = containerRef.current.clientWidth;
        const height = containerRef.current.clientHeight;
        //console.log("Container dimensions measured:", { width, height });
        setMeasuredWidth(width);
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
  }, [propContainerWidth]);

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
    // Don't calculate layout until container width is measured (unless provided via props)
    // This prevents zero-width calculations that can lead to cached zero heights
    if (!propContainerWidth && containerWidth === 0) {
      console.warn("[TreeMenu] Waiting for container width measurement before calculating layout");
      return {
        root: { ...chartData.root, children: [] },
        dimensions: { width: 0, height: 0 }
      };
    }

    // Only pass container width if it's been measured (> 0)
    const maxWidth = containerWidth > 0 ? containerWidth : undefined;
    const layout = calculateLayout(
      chartData,
      expandState,
      undefined,
      maxWidth,
      containerWidth, // Pass container width for full-width nodes
      showDefinitions,
      titleWidth,
    );

    // Validate layout to detect zero-height issues
    if (layout.dimensions.height === 0 && chartData.root.children?.length > 0) {
      console.error("[TreeMenu] Layout calculation resulted in zero height despite having children");
    }

    return layout;
  }, [chartData, expandState, containerWidth, showDefinitions, titleWidth, propContainerWidth]);

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

  // Reset ready state when chart data changes
  useEffect(() => {
    setIsReady(false);
  }, [chartData]);

  // Recovery mechanism: detect and fix zero-height layouts
  const [recoveryAttempted, setRecoveryAttempted] = useState(false);
  useEffect(() => {
    const hasChildren = root.children?.length > 0;
    const hasZeroHeight = dimensions.height === 0;
    const hasValidWidth = (propContainerWidth || containerWidth) > 0;

    if (hasChildren && hasZeroHeight && hasValidWidth && !recoveryAttempted) {
      console.warn("[TreeMenu] Detected zero-height layout - attempting recovery by clearing measurement cache");

      // Clear the measurement cache to force remeasurement
      clearTextHeightCache();

      // Mark recovery as attempted to prevent infinite loops
      setRecoveryAttempted(true);

      // Force a small delay to ensure DOM is ready, then trigger re-render
      setTimeout(() => {
        setIsReady(false);
        // The layout will recalculate due to the cleared cache
      }, 50);
    } else if (hasChildren && dimensions.height > 0) {
      // Reset recovery flag when we have valid dimensions
      setRecoveryAttempted(false);
    }
  }, [root, dimensions, containerWidth, propContainerWidth, recoveryAttempted]);

  // Mark component as ready after layout is calculated and container is measured
  useEffect(() => {
    // Only mark as ready if we have a valid layout with non-zero dimensions
    // or if there are genuinely no children to render
    const hasValidDimensions = dimensions.height > 0 || (root.children?.length === 0);
    const hasValidWidth = propContainerWidth || containerWidth > 0;

    if (root && hasValidDimensions && hasValidWidth) {
      setIsReady(true);
    } else if (root && !hasValidDimensions && root.children?.length > 0) {
      // We have children but zero height - this indicates a measurement problem
      console.warn("[TreeMenu] Detected zero-height layout with children present - delaying ready state");
      setIsReady(false);
    }
  }, [root, dimensions, containerWidth, propContainerWidth]);

  // Node click handler to navigate to the node's details
  // Uses provided onNodeClick if present, otherwise navigates to details page
  const handleNodeClick = useCallback((node: any) => {
    console.log("handleNodeClick:", node)
    if (onNodeClick) {
      onNodeClick(node);
    } else {
      // Default navigation behavior
      if (node.type === "term" || node.type === "domain" || node.type === "layer") {
        navigate({ to: `/app/structure_nodes/${node.id}` });
      } else {
        console.warn("Clicked on unknown node:", node);
      }
    }
  }, [onNodeClick, navigate]);

  return (
    <div
      ref={containerRef}
      style={{
        ...chartStyles.chartContainer,
        position: "relative", // Enable relative positioning for the container
        minHeight: chartHeight, // Ensure container has minimum height for the chart
        opacity: isReady ? 1 : 0, // Fade in when ready
      }}
    >
      {/* SVG Layer with embedded definitions via foreignObject */}
      <svg
        width={dimensions.width}
        height={chartHeight}
        style={{ display: "block" }} // Remove default inline spacing
      >
        {/* Render all children of the root node */}
        {root.children.map((child: any, index: number) => {
          child.childIndex = index;
          return (
            <TreeNode
              key={child.id || index}
              node={child}
              parentNode={root}
              onToggle={handleNodeToggle}
              onNodeClick={handleNodeClick}
              highlightedTermId={highlightedTermId}
            />
          );
        })}
        <g>
          <circle cx={root.x} cy={root.y} r={2} style={chartStyles.mainNode} />
        </g>
      </svg>
    </div>
  );
};

export { TreeMenu };
