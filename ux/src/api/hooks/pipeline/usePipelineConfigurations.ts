import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { pipelineService } from "@/api/services/pipeline";

export function usePipelineConfigurations(type: string, implId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.pipelineConfigurations(type, implId),
    queryFn: () => pipelineService.listConfigurations(type, implId),
    enabled: !!type && !!implId,
  });
}
