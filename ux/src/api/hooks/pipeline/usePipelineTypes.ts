import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { pipelineService } from "@/api/services/pipeline";

export function usePipelineTypes() {
  return useQuery({
    queryKey: QUERY_KEYS.pipelineTypes,
    queryFn: () => pipelineService.listTypes(),
  });
}
