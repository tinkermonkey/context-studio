import { chartStyles } from "./config";

// Text measurement options interface
export interface TextMeasurementOptions {
  fontSize?: string;
  fontFamily?: string;
  fontWeight?: string;
  fontStyle?: string;
  padding?: string;
  lineHeight?: string;
}

// DOM elements for measurement
let measurementSvg: SVGSVGElement | null = null;
let measurementText: SVGTextElement | null = null;
let measurementHtml: HTMLDivElement | null = null;
let measurementReady = false;

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

  // Mark as ready after DOM insertion
  measurementReady = true;
}

// Clean up the measurement SVG when component unmounts
export function cleanupMeasurementSvg(): void {
  if (measurementSvg && measurementSvg.parentNode) {
    measurementSvg.parentNode.removeChild(measurementSvg);
    measurementSvg = null;
    measurementText = null;
    measurementReady = false;
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

  // Mark as ready after DOM insertion
  measurementReady = true;
}

// Eagerly initialize both measurement elements
export function initializeMeasurementElements(): void {
  initializeMeasurementSvg();
  initializeMeasurementHtml();
}

export function cleanupMeasurementHtml(): void {
  if (measurementHtml && measurementHtml.parentNode) {
    measurementHtml.parentNode.removeChild(measurementHtml);
    measurementHtml = null;
    measurementReady = false;
  }
}

// Check if measurement elements are ready
export function isMeasurementReady(): boolean {
  return measurementReady && measurementSvg !== null && measurementHtml !== null;
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
    lineHeight: styleObject.lineHeight,
  };
}

// Get text measurement options from chart styles
export const getTextOptionsFromStyles = (): TextMeasurementOptions => {
  return extractFontPropertiesFromStyles(chartStyles.nodeLabel);
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
    console.warn(`[TreeMenu] Measurement returned zero width for text: "${text.substring(0, 50)}..."`);
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
    console.warn(`[TreeMenu] Invalid width (${width}) for text height measurement`);
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
    console.warn(`[TreeMenu] Measurement returned zero height for text: "${text.substring(0, 50)}..." (width: ${width}px)`);
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

// Text width measurement cache to avoid recalculating widths for the same text
// Font changes will require a complete chart redraw, so we only cache by text content
export class TextWidthCache {
  private cache = new Map<string, number>();
  private textOptions = extractFontPropertiesFromStyles(chartStyles.nodeLabel);

  // Get cached width or measure and cache it using current font styles
  getTextWidth(text: string): number {
    if (this.cache.has(text)) {
      return this.cache.get(text)!;
    }

    const width = measureSvgTextWidth(text, this.textOptions);
    this.cache.set(text, width);
    return width;
  }

  // Set a cached value (useful for preserving existing measurements)
  setCachedWidth(text: string, width: number): void {
    this.cache.set(text, width);
  }

  // Clear the cache (useful for testing or font changes)
  clear(): void {
    this.cache.clear();
  }

  // Get cache size for debugging
  size(): number {
    return this.cache.size;
  }
}

// Text height measurement cache to avoid recalculating heights for the same text
// Font changes will require a complete chart redraw, so we only cache by text content
export class TextHeightCache {
  private cache = new Map<string, number>();
  private textOptions;

  constructor(styleSource: any) {
    this.textOptions = extractFontPropertiesFromStyles(styleSource);
  }

  // Get cached height or measure and cache it using current font styles
  getTextHeight(text: string, width: number): number {
    const cacheKey = `${text}-${width}`;
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey)!;
    }

    const height = measureHtmlTextHeight(text, width, this.textOptions);
    this.cache.set(cacheKey, height);
    return height;
  }

  // Set a cached value (useful for preserving existing measurements)
  setCachedHeight(text: string, width: number, height: number): void {
    this.cache.set(`${text}-${width}`, height);
  }

  // Clear the cache (useful for testing or font changes)
  clear(): void {
    this.cache.clear();
  }

  // Get cache size for debugging
  size(): number {
    return this.cache.size;
  }
}
