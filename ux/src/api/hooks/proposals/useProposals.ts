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

/**
 * Each operation's decision, with who decided it and when. `enabled` is false
 * for a reverted proposal (its decisions no longer stand; the server answers
 * 409) and while nothing is decided.
 */
export function useProposalDecisions(id: string, enabled: boolean) {
  return useQuery({
    queryKey: QUERY_KEYS.changeProposalDecisions(id),
    queryFn: () => proposalsService.getDecisions(id),
    enabled: !!id && enabled,
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
