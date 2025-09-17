/**
 * D3.js Force Layout Integration
 *
 * Uses D3's force simulation for better graph layout
 */

import { UnifiedNode, UnifiedSearchLink, SOURCE_METADATA } from "@/api/types/unified";

// Declare d3 as available globally from CDN
declare const d3: any;

export interface NodePosition {
  id: string;
  x: number;
  y: number;
}

export interface GraphDimensions {
  width: number;
  height: number;
}

export interface D3LayoutOptions {
  linkDistance?: number;
  linkStrength?: number;
  chargeStrength?: number;
  collisionRadius?: number;
  clusterStrength?: number;
  alphaDecay?: number;
  velocityDecay?: number;
}

const DEFAULT_D3_OPTIONS: Required<D3LayoutOptions> = {
  linkDistance: 150,
  linkStrength: 0.6,
  chargeStrength: -800,
  collisionRadius: 60,
  clusterStrength: 0.2,
  alphaDecay: 0.005, // Much slower decay for more settling time
  velocityDecay: 0.6, // Lower velocity decay for more movement
};

/**
 * Calculate graph layout using D3 force simulation
 */
export function calculateD3Layout(
  nodes: UnifiedNode[],
  links: UnifiedSearchLink[],
  dimensions: GraphDimensions,
  options: D3LayoutOptions = {}
): Promise<NodePosition[]> {
  return new Promise((resolve) => {
    const opts = { ...DEFAULT_D3_OPTIONS, ...options };
    const { width, height } = dimensions;

    // Create cluster centers for each source type
    const sourceTypes = [...new Set(nodes.map(node => node.source))];
    const clusterCenters = new Map<string, { x: number; y: number }>();

    sourceTypes.forEach((source, index) => {
      const angle = (2 * Math.PI * index) / sourceTypes.length;
      const radius = Math.min(width, height) * 0.25;
      clusterCenters.set(source, {
        x: width / 2 + Math.cos(angle) * radius,
        y: height / 2 + Math.sin(angle) * radius,
      });
    });

    // Prepare D3 nodes with calculated properties
    const d3Nodes = nodes.map(node => {
      const connectionCount = links.filter(link =>
        link.subject === node.id || link.object === node.id
      ).length;
      const confidenceScore = node.confidence_score || 0.5;
      const nodeRadius = 15 + Math.min(10, connectionCount * 2) + (confidenceScore * 5);
      const clusterCenter = clusterCenters.get(node.source) || { x: width / 2, y: height / 2 };

      return {
        id: node.id,
        source: node.source,
        radius: nodeRadius,
        mass: 1 + confidenceScore + (connectionCount * 0.1),
        clusterX: clusterCenter.x,
        clusterY: clusterCenter.y,
        // Start near cluster center
        x: clusterCenter.x + (Math.random() - 0.5) * 100,
        y: clusterCenter.y + (Math.random() - 0.5) * 100,
      };
    });

    // Prepare D3 links
    const d3Links = links
      .filter(link => {
        const nodeIds = new Set(nodes.map(n => n.id));
        return nodeIds.has(link.subject) && nodeIds.has(link.object);
      })
      .map(link => ({
        source: link.subject,
        target: link.object,
        weight: link.weight || 1,
      }));

    // Create D3 force simulation
    const simulation = d3.forceSimulation(d3Nodes)
      .force("link", d3.forceLink(d3Links)
        .id((d: any) => d.id)
        .distance(opts.linkDistance)
        .strength(opts.linkStrength)
      )
      .force("charge", d3.forceManyBody()
        .strength((d: any) => opts.chargeStrength * (1 + d.mass * 0.3)) // Stronger repulsion for larger nodes
        .distanceMin(30) // Minimum distance for charge effect
        .distanceMax(400) // Maximum distance for charge effect
      )
      .force("collision", d3.forceCollide()
        .radius((d: any) => d.radius + 25) // Increased padding for text labels
        .strength(1)
        .iterations(3) // Multiple collision iterations for better separation
      )
      .force("center", d3.forceCenter(width / 2, height / 2)
        .strength(0.1)
      )
      .force("cluster", () => {
        // Custom cluster force with better distance handling
        d3Nodes.forEach((node: any) => {
          const dx = node.clusterX - node.x;
          const dy = node.clusterY - node.y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance > 0) {
            // Gentle attraction that doesn't override collision detection
            const targetDistance = 150; // Desired distance from cluster center
            const force = opts.clusterStrength * Math.min(distance / targetDistance, 1) * 0.5;
            node.vx += (dx / distance) * force;
            node.vy += (dy / distance) * force;
          }
        });
      })
      .alphaDecay(opts.alphaDecay)
      .velocityDecay(opts.velocityDecay);

    // Let simulation run longer with better convergence detection
    let tickCount = 0;
    let lastAlpha = 1;
    let stableCount = 0;

    simulation.on("tick", () => {
      tickCount++;

      // Check if simulation has stabilized
      const currentAlpha = simulation.alpha();
      if (Math.abs(currentAlpha - lastAlpha) < 0.001) {
        stableCount++;
      } else {
        stableCount = 0;
      }
      lastAlpha = currentAlpha;

      // Stop if stable for 50 ticks or after minimum cycles
      if ((stableCount > 50 && tickCount > 300) || tickCount > 1000) {
        simulation.stop();
        const positions: NodePosition[] = d3Nodes.map((node: any) => ({
          id: node.id,
          x: Math.max(node.radius + 40, Math.min(width - node.radius - 40, node.x)),
          y: Math.max(node.radius + 40, Math.min(height - node.radius - 40, node.y)),
        }));
        resolve(positions);
      }
    });

    // Fallback timeout - much longer now
    setTimeout(() => {
      simulation.stop();
      const positions: NodePosition[] = d3Nodes.map((node: any) => ({
        id: node.id,
        x: Math.max(node.radius + 40, Math.min(width - node.radius - 40, node.x)),
        y: Math.max(node.radius + 40, Math.min(height - node.radius - 40, node.y)),
      }));
      resolve(positions);
    }, 15000); // 15 second max
  });
}

/**
 * Simple circular layout for when there are no links (D3 version)
 */
export function calculateD3CircularLayout(
  nodes: UnifiedNode[],
  dimensions: GraphDimensions
): NodePosition[] {
  const { width, height } = dimensions;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) / 3;

  return nodes.map((node, index) => {
    const angle = (2 * Math.PI * index) / nodes.length;
    return {
      id: node.id,
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    };
  });
}

/**
 * Main D3 layout function
 */
export function calculateD3LayoutMain(
  nodes: UnifiedNode[],
  links: UnifiedSearchLink[],
  dimensions: GraphDimensions,
  options: D3LayoutOptions = {}
): Promise<NodePosition[]> {
  if (nodes.length === 0) return Promise.resolve([]);

  if (links.length === 0) {
    return Promise.resolve(calculateD3CircularLayout(nodes, dimensions));
  }

  return calculateD3Layout(nodes, links, dimensions, options);
}