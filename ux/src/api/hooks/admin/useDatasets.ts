import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { adminService } from "@/api/services/admin";
import type { components } from "@/api/types";

type DatasetCreateRequest = components["schemas"]["DatasetCreateRequest"];
type DatasetUpdateRequest = components["schemas"]["DatasetUpdateRequest"];

export function useDatasets() {
  return useQuery({
    queryKey: QUERY_KEYS.datasets(),
    queryFn: () => adminService.listDatasets(),
  });
}

export function useDataset(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.dataset(id),
    queryFn: () => adminService.getDataset(id),
    enabled: !!id,
  });
}

export function useCreateDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: DatasetCreateRequest) => adminService.createDataset(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.datasets() });
    },
  });
}

export function useUpdateDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: DatasetUpdateRequest }) =>
      adminService.updateDataset(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.datasets() });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dataset(id) });
    },
  });
}

export function useDeleteDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => adminService.deleteDataset(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.datasets() });
    },
  });
}

export function useActivateDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => adminService.activateDataset(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.datasets() });
    },
  });
}
