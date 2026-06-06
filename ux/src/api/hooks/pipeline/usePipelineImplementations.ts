import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { pipelineService } from "@/api/services/pipeline";

export function usePipelineImplementations(type: string) {
  return useQuery({
    queryKey: QUERY_KEYS.pipelineImplementations(type),
    queryFn: () => pipelineService.listImplementations(type),
    enabled: !!type,
  });
}
