import { useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { pipelineService } from "@/api/services/pipeline";
import type { components } from "@/api/types";

type PipelineConfigurationCreateRequest =
  components["schemas"]["PipelineConfigurationCreateRequest"];
type PipelineConfigurationUpdateRequest =
  components["schemas"]["PipelineConfigurationUpdateRequest"];

export function useCreateConfiguration(pipelineType: string, implId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: PipelineConfigurationCreateRequest) =>
      pipelineService.createConfiguration(pipelineType, implId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.pipelineConfigurations(pipelineType, implId),
      });
    },
  });
}

export function useUpdateConfiguration(pipelineType: string, implId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      configId,
      body,
    }: {
      configId: string;
      body: PipelineConfigurationUpdateRequest;
    }) => pipelineService.updateConfiguration(configId, body),
    onSuccess: (_result, { configId }) => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.pipelineConfigurations(pipelineType, implId),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.pipelineConfiguration(configId),
      });
    },
  });
}

export function useDeleteConfiguration(pipelineType: string, implId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (configId: string) => pipelineService.deleteConfiguration(configId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.pipelineConfigurations(pipelineType, implId),
      });
    },
  });
}
