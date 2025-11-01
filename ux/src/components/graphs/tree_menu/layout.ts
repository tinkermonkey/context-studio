import type {
  HierarchyNode,
  Dimensions,
  LayoutConfig,
  ChartData,
} from "../tree_chart/tree_data";
import { layoutConfig, chartStyles, definitionSpacing } from "./config";
import { TextWidthCache, TextHeightCache } from "./measurement";
import type { ExpandState } from "./state";

// Global cache instances
const textWidthCache = new TextWidthCache();
const textHeightCache = new TextHeightCache(chartStyles.nodeLabel);
const definitionHeightCache = new TextHeightCache(chartStyles.nodeDefinition);

// Track last container width to clear cache when it changes
let lastContainerWidth: number | undefined;

// Default expand state for new nodes
const defaultExpandState = false;

/**
 * Helper function to calculate maximum depth of the tree
 */
export function calculateMaxDepth(
  node: HierarchyNode,
  currentDepth = 0,
): number {
  if (!node.children || node.children.length === 0) {
    return currentDepth;
  }

  return Math.max(
    ...node.children.map((child) => calculateMaxDepth(child, currentDepth + 1)),
  );
}

/**
 * Collect all labels from the tree for width calculation
 */
function collectLabels(node: HierarchyNode, labels: string[] = []): string[] {
  labels.push(node.title);
  if (node.children) {
    node.children.forEach((child) => collectLabels(child, labels));
  }
  return labels;
}

/**
 * Recursive function to process nodes and assign coordinates
 * @param node The node being processed
 * @param expandState The current expansion state of the tree
 * @param depth The depth of the current node
 * @param parentX The x position of the parent node
 * @param startY The y position to start placing this node
 * @param maxY Used to keep track of the maximum Y position reached overall
 * @param config Layout configuration parameters
 * @param containerWidth The width of the container to fit into
 * @param showDefinitions Whether to show definitions
 * @param titleWidth Width for titles (number in pixels or percentage 0-1)
 */
function processNode(
  node: HierarchyNode,
  expandState: ExpandState,
  depth: number,
  parentX?: number,
  startY?: number,
  maxY: number = 0,
  config: LayoutConfig = layoutConfig,
  containerWidth: number = 0,
  showDefinitions: boolean = false,
  titleWidth: number | undefined = undefined,
): { node: HierarchyNode; bottomY: number } {
  const x =
    depth === 0
      ? config.margins.left
      : (parentX ?? config.margins.left) + config.spacing.horizontal;

  const y = startY ?? config.margins.top;

  // Get expanded state from existing tree or default to true
  const isExpanded =
    (expandState.get(node.id || node.title) ?? depth === 0)
      ? true
      : defaultExpandState;

  node.x = x;
  node.y = y;
  node.depth = depth;

  // Calculate title width based on showDefinitions and titleWidth parameter
  let titleRightEdge: number | undefined;

  if (showDefinitions && titleWidth !== undefined) {
    // When showing definitions, create a fixed right edge for the title column
    // titleWidth defines where the right edge of the title column should be
    if (titleWidth > 0 && titleWidth < 1) {
      // Percentage: calculate the fixed right edge position from container width
      titleRightEdge = containerWidth * titleWidth;
    } else {
      // Absolute pixel value: use as the fixed right edge position
      titleRightEdge = titleWidth;
    }

    // Title width is from current x position to the fixed right edge
    // As nodes indent deeper (x increases), their title width decreases, keeping right edge aligned
    node.titleWidth = Math.max(50, titleRightEdge - x);
  } else {
    // Full width mode (existing behavior)
    const rightPadding = config.margins.right + 20; // Extra padding for expand controls
    node.titleWidth = Math.max(50, containerWidth - x - rightPadding);
  }

  // Calculate text height based on the allocated width (for text wrapping)
  node.titleHeight =
    depth === 0
      ? 0
      : textHeightCache.getTextHeight(node.title, node.titleWidth);

  // Calculate definition dimensions if showing definitions
  const totalGap =
    (config.expandControls?.width || 0) +
    definitionSpacing.controlsWidth +
    definitionSpacing.leftMargin;
  if (showDefinitions && node.definition && titleRightEdge !== undefined) {
    // Definition starts after: titleRightEdge + expandControls + controlsWidth + leftMargin
    const rightPadding = config.margins.right + 20;

    node.definitionWidth = Math.max(
      0,
      containerWidth - titleRightEdge - totalGap - rightPadding,
    );
    node.definitionHeight = definitionHeightCache.getTextHeight(
      node.definition,
      node.definitionWidth,
    );
  } else {
    node.definitionWidth = 0;
    node.definitionHeight = 0;
  }

  node.expanded = isExpanded;
  node.hasChildren = node.children && node.children.length > 0;

  maxY = Math.max(maxY, y);

  // Calculate the bottom Y position accounting for text height and definition height
  // Use the actual text height plus spacing
  let currentBottomY: number;

  // Calculate the full width and height
  node.width = ((titleRightEdge || 0) + totalGap + node.definitionWidth) - node.x;
  node.height =
    Math.max(node.titleHeight || 0, node.definitionHeight || 0) +
    config.spacing.vertical;

  if (
    node.definition &&
    node.definitionHeight &&
    node.definitionHeight > chartStyles.nodeLabel.height
  ) {
    // Definition extends beyond the label height
    //currentBottomY = y + node.definitionHeight + config.spacing.vertical;
    currentBottomY = y + node.titleHeight + config.spacing.vertical;
  } else {
    // No definition or definition doesn't extend beyond label
    currentBottomY = y + node.titleHeight + config.spacing.vertical;
  }
  currentBottomY = y + node.height;

  // Only process children if node is expanded
  if (node.children && node.children.length > 0 && isExpanded) {
    // When using container width, children don't need max sibling width
    node.children = node.children.map((child) => {
      const result = processNode(
        child,
        expandState,
        depth + 1,
        x,
        currentBottomY,
        maxY,
        config,
        containerWidth,
        showDefinitions,
        titleWidth,
      );
      currentBottomY = result.bottomY;
      return result.node;
    });
  }

  return {
    node: node,
    bottomY: currentBottomY,
  };
}

/**
 * Calculate layout for the tree chart
 * @param chartData Chart data with root node
 * @param expandState Current expand state map
 * @param config Layout configuration
 * @param maxWidth Maximum width constraint
 * @param containerWidth Container width for full-width nodes
 * @param showDefinitions Whether to show node definitions
 * @param titleWidth Width for titles when showing definitions (number in pixels or percentage 0-1, default 0.2)
 * @returns Updated chart data with calculated positions and dimensions
 */
export function calculateLayout(
  chartData: ChartData,
  expandState: ExpandState,
  config: LayoutConfig = layoutConfig,
  maxWidth?: number,
  containerWidth?: number,
  showDefinitions: boolean = false,
  titleWidth: number = 0.2,
): ChartData {
  // Clear text height cache when container width changes
  // When container width changes, all node.titleWidth values change, invalidating cached heights
  if (containerWidth !== lastContainerWidth) {
    textHeightCache.clear();
    lastContainerWidth = containerWidth;
  }

  const allLabels = collectLabels(chartData.root);
  const maxTextWidth = Math.max(
    ...allLabels.map((label) => textWidthCache.getTextWidth(label)),
  );

  // Process the root node and recursively its children
  const result = processNode(
    chartData.root,
    expandState,
    0,
    undefined,
    undefined,
    config.margins.top,
    config,
    containerWidth,
    showDefinitions,
    titleWidth,
  );
  const root = result.node;
  const totalHeight = result.bottomY;

  // Calculate dimensions
  const maxDepth = calculateMaxDepth(chartData.root);
  const maxX = config.margins.left + maxDepth * config.spacing.horizontal;
  const textPadding = 20;

  // Calculate natural width based on content including right margin
  const naturalWidth =
    maxX + maxTextWidth + textPadding + (config.margins.right || 0);

  // Use maxWidth constraint if provided, otherwise use natural width
  let finalWidth = naturalWidth;

  if (maxWidth && maxWidth > 0) {
    // When constrained by maxWidth, just use maxWidth but ensure content fits within margins
    finalWidth = maxWidth;
  }

  const dimensions: Dimensions = {
    width: finalWidth,
    height: totalHeight + config.margins.bottom,
  };

  return {
    root,
    dimensions,
  };
}

// Utility functions for cache management
export function clearTextWidthCache(): void {
  textWidthCache.clear();
}

export function getTextWidthCacheSize(): number {
  return textWidthCache.size();
}

// Direct access to cached text width measurement (useful for external components)
export function getCachedTextWidth(text: string): number {
  return textWidthCache.getTextWidth(text);
}

// Utility functions for text height cache management
export function clearTextHeightCache(): void {
  textHeightCache.clear();
}

export function getTextHeightCacheSize(): number {
  return textHeightCache.size();
}
