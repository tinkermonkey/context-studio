/** Ids per request: well under the API's 500-id cap and the URL length limit. */
export const ID_CHUNK_SIZE = 100;

/** The unique, non-empty ids, sorted (a stable query key). */
export function uniqueIds(ids: Array<string | null | undefined>): string[] {
  return [...new Set(ids.filter((id): id is string => !!id))].sort();
}

/**
 * Fetch a list by ids in chunks of ID_CHUNK_SIZE, in parallel, and merge the
 * pages into one list response.
 */
export async function listByIdChunks<T, R extends { items: T[]; total: number }>(
  ids: string[],
  fetchChunk: (chunk: string[]) => Promise<R>,
): Promise<R> {
  const chunks: string[][] = [];
  for (let i = 0; i < ids.length; i += ID_CHUNK_SIZE) {
    chunks.push(ids.slice(i, i + ID_CHUNK_SIZE));
  }
  const pages = await Promise.all(chunks.map(fetchChunk));
  const items = pages.flatMap((page) => page.items);
  return { ...pages[0], items, total: items.length, limit: items.length, offset: 0 };
}

/**
 * useQueries `combine`: the loaded results' data. Module-level, so useQueries
 * keeps the combined array stable while the results don't change.
 */
export function loadedData<T>(results: { data?: T }[]): T[] {
  return results.flatMap((r) => (r.data ? [r.data] : []));
}
