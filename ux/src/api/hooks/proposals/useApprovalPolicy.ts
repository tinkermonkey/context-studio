import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { proposalsService, type ApprovalPolicyRequest } from "@/api/services/proposals";

export function useApprovalPolicy(taxonomyId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.approvalPolicy(taxonomyId),
    queryFn: () => proposalsService.getApprovalPolicy(taxonomyId),
    enabled: !!taxonomyId,
  });
}

export function useSetApprovalPolicy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ taxonomyId, data }: { taxonomyId: string; data: ApprovalPolicyRequest }) =>
      proposalsService.setApprovalPolicy(taxonomyId, data),
    onSuccess: (policy, { taxonomyId }) => {
      queryClient.setQueryData(QUERY_KEYS.approvalPolicy(taxonomyId), policy);
    },
  });
}
