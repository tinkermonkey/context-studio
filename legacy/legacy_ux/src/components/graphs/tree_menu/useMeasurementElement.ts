import { useEffect } from "react";
import {
  cleanupMeasurementSvg,
  cleanupMeasurementHtml,
  initializeMeasurementElements,
} from "./measurement";

// React hook for managing the measurement SVG lifecycle
// Note: We don't clean up on unmount because these are global singleton elements
// that should persist for the lifetime of the app to support caching
export function useMeasurementSvg(): () => void {
  useEffect(() => {
    // Eagerly initialize measurement elements on mount
    initializeMeasurementElements();

    // No cleanup on unmount - keep elements for the lifetime of the app
  }, []);

  // Return cleanup function for manual cleanup if needed (e.g., in tests)
  return cleanupMeasurementSvg;
}

export function useMeasurementHtml(): () => void {
  useEffect(() => {
    // Eagerly initialize measurement elements on mount
    initializeMeasurementElements();

    // No cleanup on unmount - keep elements for the lifetime of the app
  }, []);

  // Return cleanup function for manual cleanup if needed (e.g., in tests)
  return cleanupMeasurementHtml;
}
