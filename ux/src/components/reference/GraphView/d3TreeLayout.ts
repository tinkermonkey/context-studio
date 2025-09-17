/**
 * D3.js Force-Directed Tree Layout with Predicate Grouping
 *
 * Hierarchy-based D3 force simulation:
 * - Nodes serve as the backbone of the graph
 * - Subject-predicate-object links are grouped by predicate for each subject
 * - Fake predicate nodes are created to visualize grouped relationships
 * - Uses d3.hierarchy concepts for cleaner tree structure
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

export interface D3TreeLayoutOptions {
  linkDistance?: number;
  linkStrength?: number;
  chargeStrength?: number;
  collisionRadius?: number;
  alphaDecay?: number;
  velocityDecay?: number;
  onTick?: (positions: NodePosition[]) => void;
  onEnd?: (positions: NodePosition[]) => void;
}

export interface HierarchyNode {
  id: string;
  type: "data" | "predicate";
  source?: string;
  radius: number;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
  // For predicate nodes
  predicate?: string;
  subjectId?: string;
  // For data nodes
  originalNode?: UnifiedNode;
  // Hierarchy properties
  children?: HierarchyNode[];
  parent?: HierarchyNode;
  depth?: number;
}

export interface HierarchyLink {
  source: HierarchyNode;
  target: HierarchyNode;
  type: "subject-predicate" | "predicate-object";
  weight: number;
}

export class D3TreeSimulation {
  private simulation: any = null;
  private nodes: HierarchyNode[] = [];
  private links: HierarchyLink[] = [];
  private dimensions: GraphDimensions;
  private options: Required<Omit<D3TreeLayoutOptions, "onTick" | "onEnd">>;
  private onTick?: (positions: NodePosition[]) => void;
  private onEnd?: (positions: NodePosition[]) => void;
  private zoom: any = null;
  private svgElement: any = null;
  private tickCount: number = 0;
  private hierarchyRoot: any = null;
  private predicateNodeMap = new Map<string, string>(); // key: subjectId-predicate, value: predicateNodeId

  constructor(
    nodes: UnifiedNode[],
    links: UnifiedSearchLink[],
    dimensions: GraphDimensions,
    options: D3TreeLayoutOptions = {},
  ) {
    this.dimensions = dimensions;
    this.onTick = options.onTick;
    this.onEnd = options.onEnd;

    this.options = {
      linkDistance: options.linkDistance || 80,
      linkStrength: options.linkStrength || 1,
      chargeStrength: options.chargeStrength || -300,
      collisionRadius: options.collisionRadius || 50,
      alphaDecay: options.alphaDecay || 0.02,
      velocityDecay: options.velocityDecay || 0.4,
    };

    this.buildTreeStructure(nodes, links);
    this.createSimulation();
  }

  private buildTreeStructure(nodes: UnifiedNode[], links: UnifiedSearchLink[]) {
    // Step 1: Create a hierarchy structure
    const nodeMap = new Map<string, HierarchyNode>();
    const hierarchyLinks: HierarchyLink[] = [];

    // Create data nodes
    nodes.forEach((node) => {
      nodeMap.set(node.id, {
        id: node.id,
        type: "data",
        source: node.source,
        radius: 20,
        originalNode: node,
        children: [],
      });
    });

    // Group links by subject-predicate pairs
    const subjectPredicateGroups = new Map<string, UnifiedSearchLink[]>();
    links.forEach((link) => {
      const key = `${link.subject}|||${link.predicate}`; // Use ||| as separator to avoid conflicts
      if (!subjectPredicateGroups.has(key)) {
        subjectPredicateGroups.set(key, []);
      }
      subjectPredicateGroups.get(key)!.push(link);
    });

    // Group links by predicate-object pairs for potential future use
    const predicateObjectGroups = new Map<string, UnifiedSearchLink[]>();
    links.forEach((link) => {
      const key = `${link.predicate}|||${link.object}`;
      if (!predicateObjectGroups.has(key)) {
        predicateObjectGroups.set(key, []);
      }
      predicateObjectGroups.get(key)!.push(link);
    });

    // Create predicate nodes and hierarchy relationships for predicate-object groups
    predicateObjectGroups.forEach((groupLinks, key) => {
      const [predicate, objectId] = key.split("|||");
      const objectNode = nodeMap.get(objectId);

      if (!objectNode) return;

      // Create predicate node if it doesn't already exist
      const existingPredicateNodeId = this.predicateNodeMap.get(key);
      let predicateNode: HierarchyNode;

      if (existingPredicateNodeId) {
        predicateNode = nodeMap.get(existingPredicateNodeId)!;
      } else {
        const predicateNodeId = `pred-${key}`;
        predicateNode = {
          id: predicateNodeId,
          type: "predicate",
          radius: 8,
          predicate,
          subjectId: groupLinks[0].subject,
          parent: nodeMap.get(groupLinks[0].subject),
          children: [],
          depth: 1,
        };
        nodeMap.set(predicateNodeId, predicateNode);
        this.predicateNodeMap.set(key, predicateNodeId);
        nodeMap.get(groupLinks[0].subject)?.children!.push(predicateNode);

        // Create hierarchy link from predicate node to object
        hierarchyLinks.push({
          source: predicateNode,
          target: objectNode,
          type: "predicate-object",
          weight: 1,
        });
      }

      // Link predicate to all objects
      groupLinks.forEach((link) => {
        const subjectNode = nodeMap.get(link.subject);
        if (predicateNode && subjectNode) {
          const subjectPredicateKey = `${subjectNode.id}|||${link.predicate}`;
          this.predicateNodeMap.set(subjectPredicateKey, predicateNode.id);
          hierarchyLinks.push({
            source: subjectNode,
            target: predicateNode,
            type: "subject-predicate",
            weight: link.weight || 1,
          });
        }
      });
    });

    // Create predicate nodes and hierarchy relationships for subject-predicate groups
    subjectPredicateGroups.forEach((groupLinks, key) => {
      const [subjectId, predicate] = key.split("|||");
      const subjectNode = nodeMap.get(subjectId);

      if (!subjectNode) return;

      // Create predicate node if it doesn't already exist
      const existingPredicateNodeId = this.predicateNodeMap.get(key);
      let predicateNode: HierarchyNode;

      if (existingPredicateNodeId) {
        predicateNode = nodeMap.get(existingPredicateNodeId)!;
      } else {
        const subjectPredicateNodeId = `pred-${key}`;
        const predicateNode: HierarchyNode = {
          id: subjectPredicateNodeId,
          type: "predicate",
          radius: 8,
          predicate,
          subjectId,
          parent: subjectNode,
          children: [],
          depth: 1,
        };

        nodeMap.set(subjectPredicateNodeId, predicateNode);
        this.predicateNodeMap.set(key, subjectPredicateNodeId);
        subjectNode.children!.push(predicateNode);

        // Create hierarchy link from subject to predicate
        hierarchyLinks.push({
          source: subjectNode,
          target: predicateNode,
          type: "subject-predicate",
          weight: 1,
        });

        // Link predicate to all objects
        groupLinks.forEach((link) => {
          const objectNode = nodeMap.get(link.object);
          if (objectNode) {
            hierarchyLinks.push({
              source: predicateNode,
              target: objectNode,
              type: "predicate-object",
              weight: link.weight || 1,
            });
          }
        });
      }
    });

    // Finalize nodes and links
    this.nodes = Array.from(nodeMap.values());
    this.links = hierarchyLinks;
  }

  private createSimulation() {
    const { width, height } = this.dimensions;

    // Initialize node positions
    this.nodes.forEach((node) => {
      if (!node.x && !node.y) {
        node.x = width / 2 + (Math.random() - 0.5) * 100;
        node.y = height / 2 + (Math.random() - 0.5) * 100;
      }
    });

    this.simulation = d3
      .forceSimulation(this.nodes)
      .force(
        "link",
        d3
          .forceLink(this.links)
          .id((d: any) => d.id)
          .distance(this.options.linkDistance)
          .strength(this.options.linkStrength),
      )
      .force("charge", d3.forceManyBody().strength(this.options.chargeStrength))
      .force(
        "collision",
        d3
          .forceCollide()
          .radius((d: any) => d.radius + 10)
          .strength(0.7),
      )
      .force("x", d3.forceX(width / 2).strength(0.1))
      .force("y", d3.forceY(height / 2).strength(0.1))
      .alphaDecay(this.options.alphaDecay)
      .velocityDecay(this.options.velocityDecay)
      .on("tick", () => {
        const currentAlpha = this.simulation.alpha();
        this.tickCount++;

        // Stop simulation when energy drops to 5%
        if (currentAlpha <= 0.05) {
          this.simulation.stop();
          const positions: NodePosition[] = this.nodes.map(
            (node: HierarchyNode) => ({
              id: node.id,
              x: node.x || 0,
              y: node.y || 0,
            }),
          );
          this.onEnd?.(positions);
          return;
        }

        // Throttle position updates for better performance
        if (currentAlpha > 0.03 || this.tickCount % 2 === 0) {
          const positions: NodePosition[] = this.nodes.map(
            (node: HierarchyNode) => ({
              id: node.id,
              x: node.x || 0,
              y: node.y || 0,
            }),
          );

          this.onTick?.(positions);

          // Continuously fit to bounds during simulation (throttled every 10 ticks)
          if (this.tickCount % 10 === 0) {
            this.zoomToFit(positions, ZOOM_PADDING, false);
          }
        }
      })
      .on("end", () => {
        const positions: NodePosition[] = this.nodes.map(
          (node: HierarchyNode) => ({
            id: node.id,
            x: node.x || 0,
            y: node.y || 0,
          }),
        );

        this.onEnd?.(positions);
      });
  }

  // Get all nodes including predicate nodes for rendering
  public getAllNodes(): HierarchyNode[] {
    return this.nodes;
  }

  // Get all tree links for rendering
  public getAllLinks(): HierarchyLink[] {
    return this.links;
  }

  // Get predicate node for a subject-predicate pair
  public getPredicateNode(
    subjectId: string,
    predicate: string,
  ): HierarchyNode | undefined {
    const key = `${subjectId}|||${predicate}`;
    const predicateNodeId = this.predicateNodeMap.get(key);
    return predicateNodeId
      ? this.nodes.find((n) => n.id === predicateNodeId)
      : undefined;
  }

  // Get only data nodes (excludes predicate nodes)
  public getDataNodes(): HierarchyNode[] {
    return this.nodes.filter((node) => node.type === "data");
  }

  // Get only predicate nodes
  public getPredicateNodes(): HierarchyNode[] {
    return this.nodes.filter((node) => node.type === "predicate");
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
    return this.simulation && this.simulation.alpha() > 0.05;
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
      this.simulation.force(
        "center",
        d3.forceCenter(dimensions.width / 2, dimensions.height / 2),
      );
    }
  }

  public enableZoom(svgElement: any, containerGroup: any) {
    if (typeof d3 === "undefined" || !d3.zoom) {
      console.warn("D3 is not loaded or zoom function not available");
      return;
    }

    this.svgElement = svgElement;

    const containerSelection = d3.select(containerGroup);

    this.zoom = d3
      .zoom()
      .scaleExtent([0.1, 10])
      .on("zoom", (event: any) => {
        containerSelection.attr("transform", event.transform);
      });

    try {
      const svgSelection = d3.select(svgElement);
      svgSelection.call(this.zoom);
      console.log("Zoom enabled successfully");
    } catch (error) {
      console.error("Failed to enable zoom:", error);
    }
  }

  public resetZoom() {
    if (!this.zoom || !this.svgElement) {
      console.warn("Reset zoom failed: missing zoom or svgElement");
      return;
    }

    if (typeof d3 === "undefined" || !d3.zoomIdentity) {
      console.warn("D3 is not loaded or zoomIdentity not available");
      return;
    }

    try {
      d3.select(this.svgElement)
        .transition()
        .duration(750)
        .call(this.zoom.transform, d3.zoomIdentity);
      console.log("Reset zoom completed");
    } catch (error) {
      console.error("Failed to reset zoom:", error);
    }
  }

  public zoomToFit(
    nodePositions: NodePosition[],
    padding: number = ZOOM_PADDING,
    animate: boolean = true,
  ) {
    if (!this.zoom || !this.svgElement || nodePositions.length === 0) {
      console.warn(
        "ZoomToFit failed: missing zoom, svgElement, or no positions",
      );
      return;
    }

    if (typeof d3 === "undefined" || !d3.zoomIdentity) {
      console.warn("D3 is not loaded or zoomIdentity not available");
      return;
    }

    const minX = Math.min(...nodePositions.map((pos) => pos.x)) - padding;
    const maxX = Math.max(...nodePositions.map((pos) => pos.x)) + padding;
    const minY = Math.min(...nodePositions.map((pos) => pos.y)) - padding;
    const maxY = Math.max(...nodePositions.map((pos) => pos.y)) + padding;

    const contentWidth = maxX - minX;
    const contentHeight = maxY - minY;

    if (contentWidth === 0 || contentHeight === 0) return;

    const { width: svgWidth, height: svgHeight } = this.dimensions;

    const scaleX = svgWidth / contentWidth;
    const scaleY = svgHeight / contentHeight;
    const scale = Math.min(scaleX, scaleY) * 0.85;

    const contentCenterX = (minX + maxX) / 2;
    const contentCenterY = (minY + maxY) / 2;
    const translateX = svgWidth / 2 - contentCenterX * scale;
    const translateY = svgHeight / 2 - contentCenterY * scale;

    const transform = d3.zoomIdentity
      .translate(translateX, translateY)
      .scale(scale);

    try {
      if (animate) {
        d3.select(this.svgElement)
          .transition()
          .duration(750)
          .call(this.zoom.transform, transform);
      } else {
        d3.select(this.svgElement).call(this.zoom.transform, transform);
      }
      console.log("ZoomToFit completed successfully");
    } catch (error) {
      console.error("Failed to apply zoom transform:", error);
    }
  }
}
