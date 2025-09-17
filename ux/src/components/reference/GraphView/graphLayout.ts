/**
 * Graph Layout Utilities
 *
 * Simple force-directed layout algorithm for positioning nodes
 */

import { UnifiedNode, UnifiedSearchLink } from "@/api/types/unified";

export interface NodePosition {
  id: string;
  x: number;
  y: number;
}

export interface GraphDimensions {
  width: number;
  height: number;
}

export interface LayoutOptions {
  iterations?: number;
  repulsionStrength?: number;
  attractionStrength?: number;
  linkStrength?: number;
  linkDistance?: number;
  damping?: number;
  nodeRadius?: number;
  collisionRadius?: number;
  centeringForce?: number;
  clusterStrength?: number;
  clusterRadius?: number;
}

const DEFAULT_OPTIONS: Required<LayoutOptions> = {
  iterations: 200,
  repulsionStrength: 1000,
  attractionStrength: 0.05,
  linkStrength: 0.8,
  linkDistance: 100,
  damping: 0.85,
  nodeRadius: 20,
  collisionRadius: 25,
  centeringForce: 0.02,
  clusterStrength: 0.3,
  clusterRadius: 200,
};

/**
 * Enhanced force-directed layout algorithm with collision detection
 */
export function calculateForceDirectedLayout(
  nodes: UnifiedNode[],
  links: UnifiedSearchLink[],
  dimensions: GraphDimensions,
  options: LayoutOptions = {}
): NodePosition[] {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const { width, height } = dimensions;
  const centerX = width / 2;
  const centerY = height / 2;

  // Create cluster centers for each source type
  const sourceTypes = [...new Set(nodes.map(node => node.source))];
  const clusterCenters = new Map<string, { x: number; y: number }>();

  // Arrange cluster centers in a circle around the main center
  sourceTypes.forEach((source, index) => {
    const angle = (2 * Math.PI * index) / sourceTypes.length;
    const radius = Math.min(width, height) * 0.25; // Cluster centers distance from main center
    clusterCenters.set(source, {
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius,
    });
  });

  // Create link map for node connections
  const linkMap = new Map<string, UnifiedSearchLink[]>();
  links.forEach(link => {
    if (!linkMap.has(link.subject)) {
      linkMap.set(link.subject, []);
    }
    if (!linkMap.has(link.object)) {
      linkMap.set(link.object, []);
    }
    linkMap.get(link.subject)?.push(link);
    linkMap.get(link.object)?.push(link);
  });

  // Initialize positions randomly but closer to center
  const positions: Map<string, { x: number; y: number; vx: number; vy: number; mass: number; nodeRadius: number }> = new Map();

  nodes.forEach(node => {
    // Start nodes near their cluster center
    const clusterCenter = clusterCenters.get(node.source) || { x: centerX, y: centerY };
    const angle = Math.random() * 2 * Math.PI;
    const radius = Math.random() * opts.clusterRadius * 0.5; // Start within cluster radius

    // Calculate node size based on confidence and connections (same as GraphView)
    const connectionCount = linkMap.get(node.id)?.length || 0;
    const confidenceScore = node.confidence_score || 0.5;
    const nodeRadius = 15 + Math.min(10, connectionCount * 2) + (confidenceScore * 5);

    positions.set(node.id, {
      x: clusterCenter.x + Math.cos(angle) * radius,
      y: clusterCenter.y + Math.sin(angle) * radius,
      vx: 0,
      vy: 0,
      mass: 1 + confidenceScore + (connectionCount * 0.1), // Higher confidence and connections = more mass
      nodeRadius: nodeRadius,
    });
  });


  // Run simulation with cooling schedule
  for (let i = 0; i < opts.iterations; i++) {
    const progress = i / opts.iterations;
    const temperature = 1 - progress; // Cooling from 1 to 0

    // Reset forces
    for (const pos of positions.values()) {
      pos.vx = 0;
      pos.vy = 0;
    }

    // 1. Repulsion forces (all nodes repel each other)
    const nodeIds = Array.from(positions.keys());
    for (let j = 0; j < nodeIds.length; j++) {
      for (let k = j + 1; k < nodeIds.length; k++) {
        const nodeA = positions.get(nodeIds[j])!;
        const nodeB = positions.get(nodeIds[k])!;

        const dx = nodeB.x - nodeA.x;
        const dy = nodeB.y - nodeA.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance > 0) {
          // Coulomb's law-like repulsion
          const force = (opts.repulsionStrength * nodeA.mass * nodeB.mass) / Math.max(distance * distance, 1);
          const fx = (dx / distance) * force;
          const fy = (dy / distance) * force;

          nodeA.vx -= fx / nodeA.mass;
          nodeA.vy -= fy / nodeA.mass;
          nodeB.vx += fx / nodeB.mass;
          nodeB.vy += fy / nodeB.mass;
        }
      }
    }

    // 2. Spring forces for linked nodes (Hooke's law)
    links.forEach(link => {
      const sourcePos = positions.get(link.subject);
      const targetPos = positions.get(link.object);

      if (sourcePos && targetPos) {
        const dx = targetPos.x - sourcePos.x;
        const dy = targetPos.y - sourcePos.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance > 0) {
          // Spring force: F = k * (current_length - rest_length)
          const displacement = distance - opts.linkDistance;
          const force = opts.linkStrength * displacement;

          const fx = (dx / distance) * force;
          const fy = (dy / distance) * force;

          sourcePos.vx += fx / sourcePos.mass;
          sourcePos.vy += fy / sourcePos.mass;
          targetPos.vx -= fx / targetPos.mass;
          targetPos.vy -= fy / targetPos.mass;
        }
      }
    });

    // 3. Strong collision detection and response
    for (let j = 0; j < nodeIds.length; j++) {
      for (let k = j + 1; k < nodeIds.length; k++) {
        const nodeA = positions.get(nodeIds[j])!;
        const nodeB = positions.get(nodeIds[k])!;

        const dx = nodeB.x - nodeA.x;
        const dy = nodeB.y - nodeA.y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const minDistance = nodeA.nodeRadius + nodeB.nodeRadius + 20; // 20px padding for labels

        if (distance < minDistance && distance > 0) {
          // Overlap detected - apply strong separation force
          const overlap = minDistance - distance;
          const separationForce = overlap * 2.0; // Much stronger separation

          // Ensure minimum separation even for tiny distances
          const effectiveDistance = Math.max(distance, 1);
          const fx = (dx / effectiveDistance) * separationForce;
          const fy = (dy / effectiveDistance) * separationForce;

          // Move nodes apart proportional to their mass
          const totalMass = nodeA.mass + nodeB.mass;
          const forceA = separationForce * (nodeB.mass / totalMass);
          const forceB = separationForce * (nodeA.mass / totalMass);

          nodeA.vx -= fx * (forceA / nodeA.mass);
          nodeA.vy -= fy * (forceA / nodeA.mass);
          nodeB.vx += fx * (forceB / nodeB.mass);
          nodeB.vy += fy * (forceB / nodeB.mass);
        }
      }
    }

    // 4. Cluster attraction forces
    nodes.forEach(node => {
      const pos = positions.get(node.id)!;
      const clusterCenter = clusterCenters.get(node.source) || { x: centerX, y: centerY };

      const dx = clusterCenter.x - pos.x;
      const dy = clusterCenter.y - pos.y;
      const distance = Math.sqrt(dx * dx + dy * dy);

      if (distance > 0) {
        // Gentle attraction to cluster center
        const force = opts.clusterStrength * Math.min(distance / opts.clusterRadius, 1);
        pos.vx += (dx / distance) * force;
        pos.vy += (dy / distance) * force;
      }
    });

    // 5. Weak centering force (prevent drift)
    for (const pos of positions.values()) {
      const dx = centerX - pos.x;
      const dy = centerY - pos.y;

      pos.vx += dx * opts.centeringForce * 0.5; // Reduced since we have cluster forces
      pos.vy += dy * opts.centeringForce * 0.5;
    }

    // 6. Apply forces with damping and temperature-based scaling
    for (const pos of positions.values()) {
      // Apply temperature-based scaling (allows for settling)
      pos.vx *= opts.damping * temperature;
      pos.vy *= opts.damping * temperature;

      // Limit velocity to prevent explosion
      const maxVelocity = 10;
      const velocity = Math.sqrt(pos.vx * pos.vx + pos.vy * pos.vy);
      if (velocity > maxVelocity) {
        pos.vx = (pos.vx / velocity) * maxVelocity;
        pos.vy = (pos.vy / velocity) * maxVelocity;
      }

      pos.x += pos.vx;
      pos.y += pos.vy;

      // Keep nodes within bounds with soft constraints
      const margin = pos.nodeRadius + 30; // Extra space for labels
      if (pos.x < margin) {
        pos.x = margin;
        pos.vx = Math.abs(pos.vx) * 0.5; // Bounce back
      }
      if (pos.x > width - margin) {
        pos.x = width - margin;
        pos.vx = -Math.abs(pos.vx) * 0.5;
      }
      if (pos.y < margin) {
        pos.y = margin;
        pos.vy = Math.abs(pos.vy) * 0.5;
      }
      if (pos.y > height - margin) {
        pos.y = height - margin;
        pos.vy = -Math.abs(pos.vy) * 0.5;
      }
    }
  }

  // Final pass: ensure no overlaps remain
  const nodeIds = Array.from(positions.keys());
  for (let attempt = 0; attempt < 10; attempt++) {
    let hasOverlap = false;

    for (let j = 0; j < nodeIds.length; j++) {
      for (let k = j + 1; k < nodeIds.length; k++) {
        const nodeA = positions.get(nodeIds[j])!;
        const nodeB = positions.get(nodeIds[k])!;

        const dx = nodeB.x - nodeA.x;
        const dy = nodeB.y - nodeA.y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const minDistance = nodeA.nodeRadius + nodeB.nodeRadius + 20;

        if (distance < minDistance && distance > 0) {
          hasOverlap = true;

          // Direct position adjustment
          const overlap = minDistance - distance;
          const moveDistance = overlap / 2 + 5; // Extra padding

          const unitX = dx / distance;
          const unitY = dy / distance;

          nodeA.x -= unitX * moveDistance;
          nodeA.y -= unitY * moveDistance;
          nodeB.x += unitX * moveDistance;
          nodeB.y += unitY * moveDistance;

          // Keep within bounds
          const marginA = nodeA.nodeRadius + 30;
          const marginB = nodeB.nodeRadius + 30;

          nodeA.x = Math.max(marginA, Math.min(width - marginA, nodeA.x));
          nodeA.y = Math.max(marginA, Math.min(height - marginA, nodeA.y));
          nodeB.x = Math.max(marginB, Math.min(width - marginB, nodeB.x));
          nodeB.y = Math.max(marginB, Math.min(height - marginB, nodeB.y));
        }
      }
    }

    if (!hasOverlap) break;
  }

  // Return final positions
  return Array.from(positions.entries()).map(([id, pos]) => ({
    id,
    x: pos.x,
    y: pos.y,
  }));
}

/**
 * Simple circular layout for when there are no links
 */
export function calculateCircularLayout(
  nodes: UnifiedNode[],
  dimensions: GraphDimensions,
  options: LayoutOptions = {}
): NodePosition[] {
  const opts = { ...DEFAULT_OPTIONS, ...options };
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
 * Main layout function that chooses the appropriate algorithm
 */
export function calculateLayout(
  nodes: UnifiedNode[],
  links: UnifiedSearchLink[],
  dimensions: GraphDimensions,
  options: LayoutOptions = {}
): NodePosition[] {
  if (nodes.length === 0) return [];

  if (links.length === 0) {
    return calculateCircularLayout(nodes, dimensions, options);
  }

  return calculateForceDirectedLayout(nodes, links, dimensions, options);
}