import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { sourcesService, type Source, type SourceListParams } from "@/api/services/sources";
import { isRunActive } from "./useExtractionRun";

/** How often a list holding unsettled sources is re-read. */
export const SOURCES_POLL_MS = 2000;

/** A source that will change on its own: a web page being fetched, or an extraction running. */
export function isSourceUnsettled(source: Source): boolean {
  return (
    source.status === "fetching" ||
    !!source.last_extraction?.runs.some((run) => isRunActive(run.status))
  );
}

/**
 * A taxonomy's sources, newest first, without removed ones. While a web page
 * is being fetched or an extraction runs, the list re-reads itself, so its
 * rows settle on their own.
 */
export function useSources(params: Partial<SourceListParams>) {
  const taxonomyId = params.taxonomy_id ?? "";
  return useQuery({
    queryKey: QUERY_KEYS.sources(params),
    queryFn: () => sourcesService.listSources({ ...params, taxonomy_id: taxonomyId }),
    enabled: !!taxonomyId,
    refetchInterval: (query) =>
      query.state.data?.items.some(isSourceUnsettled) ? SOURCES_POLL_MS : false,
  });
}
