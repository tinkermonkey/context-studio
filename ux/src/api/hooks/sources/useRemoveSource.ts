import { useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { sourcesService } from "@/api/services/sources";

/** Remove a source; entities already applied from it keep their provenance. */
export function useRemoveSource() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { skipGlobalErrorToast: true },
    mutationFn: (id: string) => sourcesService.removeSource(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.sourcesRoot }),
  });
}
