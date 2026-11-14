import { useQueries } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { pipelineService } from "@/api/services/pipeline";
import { usePipelineImplementations } from "./usePipelineImplementations";

export interface RegisteredModel {
  provider: string;
  model: string;
}

/**
 * The provider and model of every configuration registered for a pipeline
 * type, across its implementations, without repeats. There is no endpoint that
 * lists the models a pipeline can run, so these are suggestions, not a limit.
 */
export function useRegisteredModels(pipelineType: string): RegisteredModel[] {
  const { data: implementations } = usePipelineImplementations(pipelineType);
  return useQueries({
    queries: (implementations ?? []).map((i) => ({
      queryKey: QUERY_KEYS.pipelineConfigurations(pipelineType, i.id),
      queryFn: () => pipelineService.listConfigurations(pipelineType, i.id),
    })),
    combine: (results) => {
      const seen = new Map<string, RegisteredModel>();
      for (const { data } of results) {
        for (const c of data ?? []) {
          if (c.provider && c.model) {
            seen.set(`${c.provider}\n${c.model}`, { provider: c.provider, model: c.model });
          }
        }
      }
      return [...seen.values()];
    },
  });
}
