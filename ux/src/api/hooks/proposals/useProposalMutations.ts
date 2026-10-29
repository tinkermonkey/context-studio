import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import {
  proposalsService,
  type ChangeProposalApplyRequest,
  type ChangeProposalCreateRequest,
  type ChangeProposalRejectRequest,
} from "@/api/services/proposals";

/** Create (auto-apply), apply and revert change the ontology: refresh all a proposal can touch. */
function invalidateOntology(queryClient: QueryClient) {
  for (const queryKey of [
    QUERY_KEYS.changeProposalsRoot,
    QUERY_KEYS.taxonomies,
    QUERY_KEYS.schemesRoot,
    QUERY_KEYS.classesRoot,
    QUERY_KEYS.individualsRoot,
    QUERY_KEYS.relationshipsRoot,
    QUERY_KEYS.properties,
    QUERY_KEYS.graph,
    QUERY_KEYS.changesRoot,
  ]) {
    queryClient.invalidateQueries({ queryKey });
  }
}

export function useCreateChangeProposal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ChangeProposalCreateRequest) => proposalsService.createProposal(data),
    // The taxonomy's approval policy may apply operations as soon as they are proposed.
    onSuccess: () => invalidateOntology(queryClient),
  });
}

/**
 * Apply operations. `data.edits` maps an operation id to the fields a reviewer corrected it to
 * (property updates and deletes only; an edited delete applies as an update). Each applied
 * operation's `applied_fields` reports what was applied.
 */
export function useApplyChangeProposal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ChangeProposalApplyRequest }) =>
      proposalsService.applyProposal(id, data),
    onSuccess: () => invalidateOntology(queryClient),
  });
}

export function useRejectChangeProposal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ChangeProposalRejectRequest }) =>
      proposalsService.rejectProposal(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.changeProposalsRoot });
    },
  });
}

export function useRevertChangeProposal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => proposalsService.revertProposal(id),
    onSuccess: () => invalidateOntology(queryClient),
  });
}
