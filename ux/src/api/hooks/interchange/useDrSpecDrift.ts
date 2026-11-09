import { useMutation, useQueryClient } from "@tanstack/react-query";
import { interchangeService, type DrSpecDriftRequest } from "@/api/services/interchange";

/**
 * Compare the DR spec on disk with the dr_spec taxonomy. A dry run reports the
 * drift; a real run proposes it, so the proposal lists refresh. Errors are the
 * dialog's to show (the global toast is skipped).
 */
export function useDrSpecDrift() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: DrSpecDriftRequest) => interchangeService.drSpecDrift(request),
    onSuccess: (result) => {
      if (!result.dry_run && result.proposal) {
        queryClient.invalidateQueries({ queryKey: ["change-proposals"] });
      }
    },
    meta: { skipGlobalErrorToast: true },
  });
}
