import React, {
  useCallback,
  useMemo,
  useEffect,
  useRef,
  useState,
} from "react";
import { type ChartData, type LayoutConfig } from "../hierarchy/tree_data";
import { MenuStyles } from "./tree_menu_styles";
import { TreeMenuNode } from "./tree_menu_node";
import { useMeasurementSvg, useMeasurementHtml } from "../hierarchy/useMeasurementElement";
import { calculateLayout } from "../hierarchy/tree_chart_layout";
import { usePersistedExpandState } from "../hierarchy/usePersistedExpandState";
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
}

// Compressed layout configuration for navigation menu
const menuLayoutConfig: LayoutConfig = {
  spacing: {
    vertical: 12, // Reduced from 20
    horizontal: 16, // Reduced from 30
  },
  margins: {
    top: 10, // Reduced from 30
    left: 10, // Reduced from 20
    right: 10,
    bottom: 10, // Reduced from 30
  },
};

const TreeMenu: React.FC<TreeMenuProps> = ({
  chartData,
  initialExpandState,
  highlightedTermId,
  onNodeClick,
}) => {
  // Container ref to measure width
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(0);

  // Use persisted expand state and scroll management hook
  const {
    expandState,
    handleNodeToggle,
    restoreScrollPosition,
    setInitialExpandState,
  } = usePersistedExpandState();

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
        setContainerWidth(width);
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
        menu.
      </Alert>
    );
  }

  // Calculate the layout with current expanded state and compressed configuration
  const { root, dimensions } = useMemo(() => {
    // Only pass container width if it's been measured (> 0)
    const maxWidth = containerWidth > 0 ? containerWidth : undefined;
    return calculateLayout(
      chartData,
      expandState,
      menuLayoutConfig,
      undefined,
      maxWidth,
    );
  }, [chartData, expandState, containerWidth]);

  // Calculate the actual height needed for the menu content
  const menuHeight = useMemo(() => {
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

  // Node click handler to navigate to the node's details
  const handleNodeClick = useCallback((node: any) => {
    // If custom click handler provided, use that
    if (onNodeClick) {
      onNodeClick(node);
      return;
    }

    // Otherwise, default navigation behavior
    if (node.type === "term") {
      navigate({ to: `/app/nodes/term/${node.id}` });
    } else if (node.type === "domain") {
      navigate({ to: `/app/nodes/domain/${node.id}` });
    } else if (node.type === "layer") {
      navigate({ to: `/app/nodes/layer/${node.id}` });
    }
  }, [navigate, onNodeClick]);

  return (
    <div
      ref={containerRef}
      style={{
        ...MenuStyles.menuContainer,
        position: "relative",
        minHeight: menuHeight,
        overflowY: "auto",
        maxHeight: "100%",
      }}
    >
      {/* SVG Layer */}
      <svg
        width={dimensions.width}
        height={menuHeight}
        style={{ display: "block" }}
      >
        {/* Render all children of the root node */}
        {root.children.map((child: any, index: number) => (
          <TreeMenuNode
            key={child.id || index}
            node={child}
            parentNode={root}
            onToggle={handleNodeToggle}
            onNodeClick={handleNodeClick}
            highlightedTermId={highlightedTermId}
          />
        ))}
      </svg>
    </div>
  );
};

export { TreeMenu };
