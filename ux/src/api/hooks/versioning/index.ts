import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { versioningService } from "@/api/services/versioning";
import type { components } from "@/api/types";

type ChangesetCreateRequest = components["schemas"]["ChangesetCreateRequest"];

interface ChangesParams {
  limit?: number;
}

export function useChanges(params?: ChangesParams) {
  return useQuery({
    queryKey: QUERY_KEYS.changes(params),
    queryFn: () => versioningService.getChanges(params),
  });
}

// Note: There is no paginated list endpoint for changesets in the current API.
// Individual changesets can be retrieved by ID via versioningService.getChangeset(id).

export function useCreateChangeset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ChangesetCreateRequest) =>
      versioningService.createChangeset(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.changesets });
    },
  });
}

export function useSyncStatus() {
  return useQuery({
    queryKey: QUERY_KEYS.syncStatus,
    queryFn: () => versioningService.getSyncStatus(),
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
