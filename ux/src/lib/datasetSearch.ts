/**
 * The `dataset` URL search parameter: which dataset the data pages, the
 * Navigator's Data mode and the graph show. Validated once on the /app layout
 * route and kept across navigation inside the app.
 */
export interface DatasetSearch {
  dataset?: string;
}

/** A dataset id from the URL, or undefined when absent or blank. */
export function parseDatasetParam(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}
