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

export function useChangesets(params?: { limit?: number }) {
  return useQuery({
    queryKey: [...QUERY_KEYS.changesets, params],
    queryFn: () => versioningService.listChangesets(params),
  });
}

export function useCreateChangeset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ChangesetCreateRequest) => versioningService.createChangeset(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.changesets });
      queryClient.invalidateQueries({ queryKey: ["changes"] });
    },
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

export function useApplyChangeset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => versioningService.applyChangeset(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.changesets });
      queryClient.invalidateQueries({ queryKey: ["changes"] });
    },
  });
}

export function useProposalConflicts(proposalId: string | undefined) {
  return useQuery({
    queryKey: proposalId
      ? QUERY_KEYS.proposalConflicts(proposalId)
      : ["proposals", "conflicts", "disabled"],
    queryFn: () => {
      if (!proposalId) throw new Error("Proposal ID is required");
      return versioningService.getProposalConflicts(proposalId);
    },
    enabled: !!proposalId,
  });
}

export function useResolveConflicts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      proposalId,
      resolutions,
    }: {
      proposalId: string;
      resolutions: Record<string, Record<string, unknown>>;
    }) => versioningService.resolveConflicts(proposalId, resolutions),
    onSuccess: (_, { proposalId }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.proposalConflicts(proposalId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.syncStatus });
    },
  });
}
