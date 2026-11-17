import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { proposalsService, type ChangeProposalListParams } from "@/api/services/proposals";

/** `refetchInterval` (ms) polls, for counts that should notice proposals made over MCP. */
export function useChangeProposals(
  params?: ChangeProposalListParams,
  options?: { refetchInterval?: number },
) {
  return useQuery({
    queryKey: QUERY_KEYS.changeProposals(params),
    queryFn: () => proposalsService.listProposals(params),
    refetchInterval: options?.refetchInterval,
  });
}

/** Every proposal matching `params`, all pages (e.g. the benchmark's gold checks). */
export function useAllChangeProposals(params: Omit<ChangeProposalListParams, "limit" | "offset">) {
  return useQuery({
    queryKey: QUERY_KEYS.changeProposals({ ...params, all: true }),
    queryFn: () => proposalsService.listAllProposals(params),
  });
}

/**
 * The proposal's standing decisions (its gold), with who decided each and
 * when. `enabled` is false for a reverted proposal (a revert supersedes what
 * it applied) and while nothing is decided.
 */
export function useProposalDecisions(taxonomyId: string, proposalId: string, enabled: boolean) {
  return useQuery({
    queryKey: QUERY_KEYS.changeProposalDecisions(proposalId),
    queryFn: () => proposalsService.listProposalGold(taxonomyId, proposalId),
    enabled: !!taxonomyId && !!proposalId && enabled,
    retry: false,
  });
}

export function useChangeProposal(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.changeProposal(id),
    queryFn: () => proposalsService.getProposal(id),
    enabled: !!id,
  });
}
