import React, { useState, useRef } from "react";

interface NodeShape {
  id: string;
  type: string;
  x: number;
  y: number;
  width: number;
  height: number;
  text?: string;
  senseLabel?: string;
  definition?: string;
  isWrapped?: boolean;
}

interface Props {
  node: NodeShape;
  nodeStyle: {
    fill: string;
    stroke: string;
    rx: number;
    lineHeight?: number;
  };
  textStyle: {
    fontSize: string;
    fontFamily: string;
    fontWeight: string;
  };
  onClick?: (node: NodeShape) => void;
  selected?: boolean;
}

export const NlpConceptChartNode: React.FC<Props> = ({ 
  node, 
  nodeStyle,
  textStyle,
  onClick, 
  selected, 
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const foreignObjectRef = useRef<SVGForeignObjectElement>(null);

  // Debug logging to see when this component re-renders
  React.useEffect(() => {
    //console.log(`Node ${node.id} re-rendered, selected: ${selected}, width: ${node.width}, height: ${node.height}`);
  }, [selected, node]);

  return (
    <g
      key={node.id}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
        onClick={() => {
          onClick?.(node);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            onClick?.(node);
          }
        }}
      role="button"
      tabIndex={0}
      style={{ cursor: isHovered ? "pointer" : "default" }}
    >
        {/* change hover to bright stroke color; selected uses a primary-700 border */}
        <rect
          x={node.x}
          y={node.y}
          width={node.width}
          height={node.height}
          fill={nodeStyle.fill}
          stroke={
            selected
              ? "#1D4ED8" 
              : isHovered
                ? "#38BDF8" 
                : nodeStyle.stroke
          }
          strokeWidth={selected ? 2 : 1}
          rx={nodeStyle.rx}
        />
      {node.type === "sense" ? (
        <foreignObject
          ref={foreignObjectRef}
          x={node.x + 10}
          y={node.y + 8}
          width={node.width}
          height={node.height}
        >
          <div
            style={{
              fontSize: textStyle.fontSize,
              fontFamily: textStyle.fontFamily,
              color: "#000",
              lineHeight: "1.3",
              textAlign: "left",
              width: `${node.width}px`,
              height: `${node.height}px`,
              overflow: "hidden",
              wordWrap: "break-word",
            }}
          >
            <div style={{ fontWeight: "bold", marginBottom: "4px" }}>
              {node.senseLabel}
            </div>
            <div style={{ fontWeight: "normal" }}>{node.definition}</div>
          </div>
        </foreignObject>
      ) : (
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
};
