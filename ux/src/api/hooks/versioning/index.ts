import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { versioningService } from "@/api/services/versioning";

interface ChangesParams {
  limit?: number;
}

export function useChanges(params?: ChangesParams) {
  return useQuery({
    queryKey: QUERY_KEYS.changes(params),
    queryFn: () => versioningService.getChanges(params),
  });
}

export function useSyncStatus() {
  return useQuery({
    queryKey: QUERY_KEYS.syncStatus,
    queryFn: () => versioningService.getSyncStatus(),
    refetchInterval: 60_000,
  });
}

export function usePushSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => versioningService.pushSync(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.syncStatus });
    },
  });
}

export function usePullSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => versioningService.pullSync(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.syncStatus });
    },
  });
}
