import { useEffect } from "react";
import {
  cleanupMeasurementSvg,
  cleanupMeasurementHtml,
  initializeMeasurementElements,
} from "./tree_chart_utils";

// React hook for managing the measurement SVG lifecycle
export function useMeasurementSvg(): () => void {
  useEffect(() => {
    // Eagerly initialize measurement elements on mount
    initializeMeasurementElements();

    // Cleanup on unmount
    return () => {
      cleanupMeasurementSvg();
    };
  }, []);

  // Return cleanup function for manual cleanup if needed
  return cleanupMeasurementSvg;
}

export function useMeasurementHtml(): () => void {
  useEffect(() => {
    // Eagerly initialize measurement elements on mount
    initializeMeasurementElements();

    // Cleanup on unmount
    return () => {
      cleanupMeasurementHtml();
    };
  }, []);

  // Return cleanup function for manual cleanup if needed
  return cleanupMeasurementHtml;
}
