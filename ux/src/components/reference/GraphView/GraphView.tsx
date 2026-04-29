/**
 * GraphView Component
 *
 * Main graph visualization component for search results using Reagraph
 */

import React, { useMemo, useState, useRef, useEffect } from "react";
import { Alert, Spinner } from "flowbite-react";
import { Info, AlertTriangle } from "lucide-react";
import { GraphCanvas, lightTheme } from "reagraph";
import {
  UnifiedNode,
  UnifiedSearchLink,
  SOURCE_METADATA,
} from "@/api/types/unified";
import {
  buildGroupedTreeStructure,
  convertToReagraphFormat,
  analyzeGraphStructure,
} from "./graphUtils";
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { getSourceBadgeColor } from "@/utils/sourceUtils";

interface GraphViewProps {
  results: UnifiedNode[];
  searchLinks: UnifiedSearchLink[];
  onSelectNode?: (node: UnifiedNode) => void;
  isSearching?: boolean;
  width?: number;
  height?: number;
  layoutType?: "cluster" | "tree" | "galaxy";
}

export const GraphView: React.FC<GraphViewProps> = ({
  results,
  searchLinks,
  onSelectNode,
  isSearching = false,
  layoutType = "tree",
}) => {
  const [layoutError, setLayoutError] = useState<string | null>(null);
  const [currentLayoutType, setCurrentLayoutType] =
    useState<string>("forceDirected2d");
  const [hoveredNode, setHoveredNode] = useState<UnifiedNode | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const [pinnedNode, setPinnedNode] = useState<UnifiedNode | null>(null);
  const [pinnedPosition, setPinnedPosition] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Convert data based on layout type - use grouping for tree layout
  const { nodes, edges } = useMemo(() => {
    if (layoutType === "tree" && searchLinks.length > 0) {
      // Use predicate grouping for tree layout
      const groupedStructure = buildGroupedTreeStructure(results, searchLinks);
      return convertToReagraphFormat(groupedStructure, SOURCE_METADATA);
    } else {
      // Use simple node/edge structure for cluster and galaxy layouts
      const simpleNodes = results.map((node) => {
        const sourceMetadata = SOURCE_METADATA[node.source] || {
          color: "gray",
        };
        const colorMap: Record<string, string> = {
          blue: "#3B82F6",
          orange: "#F97316",
          purple: "#8B5CF6",
          red: "#EF4444",
          gray: "#6B7280",
        };

        return {
          id: node.id,
          label: node.title || node.id,
          fill: colorMap[sourceMetadata.color] || colorMap.gray,
          size: 10 + (node.relevance_score || 0.5) * 10,
          data: node, // Store original node data
        };
      });

      const simpleEdges = searchLinks
        .filter((link) => {
          const nodeIds = new Set(results.map((node) => node.id));
          return nodeIds.has(link.subject) && nodeIds.has(link.object);
        })
        .map((link) => ({
          id: link.id,
          source: link.subject,
          target: link.object,
          label: link.predicate,
          data: link, // Store original link data
        }));

      return { nodes: simpleNodes, edges: simpleEdges };
    }
  }, [results, searchLinks, layoutType]);

  // Analyze graph structure to determine if hierarchical layout is suitable
  const graphAnalysis = useMemo(() => {
    return analyzeGraphStructure(nodes, edges);
  }, [nodes, edges]);

  // Handle node selection
   
  const handleNodeClick = (node: any) => {
    if (node.data) {
      // For grouped structure, only handle clicks on data nodes (not predicate nodes)
      if (
        layoutType === "tree" &&
        "type" in node.data &&
        node.data.type === "predicate"
      ) {
        // Don't handle clicks on predicate nodes
        return;
      }

      // For grouped structure, extract the original node
      const originalNode =
        layoutType === "tree" &&
        "originalNode" in node.data &&
        node.data.originalNode
          ? node.data.originalNode
          : node.data;

      // Pin the hover card at current position
      setPinnedNode(originalNode);
      setPinnedPosition(tooltipPosition);

      // Clear hover state since we're now pinned
      setHoveredNode(null);

      // Don't call onSelectNode immediately - only when "View Details" is clicked
    }
  };

  // Handle mouse move for tooltips
  const handleMouseMove = (event: React.MouseEvent) => {
    // Get the position relative to the container
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Store both viewport coordinates and container-relative coordinates
    setTooltipPosition({
      x: x, // Container-relative X
      y: y, // Container-relative Y
    });
  };

  // Smart positioning function for tooltip
  const getTooltipStyle = (position: { x: number; y: number }) => {
    if (!position || !containerRef.current) return {};

    const containerRect = containerRef.current.getBoundingClientRect();
    const containerWidth = containerRect.width;
    const containerHeight = containerRect.height;
    const tooltipWidth = 320; // w-80 = 20rem = 320px
    const tooltipHeight = 200; // Estimated tooltip height
    const offset = 15;

    let x = position.x;
    let y = position.y;
    // eslint-disable-next-line no-useless-assignment
    let transform = "";

    // Determine horizontal positioning
    const isNearRightEdge = x > containerWidth - tooltipWidth - offset;
    const isNearLeftEdge = x < tooltipWidth / 2;

    if (isNearRightEdge) {
      // Position to the left of cursor
      x = position.x - offset;
      transform = "translateX(-100%)";
    } else if (isNearLeftEdge) {
      // Position to the right of cursor
      x = position.x + offset;
      transform = "translateX(0%)";
    } else {
      // Position centered horizontally on cursor (default)
      x = position.x;
      transform = "translateX(-50%)";
    }

    // Determine vertical positioning
    const isNearBottomEdge = y > containerHeight - tooltipHeight - offset;
    const isNearTopEdge = y < tooltipHeight / 2;

    if (isNearBottomEdge) {
      // Position above cursor when near bottom edge
      y = position.y - offset;
      transform += " translateY(-100%)";
    } else if (isNearTopEdge) {
      // Position below cursor when near top edge
      y = position.y + offset;
      transform += " translateY(0%)";
    } else {
      // Default: Position below cursor (don't cover the node)
      y = position.y + offset;
      transform += " translateY(0%)";
    }

    return {
      left: x,
      top: y,
      transform,
    };
  };

  // Determine layout type for Reagraph with fallback logic
  const getLayoutType = () => {
    switch (layoutType) {
      case "tree":
        // Only use hierarchical layout if the graph structure supports it
        if (graphAnalysis.isTreeLike && nodes.length > 1) {
          return "hierarchicalTd";
        }
        // Fallback to force-directed for non-tree structures
        console.warn(
          "Graph structure not suitable for tree layout, falling back to force-directed:",
          {
            hasMultipleRoots: graphAnalysis.hasMultipleRoots,
            hasCycles: graphAnalysis.hasCycles,
            hasNoRoot: graphAnalysis.hasNoRoot,
            nodeCount: nodes.length,
            edgeCount: edges.length,
          },
        );
        return "forceDirected2d";
      case "galaxy":
        return "radialOut2d";
      case "cluster":
      default:
        return "forceDirected2d";
    }
  };

  // Update layout type and clear errors when dependencies change
  useEffect(() => {
    setLayoutError(null);
    const newLayoutType = getLayoutType();
    setCurrentLayoutType(newLayoutType);
  }, [
    layoutType,
    nodes.length,
    edges.length,
    graphAnalysis.isTreeLike,
    graphAnalysis.hasMultipleRoots,
    graphAnalysis.hasCycles,
    graphAnalysis.hasNoRoot,
  ]);

  // Handle escape key to unpin hover card
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && pinnedNode) {
        setPinnedNode(null);
        setPinnedPosition(null);
        setHoveredNode(null);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [pinnedNode]);

  // Error boundary for graph rendering
  const handleGraphError = (error: Error) => {
    console.error("Graph rendering error:", error);
    setLayoutError(error.message);
    // Fallback to force-directed layout
    if (currentLayoutType !== "forceDirected2d") {
      setCurrentLayoutType("forceDirected2d");
    }
  };

  // Show loading state
  if (isSearching && results.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="space-y-4 text-center">
          <Spinner size="lg" />
          <p className="text-gray-600">Loading graph visualization...</p>
        </div>
      </div>
    );
  }

  // Show empty state
  if (results.length === 0) {
    return (
      <Alert color="info" icon={Info}>
        <div className="space-y-2">
          <p className="font-medium">No nodes to display</p>
          <p className="text-sm">
            Search results will appear as nodes in this graph view.
          </p>
        </div>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      {/* Graph stats */}
      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>
          {layoutType === "tree" && searchLinks.length > 0 ? (
            <>
              {results.length} data node{results.length !== 1 ? "s" : ""},{" "}
              {
                nodes.filter(
                  (n) =>
                    n.data && "type" in n.data && n.data.type === "predicate",
                ).length
              }{" "}
              predicate
              {nodes.filter(
                (n) =>
                  n.data && "type" in n.data && n.data.type === "predicate",
              ).length !== 1
                ? "s"
                : ""}
              , {edges.length} link{edges.length !== 1 ? "s" : ""}
            </>
          ) : (
            <>
              {results.length} node{results.length !== 1 ? "s" : ""},{" "}
              {edges.length} link{edges.length !== 1 ? "s" : ""}
            </>
          )}
        </span>

        {isSearching && (
          <span className="flex items-center gap-2">
            <Spinner size="sm" />
            Updating...
          </span>
        )}
      </div>

      {/* Error message */}
      {layoutError && (
        <Alert color="warning" icon={AlertTriangle}>
          <div className="space-y-2">
            <p className="font-medium">Graph Layout Error</p>
            <p className="text-sm">
              {layoutError}. Falling back to force-directed layout.
            </p>
          </div>
        </Alert>
      )}

      {/* Graph visualization */}
      <div className="rounded-lg border border-gray-200 bg-white">
        <div
          ref={containerRef}
          className="relative aspect-square w-full"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => {
            if (!pinnedNode) {
              setHoveredNode(null);
            }
          }}
          onClick={(e) => {
            // Unpin if clicking on background (not on a node)
            if (e.target === e.currentTarget) {
              setPinnedNode(null);
              setPinnedPosition(null);
              setHoveredNode(null);
            }
          }}
        >
          <ErrorBoundary onError={handleGraphError}>
            <GraphCanvas
              nodes={nodes}
              edges={edges}
              theme={lightTheme}
               
              layoutType={currentLayoutType as any}
              onNodeClick={handleNodeClick}
              onCanvasClick={() => {
                // Unpin hover card when clicking on canvas background
                setPinnedNode(null);
                setPinnedPosition(null);
                setHoveredNode(null);
              }}
               
              onNodePointerOver={(node: any) => {
                if (node && node.data) {
                  // For grouped structure, only show tooltips for data nodes
                  if (
                    layoutType === "tree" &&
                    "type" in node.data &&
                    node.data.type === "predicate"
                  ) {
                    return;
                  }

                  // For grouped structure, extract the original node
                  const originalNode =
                    layoutType === "tree" &&
                    "originalNode" in node.data &&
                    node.data.originalNode
                      ? node.data.originalNode
                      : node.data;

                  // If hovering over a different node than the pinned one, unpin and show hover
                  if (pinnedNode && pinnedNode.id !== originalNode.id) {
                    setPinnedNode(null);
                    setPinnedPosition(null);
                  }

                  // Only show hover tooltip if not hovering over the same pinned node
                  if (!pinnedNode || pinnedNode.id !== originalNode.id) {
                    setHoveredNode(originalNode);
                  }
                }
              }}
              onNodePointerOut={() => {
                // Only clear hover if there's no pinned card
                if (!pinnedNode) {
                  setHoveredNode(null);
                }
              }}
              animated={false}
              edgeArrowPosition="end"
              edgeLabelPosition="above"
              labelType="all"
              draggable
            />
          </ErrorBoundary>

          {/* Node Info Tooltip */}
          {((hoveredNode && tooltipPosition) ||
            (pinnedNode && pinnedPosition)) && (
            <div
              className={`animate-in fade-in absolute z-50 w-80 rounded-lg border border-gray-300 bg-white p-4 shadow-lg duration-200 ${pinnedNode ? "pointer-events-auto" : "pointer-events-none"}`}
              style={getTooltipStyle(
                (pinnedNode && pinnedPosition) || tooltipPosition!,
              )}
            >
              <div className="space-y-3">
                {(() => {
                  const currentNode = pinnedNode || hoveredNode;
                  if (!currentNode) return null;

                  return (
                    <>
                      {/* Title */}
                      <div className="text-base font-semibold text-gray-900">
                        {currentNode.title}
                      </div>

                      {/* Image Display */}
                      {(() => {
                        // Check for file-based image content first (from normalized API)
                        if (
                          currentNode.attributes?.file_type === "image" &&
                          currentNode.attributes?.file_url
                        ) {
                          return (
                            <div className="overflow-hidden rounded-lg border bg-gray-50">
                              <img
                                src={String(currentNode.attributes.file_url)}
                                alt={
                                  String(currentNode.attributes.file_name) ||
                                  currentNode.title
                                }
                                className="h-32 w-full object-cover"
                                onError={(e) => {
                                  // Hide image if it fails to load
                                  (e.target as HTMLElement).style.display =
                                    "none";
                                }}
                                loading="lazy"
                              />
                            </div>
                          );
                        }

                        // Fallback: check for legacy image URLs in attributes
                        const imageUrl =
                          currentNode.attributes?.image ||
                          currentNode.attributes?.image_url ||
                          currentNode.attributes?.thumbnail ||
                          currentNode.attributes?.depiction ||
                          currentNode.attributes?.picture ||
                          currentNode.attributes?.photo;

                        if (imageUrl && typeof imageUrl === "string") {
                          return (
                            <div className="overflow-hidden rounded-lg border bg-gray-50">
                              <img
                                src={imageUrl}
                                alt={currentNode.title}
                                className="h-32 w-full object-cover"
                                onError={(e) => {
                                  // Hide image if it fails to load
                                  (e.target as HTMLElement).style.display =
                                    "none";
                                }}
                                loading="lazy"
                              />
                            </div>
                          );
                        }
                        return null;
                      })()}

                      {/* Basic Info */}
                      <div className="grid grid-cols-1 gap-1 text-xs text-gray-600">
                        <div>
                          <span className="font-medium">ID:</span>{" "}
                          <span className="font-mono text-xs">
                            {currentNode.id}
                          </span>
                        </div>
                        <div>
                          <span className="font-medium">Source:</span>{" "}
                          <span className="capitalize">
                            {currentNode.source.replace("_", " ")}
                          </span>
                        </div>
                        {currentNode.relevance_score && (
                          <div>
                            <span className="font-medium">Relevance:</span>{" "}
                            {(currentNode.relevance_score * 100).toFixed(1)}%
                          </div>
                        )}
                      </div>

                      {/* Definition */}
                      {currentNode.definition && (
                        <div className="border-t pt-2 text-xs text-gray-700">
                          <div className="mb-1 font-medium">Definition:</div>
                          <div className="line-clamp-3">
                            {currentNode.definition}
                          </div>
                        </div>
                      )}

                      {/* Action Links */}
                      <div className="flex gap-3 border-t pt-2">
                        {/* View Details Button */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (onSelectNode) {
                              onSelectNode(currentNode);
                            }
                          }}
                          className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 underline hover:text-blue-800"
                        >
                          View Details
                          <svg
                            className="h-3 w-3"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                            />
                          </svg>
                        </button>

                        {/* Source Link */}
                        {currentNode.source_url && (
                          <a
                            href={currentNode.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 underline hover:text-blue-800"
                            onClick={(e) => e.stopPropagation()}
                          >
                            View Source
                            <svg
                              className="h-3 w-3"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                              />
                            </svg>
                          </a>
                        )}
                      </div>

                      {/* Pin indicator for pinned cards */}
                      {pinnedNode && (
                        <div className="border-t pt-2 text-xs text-gray-500 italic">
                          Card pinned - Click elsewhere or press Escape to close
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-xs text-gray-600">
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-full bg-blue-500"></div>
          <span>ConceptNet</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-full bg-orange-500"></div>
          <span>DBpedia</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-full bg-purple-500"></div>
          <span>Wikidata</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-full bg-red-500"></div>
          <span>Schema.org</span>
        </div>
      </div>
    </div>
  );
};

// Error Boundary Component for GraphCanvas
interface ErrorBoundaryProps {
  children: React.ReactNode;
  onError: (error: Error) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(
     
    _: Error,
  ): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
    this.props.onError(error);
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    // Reset error state when children change (new data)
    if (prevProps.children !== this.props.children && this.state.hasError) {
      this.setState({ hasError: false });
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full items-center justify-center">
          <Alert color="failure" icon={AlertTriangle}>
            <div className="space-y-2">
              <p className="font-medium">Graph rendering failed</p>
              <p className="text-sm">
                An error occurred while rendering the graph. Trying fallback
                layout...
              </p>
            </div>
          </Alert>
        </div>
      );
    }

    return this.props.children;
  }
}

export default GraphView;
