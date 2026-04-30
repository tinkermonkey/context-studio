import React, { useCallback, useMemo, useRef, useState } from "react";
import {
  useMeasurementSvg,
  useMeasurementHtml,
} from "@/components/graphs/tree_chart/useMeasurementElement";

import {} from "@/components/graphs/tree_chart/tree_chart_utils";
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { NlpConceptChartLink } from "./NlpConceptChartLink";
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { NlpConceptChartNode } from "./NlpConceptChartNode";

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
  wordnet?: {
    synsets: WordNetSynset[];
  };
  relationsByType?: Record<string, ConceptRelation[]>;
  inputTerm: string;
}

interface NlpConceptChartProps {
  data?: NlpData;
  config?: LayoutConfig;
  width?: number;
  selectedNodeIds?: Set<string>;
  onNodeClick?: (nodeId: string) => void;
}

interface LayoutConfig {
  margins: {
    top: number;
    right: number;
    bottom: number;
    left: number;
  };
  padding: number;
  columnWidth: number;
  relationHeight: number;
  relationMargin: number;
  arrowMarkerSize: number;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const STYLES = {
  chartPadding: 20,
  relationMargin: 30,
  relationHeight: 60,
  relationColumnWidth: 300,
  arrowMarkerSize: 4,
};

const NlpConceptChart: React.FC<NlpConceptChartProps> = ({
  data,
  width: providedWidth,
  onNodeClick,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth] = useState<number>(providedWidth || 1000);

  // Initialize measurement utilities
  useMeasurementSvg();
  useMeasurementHtml();

  // Handle node click - simply bubble up the node ID

  const _handleNodeClick = useCallback(
    (node: any) => {
      onNodeClick?.(node.id);
    },
    [onNodeClick],
  );

  // Process the data to extract and organize the elements
  const processedData = useMemo(() => {
    if (!data) {
      return null;
    }

    // Extract WordNet synsets (senses)
    const senses = data.wordnet?.synsets || [];

    // Extract and organize relations by type
    const relationsByType: Record<string, ConceptRelation[]> = {};
    if (data.relationsByType) {
      Object.entries(data.relationsByType).forEach(([type, relations]) => {
        relationsByType[type] = relations;
      });
    }

    return {
      inputTerm: data.inputTerm,
      senses,
      relationsByType,
    };
  }, [data]);

  // Render the chart
  return (
    <div
      ref={containerRef}
      className="h-auto w-full rounded-lg border border-gray-200 bg-white p-4"
    >
      <svg
        width={containerWidth}
        height={600}
        className="w-full"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Render definitions/senses */}
        {processedData?.senses.map((sense) => (
          <g key={sense.name}>
            <rect x="0" y="0" width="150" height="60" fill="lightblue" />
            <text x="10" y="20">
              {sense.name}
            </text>
          </g>
        ))}

        {/* Render relations */}
        {Object.entries(processedData?.relationsByType || {}).map(
          ([relationType, relations]) => (
            <g key={relationType}>
              {relations.map((relation) => (
                <g key={relation.text}>
                  <rect
                    x="200"
                    y="0"
                    width="150"
                    height="60"
                    fill="lightyellow"
                  />
                  <text x="210" y="20">
                    {relation.text}
                  </text>
                </g>
              ))}
            </g>
          ),
        )}
      </svg>
    </div>
  );
};

export default NlpConceptChart;
