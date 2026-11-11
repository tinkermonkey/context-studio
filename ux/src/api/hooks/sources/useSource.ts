import { useQueries, useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { sourcesService } from "@/api/services/sources";

/** A source without its text; a removed one too (with removed_at set). */
export function useSource(id: string | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.source(id ?? ""),
    queryFn: () => sourcesService.getSource(id!),
    enabled: !!id,
    // A missing source is an answer, not a blip: callers fall back to the evidence.
    retry: false,
  });
}

/** Several sources by id, one cached query each; missing ones are left out. */
export function useSourcesByIds(ids: string[]) {
  const unique = [...new Set(ids)];
  const results = useQueries({
    queries: unique.map((id) => ({
      queryKey: QUERY_KEYS.source(id),
      queryFn: () => sourcesService.getSource(id),
      retry: false,
    })),
  });
  return new Map(
    results.flatMap((result, index) => (result.data ? [[unique[index], result.data]] : [])),
  );
}

/**
 * One page of a source's text, or its whole text when `page` is null. The
 * server answers 409 while the source isn't ready and 422 for a bad page.
 */
export function useSourceText(
  id: string | undefined,
  page: number | null,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: QUERY_KEYS.sourceText(id ?? "", page),
    queryFn: () => sourcesService.getSourceText(id!, page),
    enabled: !!id && (options.enabled ?? true),
    retry: false,
  });
}
