/**
 * D3.js Live Force Layout
 *
 * Real-time D3 force simulation with animated updates
 */

import { UnifiedNode, UnifiedSearchLink } from "@/api/types/unified";

// Declare d3 as available globally from CDN
declare const d3: any;

// Consistent padding for all zoom operations
const ZOOM_PADDING = 25;

export interface NodePosition {
  id: string;
  x: number;
  y: number;
}

export interface GraphDimensions {
  width: number;
  height: number;
}

export interface D3LiveLayoutOptions {
  linkDistance?: number;
  linkStrength?: number;
  chargeStrength?: number;
  collisionRadius?: number;
  clusterStrength?: number;
  alphaDecay?: number;
  velocityDecay?: number;
  onTick?: (positions: NodePosition[]) => void;
  onEnd?: (positions: NodePosition[]) => void;
}

export class D3LiveSimulation {
  private simulation: any = null;
  private nodes: any[] = [];
  private links: any[] = [];
  private dimensions: GraphDimensions;
  private options: Required<Omit<D3LiveLayoutOptions, 'onTick' | 'onEnd'>>;
  private onTick?: (positions: NodePosition[]) => void;
  private onEnd?: (positions: NodePosition[]) => void;
  private clusterCenters = new Map<string, { x: number; y: number }>();
  private zoom: any = null;
  private svgElement: any = null;
  private tickCount: number = 0;

  constructor(
    nodes: UnifiedNode[],
    links: UnifiedSearchLink[],
    dimensions: GraphDimensions,
    options: D3LiveLayoutOptions = {}
  ) {
    this.dimensions = dimensions;
    this.onTick = options.onTick;
    this.onEnd = options.onEnd;

    this.options = {
      linkDistance: options.linkDistance || 200,
      linkStrength: options.linkStrength || 0.7,
      chargeStrength: options.chargeStrength || -800,
      collisionRadius: options.collisionRadius || 80,
      clusterStrength: options.clusterStrength || 0.03,
      alphaDecay: options.alphaDecay || 0.01,
      velocityDecay: options.velocityDecay || 0.7,
    };

    this.setupClusterCenters(nodes);
    this.prepareNodes(nodes, links);
    this.prepareLinks(links, nodes);
    this.createSimulation();
  }

  private setupClusterCenters(nodes: UnifiedNode[]) {
    const { width, height } = this.dimensions;
    const sourceTypes = [...new Set(nodes.map(node => node.source))];

    sourceTypes.forEach((source, index) => {
      const angle = (2 * Math.PI * index) / sourceTypes.length;
      const radius = Math.min(width, height) * 0.25;
      this.clusterCenters.set(source, {
        x: width / 2 + Math.cos(angle) * radius,
        y: height / 2 + Math.sin(angle) * radius,
      });
    });
  }

  private prepareNodes(nodes: UnifiedNode[], links: UnifiedSearchLink[]) {
    this.nodes = nodes.map(node => {
      const connectionCount = links.filter(link =>
        link.subject === node.id || link.object === node.id
      ).length;
      const confidenceScore = node.confidence_score || 0.5;
      const nodeRadius = 15 + Math.min(10, connectionCount * 2) + (confidenceScore * 5);
      const clusterCenter = this.clusterCenters.get(node.source) || {
        x: this.dimensions.width / 2,
        y: this.dimensions.height / 2
      };

      return {
        id: node.id,
        source: node.source,
        radius: nodeRadius,
        mass: 1 + confidenceScore + (connectionCount * 0.1),
        clusterX: clusterCenter.x,
        clusterY: clusterCenter.y,
        // Start near cluster center with some randomness
        x: clusterCenter.x + (Math.random() - 0.5) * 100,
        y: clusterCenter.y + (Math.random() - 0.5) * 100,
        vx: 0,
        vy: 0,
      };
    });
  }

  private prepareLinks(links: UnifiedSearchLink[], nodes: UnifiedNode[]) {
    const nodeIds = new Set(nodes.map(n => n.id));
    this.links = links
      .filter(link => nodeIds.has(link.subject) && nodeIds.has(link.object))
      .map(link => ({
        source: link.subject,
        target: link.object,
        weight: link.weight || 1,
      }));
  }

  private createSimulation() {
    const { width, height } = this.dimensions;

    this.simulation = d3.forceSimulation(this.nodes)
      .force("link", d3.forceLink(this.links)
        .id((d: any) => d.id)
        .distance(this.options.linkDistance)
        .strength(this.options.linkStrength)
      )
      .force("charge", d3.forceManyBody()
        .strength((d: any) => this.options.chargeStrength * (1 + d.mass * 0.3))
        .distanceMin(30)
        .distanceMax(400)
      )
      .force("collision", d3.forceCollide()
        .radius((d: any) => {
          // Dynamic radius based on node size plus padding for labels
          return d.radius + 30; // Base padding for text labels
        })
        .strength(1)
        .iterations(3)
      )
      .force("x", d3.forceX()
        .x((d: any) => d.clusterX)
        .strength(this.options.clusterStrength)
      )
      .force("y", d3.forceY()
        .y((d: any) => d.clusterY)
        .strength(this.options.clusterStrength)
      )
      .force("center", d3.forceCenter(width / 2, height / 2)
        .strength(0.03)
      )
      .alphaDecay(this.options.alphaDecay)
      .velocityDecay(this.options.velocityDecay)
      .on("tick", () => {
        const currentAlpha = this.simulation.alpha();
        this.tickCount++;

        // Stop simulation when energy drops to 15%
        if (currentAlpha <= 0.15) {
          this.simulation.stop();
          // Trigger end event manually
          const positions: NodePosition[] = this.nodes.map((node: any) => ({
            id: node.id,
            x: node.x,
            y: node.y,
          }));
          this.onEnd?.(positions);
          return;
        }

        // Throttle position updates for better performance
        if (currentAlpha > 0.1 || currentAlpha % 0.05 < 0.01) {
          const positions: NodePosition[] = this.nodes.map((node: any) => ({
            id: node.id,
            x: node.x,
            y: node.y,
          }));

          this.onTick?.(positions);

          // Continuously fit to bounds during simulation (throttled every 5 ticks)
          if (this.tickCount % 5 === 0) {
            this.zoomToFit(positions, ZOOM_PADDING, false);
          }
        }
      })
      .on("end", () => {
        // Final positions without constraints
        const positions: NodePosition[] = this.nodes.map((node: any) => ({
          id: node.id,
          x: node.x,
          y: node.y,
        }));

        this.onEnd?.(positions);
      });
  }

  public start() {
    if (this.simulation) {
      this.tickCount = 0;
      this.simulation.restart();
    }
  }

  public stop() {
    if (this.simulation) {
      this.simulation.stop();
    }
  }

  public pause() {
    if (this.simulation) {
      this.simulation.stop();
    }
  }

  public resume() {
    if (this.simulation) {
      this.simulation.restart();
    }
  }

  public restart() {
    if (this.simulation) {
      this.tickCount = 0;
      this.simulation.alpha(1).restart();
    }
  }

  public getAlpha(): number {
    return this.simulation ? this.simulation.alpha() : 0;
  }

  public isRunning(): boolean {
    return this.simulation && this.simulation.alpha() > 0.15;
  }

  public destroy() {
    if (this.simulation) {
      this.simulation.stop();
      this.simulation = null;
    }
  }

  public updateDimensions(dimensions: GraphDimensions) {
    this.dimensions = dimensions;
    if (this.simulation) {
      this.simulation.force("center", d3.forceCenter(dimensions.width / 2, dimensions.height / 2));
    }
  }

  public enableZoom(svgElement: any, containerGroup: any) {
    if (typeof d3 === 'undefined' || !d3.zoom) {
      console.warn('D3 is not loaded or zoom function not available');
      return;
    }

    this.svgElement = svgElement;

    // Create D3 selection for the container group
    const containerSelection = d3.select(containerGroup);

    this.zoom = d3.zoom()
      .scaleExtent([0.1, 10])
      .on("zoom", (event: any) => {
        containerSelection.attr("transform", event.transform);
      });

    try {
      const svgSelection = d3.select(svgElement);
      svgSelection.call(this.zoom);
      console.log('Zoom enabled successfully');
    } catch (error) {
      console.error('Failed to enable zoom:', error);
    }
  }

  public resetZoom() {
    if (!this.zoom || !this.svgElement) {
      console.warn('Reset zoom failed: missing zoom or svgElement');
      return;
    }

    if (typeof d3 === 'undefined' || !d3.zoomIdentity) {
      console.warn('D3 is not loaded or zoomIdentity not available');
      return;
    }

    try {
      d3.select(this.svgElement)
        .transition()
        .duration(750)
        .call(this.zoom.transform, d3.zoomIdentity);
      console.log('Reset zoom completed');
    } catch (error) {
      console.error('Failed to reset zoom:', error);
    }
  }

  public zoomToFit(nodePositions: NodePosition[], padding: number = ZOOM_PADDING, animate: boolean = true) {
    if (!this.zoom || !this.svgElement || nodePositions.length === 0) {
      console.warn('ZoomToFit failed: missing zoom, svgElement, or no positions');
      return;
    }

    if (typeof d3 === 'undefined' || !d3.zoomIdentity) {
      console.warn('D3 is not loaded or zoomIdentity not available');
      return;
    }

    const minX = Math.min(...nodePositions.map(pos => pos.x)) - padding;
    const maxX = Math.max(...nodePositions.map(pos => pos.x)) + padding;
    const minY = Math.min(...nodePositions.map(pos => pos.y)) - padding;
    const maxY = Math.max(...nodePositions.map(pos => pos.y)) + padding;

    const contentWidth = maxX - minX;
    const contentHeight = maxY - minY;

    // Avoid division by zero
    if (contentWidth === 0 || contentHeight === 0) return;

    const { width: svgWidth, height: svgHeight } = this.dimensions;

    // Calculate scale to fit content with some padding
    const scaleX = svgWidth / contentWidth;
    const scaleY = svgHeight / contentHeight;
    const scale = Math.min(scaleX, scaleY) * 0.85; // 85% to leave some padding

    // Calculate translation to center the content
    const contentCenterX = (minX + maxX) / 2;
    const contentCenterY = (minY + maxY) / 2;
    const translateX = svgWidth / 2 - contentCenterX * scale;
    const translateY = svgHeight / 2 - contentCenterY * scale;

    const transform = d3.zoomIdentity.translate(translateX, translateY).scale(scale);

    try {
      if (animate) {
        d3.select(this.svgElement)
          .transition()
          .duration(750)
          .call(this.zoom.transform, transform);
      } else {
        d3.select(this.svgElement).call(this.zoom.transform, transform);
      }
      console.log('ZoomToFit completed successfully');
    } catch (error) {
      console.error('Failed to apply zoom transform:', error);
    }
  }
}