import React, { useCallback, useMemo, useEffect, useRef, useState } from "react";
import { useMeasurementSvg, useMeasurementHtml } from "@/components/graphs/hierarchy/useMeasurementElement";
import { 
  measureSvgTextWidth, 
  measureHtmlTextHeight, 
  TextMeasurementOptions 
} from "@/components/graphs/hierarchy/tree_chart_utils";
import NlpLinkWithPredicate from "./NlpLinkWithPredicate";

// Type definitions for the NLP data structure
interface ConceptRelation {
  subject: {
    id: string;
    label: string;
    language: string;
    term: string;
  };
  object: {
    id: string;
    label: string;
    language: string;
    term: string;
  };
  relation: string;
  text: string;
  weight: number;
}

interface WordNetSynset {
  name: string;
  definition: string;
  lemmas: string[];
  pos: string;
  offset: number;
  domain: string;
}

interface NlpData {
  text: string;
  lemma: string;
  pos: string;
  concepcy: {
    related_terms: ConceptRelation[];
  };
  wordnet: {
    synsets: WordNetSynset[];
    definitions: string[];
  };
}

// Configuration for which relations to show and how many of each
interface ChartConfig {
  [relation: string]: number;
}

interface NlpConceptChartProps {
  data: NlpData;
  config?: ChartConfig;
  width?: number;
  height?: number;
}

// Default configuration - matches the example SVG
const DEFAULT_CONFIG: ChartConfig = {
  "RelatedTo": 2,
  "IsA": 4,
  "HasA": 2,
};

// Styling constants
const STYLES = {
  // Colors matching the example SVG
  inputNode: {
    fill: "#afe9af",
    stroke: "#000000",
    rx: 14,
  },
  senseNode: {
    fill: "#aaeeff",
    stroke: "none",
    rx: 14,
  },
  definitionNode: {
    fill: "#e5e5e5",
    stroke: "none",
    rx: 14,
  },
  relationNode: {
    fill: "#e6e6e6",
    stroke: "none",
    rx: 14,
  },
  // Text styles
  inputText: {
    fontSize: "12px",
    fontFamily: "sans-serif",
    fontWeight: "normal",
  },
  senseText: {
    fontSize: "12px",
    fontFamily: "sans-serif",
    fontWeight: "bold",
  },
  definitionText: {
    fontSize: "12px",
    fontFamily: "sans-serif",
    fontWeight: "normal",
  },
  relationText: {
    fontSize: "12px",
    fontFamily: "sans-serif",
    fontWeight: "normal",
  },
  edgeText: {
    fontSize: "12px",
    fontFamily: "sans-serif",
    fontWeight: "normal",
  },
  // Layout constants
  nodeHeight: 44,
  nodePadding: 10,
  nodeMargin: 10,
  relationMargin: 15,
  verticalSpacing: 50,
  horizontalSpacing: 100,
  arrowMarkerSize: 4,
};

const NlpConceptChart: React.FC<NlpConceptChartProps> = ({ 
  data, 
  config = DEFAULT_CONFIG,
  width: providedWidth,
  height: providedHeight 
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(providedWidth || 1000);

  // Initialize measurement utilities
  useMeasurementSvg();
  useMeasurementHtml();

  // Measure container width on mount and resize
  useEffect(() => {
    if (providedWidth) return; // Skip if width is provided

    const measureWidth = () => {
      if (containerRef.current) {
        const width = containerRef.current.clientWidth;
        setContainerWidth(width);
      }
    };

    measureWidth();

    const resizeObserver = new ResizeObserver(measureWidth);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      resizeObserver.disconnect();
    };
  }, [providedWidth]);

  // Process the data to extract and organize the elements
  const processedData = useMemo(() => {
    if (!data) {
      return null;
    }

    // Extract WordNet synsets (senses)
    const senses = data.wordnet?.synsets || [];
    
    // Group relations by type and take the configured number of each
    const relationsByType: { [key: string]: ConceptRelation[] } = {};
    
    const relatedTerms = data.concepcy?.related_terms || [];
    
    relatedTerms.forEach(relation => {
      if (!relationsByType[relation.relation]) {
        relationsByType[relation.relation] = [];
      }
      const maxCount = config[relation.relation] || 0;
      if (relationsByType[relation.relation].length < maxCount) {
        relationsByType[relation.relation].push(relation);
      }
    });

    return {
      inputTerm: data.lemma,
      senses,
      relationsByType,
    };
  }, [data, config]);

  // Calculate layout and dimensions
  const layout = useMemo(() => {
    if (!processedData) return { nodes: [], edges: [], width: 800, height: 600 };

    const textOptions: TextMeasurementOptions = {
      fontSize: STYLES.inputText.fontSize,
      fontFamily: STYLES.inputText.fontFamily,
    };

    const nodes: any[] = [];
    const edges: any[] = [];

    // Collect sense links for the sub-component
    const senseLinks: Array<{
      startPoint: { x: number; y: number };
      label: string;
      endPoints: Array<{ x: number; y: number }>;
    }> = [];
    
    // Collect predicate links for the new sub-component
    const predicateLinks: Array<{
      startPoint: { x: number; y: number };
      label: string;
      endPoints: Array<{ x: number; y: number }>;
    }> = [];

    let currentY = 50;
    const leftColumnX = 50;
    const middleColumnX = 350;
    const rightColumnX = 500;
    const maxWidth = containerWidth - 50;

    // Input node (left side)
    const inputNodeWidth = Math.max(
      measureSvgTextWidth(processedData.inputTerm, textOptions) + 40,
      130
    );
    nodes.push({
      id: "input",
      type: "input",
      x: leftColumnX,
      y: currentY,
      width: inputNodeWidth,
      height: STYLES.nodeHeight,
      text: processedData.inputTerm,
    });

    // WordNet senses (middle column) - combined sense metadata and definition
    let senseY = currentY;
    const senseNodes: any[] = [];
    
    processedData.senses.forEach((sense, index) => {
      const senseMetadataLabel = `${sense.name} (${sense.pos}) - ${sense.domain}`;
      
      // Calculate width based on the longer of the two lines
      const labelWidth = measureSvgTextWidth(senseMetadataLabel, { ...textOptions, fontWeight: "bold" });
      const maxDefWidth = 500; // Maximum width for definition text
      const senseWidth = Math.min(
        Math.max(labelWidth + 40, maxDefWidth),
        maxWidth - middleColumnX - 50
      );
      
      // Calculate height needed for both lines with proper spacing
      const lineHeight = 16; // Approximate line height
      const padding = 20;
      const senseHeight = Math.max(
        measureHtmlTextHeight(sense.definition, senseWidth - 20, textOptions) + lineHeight + padding,
        STYLES.nodeHeight * 1.5 // Minimum height for two lines
      );
      
      const senseNode = {
        id: `sense-${index}`,
        type: "sense-combined",
        x: middleColumnX,
        y: senseY,
        width: senseWidth,
        height: senseHeight,
        senseLabel: senseMetadataLabel,
        definition: sense.definition,
        isWrapped: true,
      };
      
      nodes.push(senseNode);
      senseNodes.push(senseNode);
      
      senseY += senseHeight + 25;
    });

    // Create sense links data for the sub-component
    if (senseNodes.length > 0) {
      const startPoint = { 
        x: leftColumnX + inputNodeWidth, 
        y: currentY + STYLES.nodeHeight / 2 
      };
      
      const endPoints = senseNodes.map(node => ({
        x: node.x,
        y: node.y + node.height / 2
      }));
      
      senseLinks.push({
        startPoint,
        label: "has sense",
        endPoints
      });
    }

    // Relation nodes (aligned with definitions, branching off from input)
    let relationStartY = Math.max(senseY + 20, currentY + 100);
    let maxRelationY = relationStartY;
    
    // Use the same X position as the sense/definition boxes for alignment
    const relationColumnX = middleColumnX;
    
    Object.entries(processedData.relationsByType).forEach(([relationType, relations], typeIndex) => {
      let relationY = relationStartY + STYLES.relationMargin;
      
      const relationNodes: any[] = [];
      const endPoints: Array<{ x: number; y: number }> = [];
      
      relations.forEach((relation, index) => {
        const relationText = relation.object.label;
        const relationWidth = Math.max(
          measureSvgTextWidth(relationText, textOptions) + 50, // Extra padding for left alignment
          130
        );
        
        const relationNode = {
          id: `relation-${relationType}-${index}`,
          type: "relation",
          x: relationColumnX,
          y: relationY,
          width: relationWidth,
          height: STYLES.nodeHeight,
          text: relationText,
          relation: relationType,
        };
        
        nodes.push(relationNode);
        relationNodes.push(relationNode);
        
        // Collect end point for this relation (left edge, vertical center)
        endPoints.push({
          x: relationColumnX,
          y: relationY + STYLES.nodeHeight / 2
        });
        
        relationY += STYLES.nodeHeight + STYLES.nodeMargin;
        maxRelationY = Math.max(maxRelationY, relationY);
      });
      
      // Create predicate link data for this relation type
      if (relationNodes.length > 0) {
        const edgeLabel = relationType === "RelatedTo" ? "is related to" :
                         relationType === "IsA" ? "is a" :
                         relationType === "HasA" ? "has" :
                         relationType.toLowerCase();
        
        const startPoint = { 
          x: leftColumnX + inputNodeWidth / 2,
          y: currentY + STYLES.nodeHeight
        };
        
        predicateLinks.push({
          startPoint,
          label: edgeLabel,
          endPoints
        });
      }

      // For the predicateLinks, once they've all been added go back and space them out evenly across the bottom of the input node
      const predicateLinkCount = predicateLinks.length;
      if (predicateLinkCount > 0) {
        const xSpacing = inputNodeWidth / (predicateLinkCount + 1);
        predicateLinks.forEach((link, index) => {
          link.startPoint.x = leftColumnX + inputNodeWidth - xSpacing * (index + 1);
        });
      }

      // Update starting position for next relation type
      relationStartY = relationY + 10; // Small gap between relation types
    });

    const totalWidth = Math.max(relationColumnX + 350, maxWidth); // Ensure enough space for relation nodes
    const totalHeight = Math.max(maxRelationY, senseY) + 50;

    return {
      nodes,
      edges,
      senseLinks,
      predicateLinks,
      width: totalWidth,
      height: totalHeight,
    };
  }, [processedData, containerWidth]);

  // Helper function to create curved path
  const createCurvedPath = useCallback((from: { x: number; y: number }, to: { x: number; y: number }) => {
    // Create a curve that starts vertically down and then curves horizontally to the target
    const deltaY = to.y - from.y;
    const midY = from.y + Math.max(deltaY * 0.6, 30);
    
    return `M ${from.x} ${from.y} 
            C ${from.x} ${midY}, ${to.x - 50} ${midY}, ${to.x} ${to.y}`;
  }, []);

  // Helper function to create straight path
  const createStraightPath = useCallback((from: { x: number; y: number }, to: { x: number; y: number }) => {
    return `M ${from.x} ${from.y} L ${to.x} ${to.y}`;
  }, []);

  if (!processedData) {
    return (
      <div className="p-4 text-center text-gray-500 border border-gray-200 rounded">
        <p>No concept data available</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full">
      <svg
        width={layout.width}
        height={layout.height}
        className="border border-gray-200"
      >
        {/* Define arrow marker */}
        <defs>
          <marker
            id="arrowhead"
            markerWidth="10"
            markerHeight="7"
            refX="9"
            refY="3.5"
            orient="auto"
          >
            <polygon
              points="0 0, 10 3.5, 0 7"
              fill="#000"
            />
          </marker>
        </defs>

        {/* Render sense links using the sub-component */}
        {layout.senseLinks?.map((link, index) => (
          <NlpLinkWithPredicate
            key={`sense-link-${index}`}
            startPoint={link.startPoint}
            label={link.label}
            endPoints={link.endPoints}
            fontSize={STYLES.edgeText.fontSize}
            fontFamily={STYLES.edgeText.fontFamily}
          />
        ))}

        {/* Render predicate links using the sub-component */}
        {layout.predicateLinks?.map((link, index) => (
          <NlpLinkWithPredicate
            key={`predicate-link-${index}`}
            startPoint={link.startPoint}
            label={link.label}
            endPoints={link.endPoints}
            fontSize={STYLES.edgeText.fontSize}
            fontFamily={STYLES.edgeText.fontFamily}
          />
        ))}

        {/* Render nodes */}
        {layout.nodes.map((node) => {
          const nodeStyle = node.type === "input" ? STYLES.inputNode :
                           node.type === "sense-combined" ? STYLES.senseNode :
                           node.type === "sense" ? STYLES.senseNode :
                           node.type === "definition" ? STYLES.definitionNode :
                           STYLES.relationNode;
          
          const textStyle = node.type === "input" ? STYLES.inputText :
                           node.type === "sense-combined" ? STYLES.senseText :
                           node.type === "sense" ? STYLES.senseText :
                           node.type === "definition" ? STYLES.definitionText :
                           STYLES.relationText;

          return (
            <g key={node.id}>
              <rect
                x={node.x}
                y={node.y}
                width={node.width}
                height={node.height}
                fill={nodeStyle.fill}
                stroke={nodeStyle.stroke}
                rx={nodeStyle.rx}
              />
              {node.type === "sense-combined" ? (
                // Special handling for combined sense + definition boxes
                <foreignObject
                  x={node.x + 10}
                  y={node.y + 8}
                  width={node.width - 20}
                  height={node.height - 16}
                >
                  <div
                    style={{
                      fontSize: textStyle.fontSize,
                      fontFamily: textStyle.fontFamily,
                      color: "#000",
                      lineHeight: "1.3",
                      textAlign: "left",
                    }}
                  >
                    <div style={{ fontWeight: "bold", marginBottom: "4px" }}>
                      {node.senseLabel}
                    </div>
                    <div style={{ fontWeight: "normal" }}>
                      {node.definition}
                    </div>
                  </div>
                </foreignObject>
              ) : node.isWrapped ? (
                // For other wrapped text (like standalone definitions), use foreignObject
                <foreignObject
                  x={node.x + 10}
                  y={node.y + 5}
                  width={node.width - 20}
                  height={node.height - 10}
                >
                  <div
                    style={{
                      fontSize: textStyle.fontSize,
                      fontFamily: textStyle.fontFamily,
                      fontWeight: textStyle.fontWeight,
                      color: "#000",
                      padding: "5px",
                      lineHeight: "1.2",
                      wordWrap: "break-word",
                      overflow: "hidden",
                      textAlign: "left",
                    }}
                  >
                    {node.text}
                  </div>
                </foreignObject>
              ) : (
                // For simple text nodes, center for input, left-align for others
                <text
                  x={node.type === "input" ? node.x + node.width / 2 : node.x + 15}
                  y={node.y + node.height / 2 + 4}
                  textAnchor={node.type === "input" ? "middle" : "start"}
                  fontSize={textStyle.fontSize}
                  fontFamily={textStyle.fontFamily}
                  fontWeight={textStyle.fontWeight}
                  fill="#000"
                >
                  {node.text}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
};

export default NlpConceptChart;
