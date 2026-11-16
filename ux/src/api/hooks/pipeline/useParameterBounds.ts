import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { pipelineService, type ParameterBounds } from "@/api/services/pipeline";

const NO_BOUNDS: ParameterBounds = {};

/**
 * The ranges the API accepts for a configuration's parameters. They change
 * only with the server, so they are read once. Empty until read (and if the
 * read fails): the form then checks no range and the server's answer stands.
 */
export function useParameterBounds(): ParameterBounds {
  const { data } = useQuery({
    queryKey: QUERY_KEYS.pipelineParameterBounds,
    queryFn: () => pipelineService.getParameterBounds(),
    staleTime: Infinity,
    meta: { skipGlobalErrorToast: true },
  });
  return data ?? NO_BOUNDS;
}
