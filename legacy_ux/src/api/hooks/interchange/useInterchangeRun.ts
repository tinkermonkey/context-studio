/**
 * Interchange Run Detail Query Hook
 *
 * Hook for fetching a specific import run by ID
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import { interchangeService, ImportRun } from "../../services/interchange";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

/**
 * Hook to fetch a specific import run by ID
 */
export const useInterchangeRun = (
  id: string,
  options?: UseQueryOptions<ImportRun, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.INTERCHANGE_RUNS, id),
    queryFn: () => interchangeService.getRun(id),
    enabled: !!id,
    ...options,
  });
};
