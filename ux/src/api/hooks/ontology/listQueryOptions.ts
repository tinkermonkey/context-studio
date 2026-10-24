import { keepPreviousData } from "@tanstack/react-query";

/** Options shared by the ontology list hooks. */
export interface ListQueryOptions {
  /** Skip the request while false (e.g. an empty id set or search term). */
  enabled?: boolean;
  /** Keep showing the previous page while the next one loads (paged tables). */
  keepPrevious?: boolean;
}

/** Translate ListQueryOptions into TanStack Query options. */
export function listQueryOptions(options?: ListQueryOptions) {
  return {
    enabled: options?.enabled ?? true,
    placeholderData: options?.keepPrevious ? keepPreviousData : undefined,
  };
}
