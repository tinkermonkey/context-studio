import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { isTimeout } from "@/api/client/interceptors";
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
    QUERY_KEYS.datasetsRoot,
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
    // The proposal page says what an apply did, failures and timeouts included.
    meta: { skipGlobalErrorToast: true },
    onSuccess: (proposal) => {
      // The response is the proposal afterwards: show it now, before the refetch lands.
      queryClient.setQueryData(QUERY_KEYS.changeProposal(proposal.id), proposal);
      invalidateOntology(queryClient);
    },
    // A timed-out apply may still be running, or have finished, on the server: show where it got.
    onError: (error) => {
      if (isTimeout(error)) invalidateOntology(queryClient);
    },
  });
}

export function useRejectChangeProposal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ChangeProposalRejectRequest }) =>
      proposalsService.rejectProposal(id, data),
    onSuccess: (proposal) => {
      queryClient.setQueryData(QUERY_KEYS.changeProposal(proposal.id), proposal);
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.changeProposalsRoot });
    },
  });
}

export function useRevertChangeProposal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => proposalsService.revertProposal(id),
    // The page explains a refused (409) revert itself.
    meta: { skipGlobalErrorToast: true },
    onSuccess: (result) => {
      queryClient.setQueryData(QUERY_KEYS.changeProposal(result.proposal.id), result.proposal);
      invalidateOntology(queryClient);
    },
  });
}

/** Fetch a DR reflection-plan proposal's decisions file, to download it. */
export function useExportProposalDecisions() {
  return useMutation({
    mutationFn: (id: string) => proposalsService.getDecisions(id),
  });
}
