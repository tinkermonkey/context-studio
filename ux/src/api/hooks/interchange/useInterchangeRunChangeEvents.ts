/**
 * Interchange Run Change Events Query Hook
 *
 * Hook for fetching change events associated with an import run
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import {
  interchangeService,
  ChangeEvent,
  ChangeEventListParams,
} from "../../services/interchange";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

/**
 * Hook to fetch change events for a specific import run
 */
export const useInterchangeRunChangeEvents = (
  id: string,
  params?: ChangeEventListParams,
  options?: UseQueryOptions<ChangeEvent[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.INTERCHANGE_RUNS, id, {
      change_events: true,
      ...params,
    }),
    queryFn: () => interchangeService.getRunChangeEvents(id, params),
    enabled: !!id,
    ...options,
  });
};
