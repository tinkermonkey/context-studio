import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { referenceService } from "@/api/services/reference";
import type { GroundingWorkflowCreate, GroundingWorkflowUpdate } from "@/api/types/grounding";

export function useReferenceSearch(q?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.referenceSearch(q),
    queryFn: () => referenceService.search(q ?? ""),
    enabled: !!q,
  });
}

export function useReferenceStatus() {
  return useQuery({
    queryKey: QUERY_KEYS.referenceStatus,
    queryFn: () => referenceService.getStatus(),
  });
}

export function useReferenceSearchMutation() {
  return useMutation({
    mutationFn: ({
      term,
      options,
    }: {
      term: string;
      options?: { limit?: number; sources?: string[] };
    }) => referenceService.search(term, options),
  });
}

export function useGroundingWorkflows() {
  return useQuery({
    queryKey: QUERY_KEYS.groundingWorkflows,
    queryFn: () => referenceService.listGroundingWorkflows(),
  });
}

export function useGroundingWorkflow(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.groundingWorkflow(id),
    queryFn: () => referenceService.getGroundingWorkflow(id),
    enabled: !!id,
  });
}

export function useCreateGroundingWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: GroundingWorkflowCreate) => referenceService.createGroundingWorkflow(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.groundingWorkflows });
    },
  });
}

export function useUpdateGroundingWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: GroundingWorkflowUpdate }) =>
      referenceService.updateGroundingWorkflow(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.groundingWorkflows });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.groundingWorkflow(id) });
    },
  });
}

export function useDeleteGroundingWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => referenceService.deleteGroundingWorkflow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.groundingWorkflows });
    },
  });
}

export function useRunGroundingWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => referenceService.runGroundingWorkflow(id),
    onSuccess: (_result, id) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.groundingWorkflowRuns(id) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.groundingWorkflows });
    },
  });
}

export function useGroundingWorkflowRuns(workflowId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.groundingWorkflowRuns(workflowId),
    queryFn: () => referenceService.getGroundingWorkflowRuns(workflowId),
    enabled: !!workflowId,
  });
}
