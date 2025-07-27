import { useEffect } from 'react';
import { cleanupMeasurementSvg } from './tree_chart_utils';

// React hook for managing the measurement SVG lifecycle
export function useMeasurementSvg(): () => void {
  useEffect(() => {
    // Cleanup on unmount
    return () => {
      cleanupMeasurementSvg();
    };
  }, []);
  
  // Return cleanup function for manual cleanup if needed
  return cleanupMeasurementSvg;
}
