import { useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { sourcesService, type NewSource, type SourceScope } from "@/api/services/sources";

/** Add a file, a web page or pasted text as a source. */
export function useAddSource() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { skipGlobalErrorToast: true },
    mutationFn: ({ scope, source }: { scope: SourceScope; source: NewSource }) =>
      sourcesService.addSource(scope, source),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.sourcesRoot }),
  });
}
