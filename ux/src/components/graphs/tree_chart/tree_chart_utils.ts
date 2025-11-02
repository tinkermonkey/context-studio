import { LayoutConfig } from "@/components/graphs/tree_chart/tree_data"
import { ChartStyles } from "./tree_chart_styles";

const treeTrunkCurveRadius = 14;
const treeTrunkLeadInRadius = 10;

/**
 * Create an SVG path string for a tree node connection
 * @param startX
 * @param startY
 * @param endX
 * @param endY
 * @param curveRadius
 * @param leadInRadius
 * @returns
 */
export const createNodePath = (
  startX: number,
  startY: number,
  endX: number,
  endY: number,
  curveRadius: number = treeTrunkCurveRadius,
  leadInRadius: number = treeTrunkLeadInRadius,
): string => {
  const curveStartX = startX;
  const curveStartY = endY - curveRadius;
  const curveEndX = startX + curveRadius;
  const curveEndY = endY;

  return `M ${startX - leadInRadius + ChartStyles.branchLine.strokeWidth} ${startY}
          Q ${startX} ${startY} ${startX} ${startY + leadInRadius}
          L ${curveStartX} ${curveStartY} 
          Q ${curveStartX} ${curveEndY} ${curveEndX} ${curveEndY}
          L ${endX} ${endY}`;
};

/**
 * Create the svg path for the menu node background
 * @param x
 * @param y
 * @param labelWidth
 * @param labelHeight
 * @returns
 */
export const createMenuNodeBackgroundPath = (
  x: number,
  y: number,
  labelWidth: number,
  labelHeight: number,
  childIndex: number = 0,
  config: LayoutConfig,
  styles: any,
): string => {
  const bgWidth = labelWidth + styles.branchLine.strokeWidth;
  const halfStroke = styles.branchLine.strokeWidth / 2;
  if (childIndex === 0) {
    return `M ${x - (treeTrunkCurveRadius + halfStroke) - 3} ${y - labelHeight -4}
          h ${labelWidth + 5 + (treeTrunkCurveRadius - 2)}
          v ${labelHeight + 3}
          h ${-(labelWidth + 3.5)}
          a ${treeTrunkCurveRadius - 2} ${treeTrunkCurveRadius - 2} 0 0 1 -${treeTrunkCurveRadius - 3} -${treeTrunkCurveRadius - 2}
          Z`;
  }

  return `M ${x - (treeTrunkCurveRadius + halfStroke)} ${y - labelHeight - treeTrunkLeadInRadius}
          a ${treeTrunkCurveRadius} ${treeTrunkCurveRadius - 2} 1 0 0 ${treeTrunkCurveRadius - 2} ${(treeTrunkCurveRadius - 2) / 2}
          h ${labelWidth + 2}
          v ${labelHeight + 3}
          h ${-(labelWidth + 3.5)}
          a ${treeTrunkCurveRadius - 2} ${treeTrunkCurveRadius - 2} 0 0 1 -${treeTrunkCurveRadius - 3} -${treeTrunkCurveRadius - 2}
          Z`;
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

// Eagerly initialize both measurement elements
export function initializeMeasurementElements(): void {
  initializeMeasurementSvg();
  initializeMeasurementHtml();
}

// Text measurement options interface
export interface TextMeasurementOptions {
  fontSize?: string;
  fontFamily?: string;
  fontWeight?: string;
  fontStyle?: string;
  padding?: string;
  lineHeight?: string;
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
    padding: styleObject.padding,
    lineHeight: styleObject.lineHeight || "normal",
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
  const width = Math.ceil(bbox.width);

  // Validate measurement - warn if we got zero for non-empty text
  if (width === 0 && text.length > 0) {
    console.warn(`[NlpConceptChart] Measurement returned zero width for text: "${text.substring(0, 50)}..."`);
    // Return a fallback based on character count
    return text.length * 8; // Approximate 8px per character
  }

  return width;
}

// Measure HTML text height with specific font properties and width
export function measureHtmlTextHeight(
  text: string,
  width: number, // width available for the definition box
  options: TextMeasurementOptions = {},
): number {
  if (!text) return 0;
  if (width <= 0) {
    console.warn(`[NlpConceptChart] Invalid width (${width}) for text height measurement`);
    return 0;
  }

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
    lineHeight,
  } = options;

  measurementHtml.style.fontSize = fontSize;
  measurementHtml.style.fontFamily = fontFamily;
  measurementHtml.style.fontWeight = fontWeight;
  measurementHtml.style.fontStyle = fontStyle;
  measurementHtml.style.padding = padding;
  if (lineHeight) {
    measurementHtml.style.lineHeight = lineHeight;
  }

  // Apply word wrapping styles to match rendered text
  measurementHtml.style.wordWrap = "break-word";
  measurementHtml.style.overflowWrap = "break-word";
  measurementHtml.style.hyphens = "auto";
  measurementHtml.style.boxSizing = "border-box";
  measurementHtml.style.whiteSpace = "normal"; // Allow wrapping
  measurementHtml.style.overflow = "visible"; // Don't clip content
  measurementHtml.style.height = "auto"; // Let height expand

  // Set the text content and width constraint
  measurementHtml.textContent = text;
  measurementHtml.style.width = `${width}px`; // Set width for wrapping
  measurementHtml.style.maxWidth = `${width}px`; // Enforce max width

  // Get the bounding box height
  const bbox = measurementHtml.getBoundingClientRect();
  const height = Math.ceil(bbox.height);

  // Validate measurement - warn if we got zero for non-empty text
  if (height === 0 && text.length > 0) {
    console.warn(`[NlpConceptChart] Measurement returned zero height for text: "${text.substring(0, 50)}..." (width: ${width}px)`);
    // Return a fallback minimum height
    return 20; // Approximate minimum single-line height
  }

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
