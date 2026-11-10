import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";
import type { components } from "@/api/types";

type DatasetCreateRequest = components["schemas"]["DatasetCreateRequest"];

/** Datasets (by title, with their sizes): one taxonomy's, or every one in the workspace. */
export function useDatasets(taxonomyId?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.datasets(taxonomyId),
    queryFn: () => ontologyService.listDatasets(taxonomyId),
  });
}

export function useCreateDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { skipGlobalErrorToast: true },
    mutationFn: (data: DatasetCreateRequest) => ontologyService.createDataset(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.datasetsRoot });
    },
  });
}

/** Delete a dataset with its individuals and their relationships. */
export function useDeleteDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { skipGlobalErrorToast: true },
    mutationFn: (id: string) => ontologyService.deleteDataset(id),
    onSuccess: () => {
      for (const queryKey of [
        QUERY_KEYS.datasetsRoot,
        QUERY_KEYS.individualsRoot,
        QUERY_KEYS.relationshipsRoot,
        // Class and scheme counts live under the classes root.
        QUERY_KEYS.classesRoot,
        QUERY_KEYS.graph,
        QUERY_KEYS.changesRoot,
      ]) {
        queryClient.invalidateQueries({ queryKey });
      }
    },
  });
}
