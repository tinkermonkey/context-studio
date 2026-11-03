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

export function useChangeProposal(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.changeProposal(id),
    queryFn: () => proposalsService.getProposal(id),
    enabled: !!id,
  });
}
