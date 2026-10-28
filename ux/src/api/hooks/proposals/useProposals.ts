import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { proposalsService, type ChangeProposalListParams } from "@/api/services/proposals";

export function useChangeProposals(params?: ChangeProposalListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.changeProposals(params),
    queryFn: () => proposalsService.listProposals(params),
  });
}

export function useChangeProposal(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.changeProposal(id),
    queryFn: () => proposalsService.getProposal(id),
    enabled: !!id,
  });
}
