import { useQuery, useMutation } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { referenceService } from "@/api/services/reference";

export function useReferenceSearch(q?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.referenceSearch(q),
    queryFn: () => referenceService.search(q ?? ""),
    enabled: !!q,
  });
}

export function useReferenceStatus() {
  return useQuery({
    queryKey: QUERY_KEYS.referenceStatus,
    queryFn: () => referenceService.getStatus(),
  });
}

export function useReferenceSearchMutation() {
  return useMutation({
    mutationFn: ({
      term,
      options,
    }: {
      term: string;
      options?: { limit?: number; sources?: string[] };
    }) => referenceService.search(term, options),
  });
}
