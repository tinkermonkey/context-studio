/**
 * Interchange Export Mutation Hook
 *
 * Hook for exporting ontology data to a file
 */

import { useMutation, UseMutationOptions } from "@tanstack/react-query";
import {
  interchangeService,
  SerializationScope,
} from "../../services/interchange";

/**
 * Hook to export ontology data
 */
export const useInterchangeExport = (
  options?: UseMutationOptions<
    Blob,
    Error,
    { format: string; scope: SerializationScope }
  >,
) => {
  return useMutation({
    mutationFn: ({ format, scope }) =>
      interchangeService.exportFile(format, scope),
    ...options,
  });
};
