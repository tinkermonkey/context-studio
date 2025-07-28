import { ChartStyles } from "./tree_styles";

// Path utility functions for SVG drawing
export const createNodePath = (
  startX: number,
  startY: number,
  endX: number,
  endY: number,
  curveRadius: number = 15,
  leadInRadius: number = 10,
): string => {
  const curveStartX = startX;
  const curveStartY = endY - curveRadius;
  const curveEndX = startX + curveRadius;
  const curveEndY = endY;

  return `M ${startX - leadInRadius} ${startY + ChartStyles.branchLine.strokeWidth}
          Q ${startX} ${startY} ${startX} ${startY + leadInRadius}
          L ${curveStartX} ${curveStartY} 
          Q ${curveStartX} ${curveEndY} ${curveEndX} ${curveEndY}
          L ${endX} ${endY}`;
};

// Text measurement utilities
let measurementSvg: SVGSVGElement | null = null;
let measurementText: SVGTextElement | null = null;
let measurementHtml: HTMLDivElement | null = null;

// Initialize the offscreen SVG element for text measurement
function initializeMeasurementSvg(): void {
  if (measurementSvg) return;

  measurementSvg = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "svg",
  );
  measurementSvg.style.position = "absolute";
  measurementSvg.style.left = "-9999px";
  measurementSvg.style.top = "-9999px";
  measurementSvg.style.visibility = "hidden";
  measurementSvg.style.pointerEvents = "none";

  measurementText = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "text",
  );
  measurementSvg.appendChild(measurementText);
  document.body.appendChild(measurementSvg);
}

// Clean up the measurement SVG when component unmounts
export function cleanupMeasurementSvg(): void {
  if (measurementSvg && measurementSvg.parentNode) {
    measurementSvg.parentNode.removeChild(measurementSvg);
    measurementSvg = null;
    measurementText = null;
  }
}

// Initialize the offscreen HTML element for text measurement
function initializeMeasurementHtml(): void {
  if (measurementHtml) return;

  measurementHtml = document.getElementById(
    "text-measurement",
  ) as HTMLDivElement | null;

  if (!measurementHtml || !(measurementHtml instanceof HTMLDivElement)) {
    measurementHtml = document.createElement("div");
    // set the id
    measurementHtml.id = "text-measurement";
    measurementHtml.style.position = "absolute";
    measurementHtml.style.left = "-9999px";
    measurementHtml.style.top = "-9999px";
    measurementHtml.style.visibility = "hidden";
    measurementHtml.style.pointerEvents = "none";

    document.body.appendChild(measurementHtml);
  }
}

export function cleanupMeasurementHtml(): void {
  if (measurementHtml && measurementHtml.parentNode) {
    measurementHtml.parentNode.removeChild(measurementHtml);
    measurementHtml = null;
  }
}

// Text measurement options interface
export interface TextMeasurementOptions {
  fontSize?: string;
  fontFamily?: string;
  fontWeight?: string;
  fontStyle?: string;
  padding?: string;
}

// Extract font properties from chart styles with better parsing
export function extractFontPropertiesFromStyles(
  styleObject: any,
): TextMeasurementOptions {
  // Parse the font shorthand property if it exists
  // Font shorthand format: [font-style] [font-variant] [font-weight] [font-size/line-height] [font-family]
  const fontString = styleObject.font || "14px sans-serif";
  const fontParts = fontString.split(" ");

  // Default values that match chart styles
  let fontSize = "14px";
  let fontFamily = "sans-serif";
  let fontWeight = "normal";
  let fontStyle = "normal";

  if (fontParts.length >= 2) {
    // Look for size (contains 'px', 'em', 'rem', etc.)
    const sizeIndex = fontParts.findIndex((part: string) =>
      /\d+(px|em|rem|pt|%)/.test(part),
    );
    if (sizeIndex !== -1) {
      fontSize = fontParts[sizeIndex];
      // Everything after size is typically font-family
      if (sizeIndex + 1 < fontParts.length) {
        fontFamily = fontParts.slice(sizeIndex + 1).join(" ");
      }
      // Everything before size could be style/weight
      const beforeSize = fontParts.slice(0, sizeIndex);
      beforeSize.forEach((part: string) => {
        if (["italic", "oblique"].includes(part)) {
          fontStyle = part;
        } else if (
          [
            "bold",
            "bolder",
            "lighter",
            "100",
            "200",
            "300",
            "400",
            "500",
            "600",
            "700",
            "800",
            "900",
          ].includes(part)
        ) {
          fontWeight = part;
        }
      });
    } else {
      // Fallback: assume first is size, rest is family
      fontSize = fontParts[0];
      fontFamily = fontParts.slice(1).join(" ");
    }
  }

  return {
    fontSize,
    fontFamily,
    fontWeight,
    fontStyle,
  };
}

// Get text measurement options from chart styles
export const getTextOptionsFromStyles = (): TextMeasurementOptions => {
  return extractFontPropertiesFromStyles(ChartStyles.nodeLabel);
};

// Helper to create a CSS font string from TextMeasurementOptions
export function createFontString(options: TextMeasurementOptions): string {
  const {
    fontStyle = "normal",
    fontWeight = "normal",
    fontSize = "14px",
    fontFamily = "sans-serif",
  } = options;
  return `${fontStyle} ${fontWeight} ${fontSize} ${fontFamily}`.trim();
}

// Measure SVG text width with specific font properties
export function measureSvgTextWidth(
  text: string,
  options: TextMeasurementOptions = {},
): number {
  if (!text) return 0;

  // Initialize measurement SVG if needed
  initializeMeasurementSvg();

  if (!measurementText) {
    throw new Error("Failed to initialize measurement text element");
  }

  // Apply font properties
  const {
    fontSize = "14px",
    fontFamily = "system-ui, -apple-system, sans-serif",
    fontWeight = "normal",
    fontStyle = "normal",
  } = options;

  measurementText.style.fontSize = fontSize;
  measurementText.style.fontFamily = fontFamily;
  measurementText.style.fontWeight = fontWeight;
  measurementText.style.fontStyle = fontStyle;

  // Set the text content
  measurementText.textContent = text;

  // Get the bounding box
  const bbox = measurementText.getBBox();
  return Math.ceil(bbox.width);
}

// Measure HTML text height with specific font properties and width
export function measureHtmlTextHeight(
  text: string,
  width: number, // width available for the definition box
  options: TextMeasurementOptions = {},
): number {
  if (!text) return 0;

  // Initialize measurement HTML container if needed
  initializeMeasurementHtml();

  if (!measurementHtml) {
    throw new Error("Failed to initialize measurement text element");
  }

  // Apply font properties
  const {
    fontSize = "14px",
    fontFamily = "system-ui, -apple-system, sans-serif",
    fontWeight = "normal",
    fontStyle = "normal",
    padding = "3px",
  } = options;

  measurementHtml.style.fontSize = fontSize;
  measurementHtml.style.fontFamily = fontFamily;
  measurementHtml.style.fontWeight = fontWeight;
  measurementHtml.style.fontStyle = fontStyle;
  measurementHtml.style.padding = padding;

  // Set the text content
  measurementHtml.textContent = text;
  measurementHtml.style.width = `${width}px`; // Set width for wrapping

  // Get the bounding box height
  const bbox = measurementHtml.getBoundingClientRect();
  const height = Math.ceil(bbox.height);

  return height;
}

// Convenience function to measure multiple texts and return the maximum width
export function measureMaxTextWidth(
  texts: string[],
  options: TextMeasurementOptions = {},
): number {
  if (texts.length === 0) return 0;

  return Math.max(...texts.map((text) => measureSvgTextWidth(text, options)));
}
