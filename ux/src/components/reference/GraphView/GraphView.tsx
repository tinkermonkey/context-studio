/**
 * GraphView Component
 *
 * Main graph visualization component for search results
 */

import React, { useMemo, useState, useRef, useEffect, useCallback } from "react";
import { Alert, Spinner, Button } from "flowbite-react";
import { Info, Play, Pause, RotateCcw, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";
import { UnifiedNode, UnifiedSearchLink, SOURCE_METADATA } from "@/api/types/unified";
import GraphNode from "./GraphNode";
import GraphLink from "./GraphLink";
import { D3LiveSimulation, NodePosition, GraphDimensions } from "./d3LiveLayout";

// Consistent padding for zoom operations (matches d3LiveLayout.ts)
const ZOOM_PADDING = 25;

interface GraphViewProps {
  results: UnifiedNode[];
  searchLinks: UnifiedSearchLink[];
  onSelectNode?: (node: UnifiedNode) => void;
  isSearching?: boolean;
  width?: number;
  height?: number;
}

export const GraphView: React.FC<GraphViewProps> = ({
  results,
  searchLinks,
  onSelectNode,
  isSearching = false,
  width = 800,
  height = 600,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerGroupRef = useRef<SVGGElement>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredLink, setHoveredLink] = useState<string | null>(null);
  const [dimensions, setDimensions] = useState<GraphDimensions>({ width, height });

  // Update dimensions based on container
  useEffect(() => {
    const updateDimensions = () => {
      if (svgRef.current) {
        const rect = svgRef.current.getBoundingClientRect();
        setDimensions({
          width: rect.width || width,
          height: rect.height || height,
        });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, [width, height]);

  // State for live simulation
  const [nodePositions, setNodePositions] = useState<NodePosition[]>([]);
  const [simulation, setSimulation] = useState<D3LiveSimulation | null>(null);
  const [isSimulationRunning, setIsSimulationRunning] = useState(false);
  const [simulationAlpha, setSimulationAlpha] = useState(1);

  // Create and manage live D3 simulation
  useEffect(() => {
    if (results.length === 0) {
      setNodePositions([]);
      if (simulation) {
        simulation.destroy();
        setSimulation(null);
      }
      return;
    }

    // Clean up previous simulation
    if (simulation) {
      simulation.destroy();
    }

    // Create new live simulation
    const newSimulation = new D3LiveSimulation(
      results,
      searchLinks,
      dimensions,
      {
        linkDistance: 150,
        linkStrength: 0.5,
        chargeStrength: -1500,
        collisionRadius: 100,
        clusterStrength: 0.08,
        alphaDecay: 0.008,
        velocityDecay: 0.7,
        onTick: (positions) => {
          setNodePositions(positions);
          setSimulationAlpha(newSimulation.getAlpha());
          setIsSimulationRunning(newSimulation.isRunning());
        },
        onEnd: (positions) => {
          setNodePositions(positions);
          setIsSimulationRunning(false);
          setSimulationAlpha(0);
        }
      }
    );

    setSimulation(newSimulation);
    setIsSimulationRunning(true);
    newSimulation.start();

    // Cleanup on unmount
    return () => {
      newSimulation.destroy();
    };
  }, [results, searchLinks, dimensions]);

  // Update simulation dimensions when component resizes
  useEffect(() => {
    if (simulation) {
      simulation.updateDimensions(dimensions);
    }
  }, [simulation, dimensions]);

  // Enable zoom when simulation and refs are ready
  useEffect(() => {
    if (simulation && svgRef.current && containerGroupRef.current) {
      // Add a delay to ensure D3 is fully loaded and DOM is ready
      setTimeout(() => {
        simulation.enableZoom(svgRef.current, containerGroupRef.current);

        // Initial fit to bounds
        if (nodePositions.length > 0) {
          setTimeout(() => {
            simulation.zoomToFit(nodePositions, ZOOM_PADDING, false);
          }, 200);
        }
      }, 100);
    }
  }, [simulation]);

  // Initial fit when zoom is first enabled
  useEffect(() => {
    if (simulation && nodePositions.length > 0 && !isSimulationRunning) {
      // Only fit once when simulation has ended
      simulation.zoomToFit(nodePositions, ZOOM_PADDING, true);
    }
  }, [simulation, nodePositions, isSimulationRunning]);

  // Create position lookup map
  const positionMap = useMemo(() => {
    const map = new Map<string, NodePosition>();
    nodePositions.forEach(pos => map.set(pos.id, pos));
    return map;
  }, [nodePositions]);

  // Filter links to only show those between visible nodes
  const visibleLinks = useMemo(() => {
    const nodeIds = new Set(results.map(node => node.id));
    return searchLinks.filter(link =>
      nodeIds.has(link.subject) && nodeIds.has(link.object)
    );
  }, [results, searchLinks]);

  // Group nodes by source for cluster visualization
  const nodesBySource = useMemo(() => {
    const groups = new Map<string, UnifiedNode[]>();
    results.forEach(node => {
      if (!groups.has(node.source)) {
        groups.set(node.source, []);
      }
      groups.get(node.source)?.push(node);
    });
    return groups;
  }, [results]);

  // Calculate dynamic viewBox based on node positions
  const dynamicViewBox = useMemo(() => {
    if (nodePositions.length === 0) {
      return `0 0 ${dimensions.width} ${dimensions.height}`;
    }

    // Find the bounding box of all nodes
    const padding = 100; // Extra space around nodes
    const minX = Math.min(...nodePositions.map(pos => pos.x)) - padding;
    const maxX = Math.max(...nodePositions.map(pos => pos.x)) + padding;
    const minY = Math.min(...nodePositions.map(pos => pos.y)) - padding;
    const maxY = Math.max(...nodePositions.map(pos => pos.y)) + padding;

    const width = maxX - minX;
    const height = maxY - minY;

    // Ensure minimum size
    const minWidth = dimensions.width;
    const minHeight = dimensions.height;

    const finalWidth = Math.max(width, minWidth);
    const finalHeight = Math.max(height, minHeight);

    // Center the content if it's smaller than the container
    const offsetX = width < minWidth ? (minWidth - width) / 2 : 0;
    const offsetY = height < minHeight ? (minHeight - height) / 2 : 0;

    return `${minX - offsetX} ${minY - offsetY} ${finalWidth} ${finalHeight}`;
  }, [nodePositions, dimensions]);

  const handleNodeClick = (node: UnifiedNode) => {
    onSelectNode?.(node);
  };

  const handleNodeMouseEnter = (node: UnifiedNode) => {
    setHoveredNode(node.id);
  };

  const handleNodeMouseLeave = () => {
    setHoveredNode(null);
  };

  const handleLinkMouseEnter = (link: UnifiedSearchLink) => {
    setHoveredLink(link.id);
  };

  const handleLinkMouseLeave = () => {
    setHoveredLink(null);
  };

  // Simulation control functions
  const handlePlayPause = useCallback(() => {
    if (!simulation) return;

    if (isSimulationRunning) {
      simulation.pause();
      setIsSimulationRunning(false);
    } else {
      simulation.resume();
      setIsSimulationRunning(true);
    }
  }, [simulation, isSimulationRunning]);

  const handleRestart = useCallback(() => {
    if (!simulation) return;

    simulation.restart();
    setIsSimulationRunning(true);
    setSimulationAlpha(1);
  }, [simulation]);

  // Zoom control functions
  const handleZoomToFit = useCallback(() => {
    if (simulation && nodePositions.length > 0) {
      console.log('Fit button clicked, calling zoomToFit with', nodePositions.length, 'positions');
      simulation.zoomToFit(nodePositions, ZOOM_PADDING, true); // Animated fit
    } else {
      console.warn('Fit button clicked but conditions not met:', {
        simulation: !!simulation,
        positionsLength: nodePositions.length
      });
    }
  }, [simulation, nodePositions]);

  const handleResetZoom = useCallback(() => {
    if (simulation) {
      console.log('Reset zoom button clicked');
      simulation.resetZoom();
    } else {
      console.warn('Reset zoom clicked but no simulation');
    }
  }, [simulation]);

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
      {/* Graph stats and controls */}
      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>
          {results.length} node{results.length !== 1 ? 's' : ''}, {visibleLinks.length} link{visibleLinks.length !== 1 ? 's' : ''}
          {simulation && (
            <span className="ml-4">
              Simulation: {isSimulationRunning ? 'Running' : 'Paused'}
              {simulationAlpha > 0.15 && ` (${Math.round(simulationAlpha * 100)}% energy)`}
            </span>
          )}
        </span>

        <div className="flex items-center gap-2">
          {isSearching && (
            <span className="flex items-center gap-2">
              <Spinner size="sm" />
              Updating...
            </span>
          )}

          {simulation && (
            <div className="flex items-center gap-1">
              <Button
                size="xs"
                color="gray"
                onClick={handlePlayPause}
                className="flex items-center gap-1"
              >
                {isSimulationRunning ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                {isSimulationRunning ? 'Pause' : 'Play'}
              </Button>

              <Button
                size="xs"
                color="gray"
                onClick={handleRestart}
                className="flex items-center gap-1"
              >
                <RotateCcw className="h-3 w-3" />
                Restart
              </Button>

              <div className="border-l border-gray-300 mx-1 h-6"></div>

              <Button
                size="xs"
                color="gray"
                onClick={handleZoomToFit}
                className="flex items-center gap-1"
              >
                <Maximize2 className="h-3 w-3" />
                Fit
              </Button>

              <Button
                size="xs"
                color="gray"
                onClick={handleResetZoom}
                className="flex items-center gap-1"
              >
                <ZoomOut className="h-3 w-3" />
                Reset
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Graph visualization */}
      <div className="border border-gray-200 rounded-lg bg-white overflow-hidden">
        <svg
          ref={svgRef}
          width="100%"
          height={height}
          viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
          className="block"
        >
          {/* Arrow markers for links */}
          <defs>
            <marker
              id="arrowhead"
              markerWidth="8"
              markerHeight="6"
              refX="7"
              refY="3"
              orient="auto"
              markerUnits="userSpaceOnUse"
            >
              <polygon
                points="0 0, 8 3, 0 6"
                fill="#6B7280"
                opacity="0.7"
              />
            </marker>
            <marker
              id="arrowhead-highlighted"
              markerWidth="10"
              markerHeight="8"
              refX="9"
              refY="4"
              orient="auto"
              markerUnits="userSpaceOnUse"
            >
              <polygon
                points="0 0, 10 4, 0 8"
                fill="#374151"
                opacity="1"
              />
            </marker>
          </defs>

          {/* Container group for zoom/pan transforms */}
          <g ref={containerGroupRef}>
            {/* Render cluster backgrounds */}
          {Array.from(nodesBySource.entries()).map(([source, nodes]) => {
            if (nodes.length < 2) return null; // Don't show cluster for single nodes

            // Calculate cluster center and radius
            const positions = nodes.map(node => positionMap.get(node.id)).filter(Boolean) as NodePosition[];
            if (positions.length === 0) return null;

            const centerX = positions.reduce((sum, pos) => sum + pos.x, 0) / positions.length;
            const centerY = positions.reduce((sum, pos) => sum + pos.y, 0) / positions.length;

            // Calculate radius to encompass all nodes
            const maxDistance = Math.max(
              ...positions.map(pos => Math.sqrt((pos.x - centerX) ** 2 + (pos.y - centerY) ** 2))
            );
            const clusterRadius = maxDistance + 60; // Extra padding

            const sourceMetadata = SOURCE_METADATA[source] || { color: "gray" };
            const colorMap: Record<string, string> = {
              blue: "#3B82F6",
              orange: "#F97316",
              purple: "#8B5CF6",
              red: "#EF4444",
              gray: "#6B7280",
            };
            const clusterColor = colorMap[sourceMetadata.color] || colorMap.gray;

            return (
              <circle
                key={`cluster-${source}`}
                cx={centerX}
                cy={centerY}
                r={clusterRadius}
                fill={clusterColor}
                fillOpacity={0.05}
                stroke={clusterColor}
                strokeOpacity={0.2}
                strokeWidth={2}
                strokeDasharray="5,5"
                className="pointer-events-none"
              />
            );
          })}

          {/* Render links first (so they appear behind nodes) */}
          {visibleLinks.map(link => {
            const sourcePos = positionMap.get(link.subject);
            const targetPos = positionMap.get(link.object);

            if (!sourcePos || !targetPos) return null;

            return (
              <GraphLink
                key={link.id}
                link={link}
                sourceX={sourcePos.x}
                sourceY={sourcePos.y}
                targetX={targetPos.x}
                targetY={targetPos.y}
                onMouseEnter={handleLinkMouseEnter}
                onMouseLeave={handleLinkMouseLeave}
                isHighlighted={hoveredLink === link.id}
              />
            );
          })}

          {/* Render nodes */}
          {results.map(node => {
            const position = positionMap.get(node.id);
            if (!position) return null;

            // Calculate node size based on confidence and connections
            const connectionCount = visibleLinks.filter(link =>
              link.subject === node.id || link.object === node.id
            ).length;
            const confidenceScore = node.confidence_score || 0.5;

            // Base radius varies from 15-30 based on connections and confidence
            const baseRadius = 15 + Math.min(10, connectionCount * 2) + (confidenceScore * 5);

            return (
              <GraphNode
                key={node.id}
                node={node}
                x={position.x}
                y={position.y}
                radius={baseRadius}
                onClick={handleNodeClick}
                onMouseEnter={handleNodeMouseEnter}
                onMouseLeave={handleNodeMouseLeave}
                isHighlighted={hoveredNode === node.id}
              />
            );
          })}
          </g>
        </svg>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-xs text-gray-600">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-blue-500"></div>
          <span>ConceptNet</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-orange-500"></div>
          <span>DBpedia</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-purple-500"></div>
          <span>Wikidata</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500"></div>
          <span>Schema.org</span>
        </div>
      </div>
    </div>
  );
};

export default GraphView;