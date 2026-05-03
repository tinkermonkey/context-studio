/**
 * Interchange Runs Query Hook
 *
 * Hook for fetching paginated list of import runs
 */

import {
  useQuery,
  UseQueryOptions,
} from "@tanstack/react-query";
import { interchangeService, ImportRun, ImportRunListParams } from "../../services/interchange";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

/**
 * Hook to fetch paginated list of import runs
 */
export const useInterchangeRuns = (
  params?: ImportRunListParams,
  options?: UseQueryOptions<ImportRun[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.INTERCHANGE_RUNS, undefined, params),
    queryFn: () => interchangeService.listRuns(params),
    ...options,
  });
};
