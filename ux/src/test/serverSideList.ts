import { http, HttpResponse } from "msw";

interface ListEntity {
  id: string;
  title?: string;
  identifier?: string | null;
}

/**
 * An MSW list handler that behaves like the backend list routes: filters by
 * `q` (case-insensitive title or identifier, or `matchText` when given), by
 * repeated `ids`, and by any `filters` param → field pairs; pages by
 * limit/offset; reports the filtered `total`; and records each request's
 * query params in `requests`.
 */
export function serverSideList<T extends ListEntity>(
  path: string,
  all: T[],
  requests: URLSearchParams[] = [],
  options: {
    filters?: Record<string, (item: T, value: string) => boolean>;
    matchText?: (item: T) => string;
  } = {},
) {
  return http.get(`*${path}`, ({ request }) => {
    const params = new URL(request.url).searchParams;
    requests.push(params);
    const q = params.get("q")?.toLowerCase();
    const ids = params.getAll("ids");
    const text = options.matchText ?? ((item: T) => `${item.title ?? ""} ${item.identifier ?? ""}`);
    const matching = all.filter(
      (item) =>
        (!q || text(item).toLowerCase().includes(q)) &&
        (ids.length === 0 || ids.includes(item.id)) &&
        Object.entries(options.filters ?? {}).every(([param, test]) => {
          const value = params.get(param);
          return value === null || test(item, value);
        }),
    );
    const limit = Number(params.get("limit") ?? 100);
    const offset = Number(params.get("offset") ?? 0);
    return HttpResponse.json({
      items: matching.slice(offset, offset + limit),
      total: matching.length,
      limit,
      offset,
    });
  });
}

/** The page's main table requests: not the limit=1 tab counts or ids title lookups. */
export function pageRequests(requests: URLSearchParams[]) {
  return requests.filter((p) => p.get("limit") !== "1" && p.getAll("ids").length === 0);
}
