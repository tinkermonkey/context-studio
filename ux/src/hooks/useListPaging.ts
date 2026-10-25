import { useCallback, useEffect, useState } from "react";
import { LIST_PAGE_SIZES } from "@/api/config";
import { useDebounce } from "@/hooks/useDebounce";
import type { ListPagerProps } from "@/components/crud/ListPager";

/** Debounce applied to list-page search text before it is sent as `q`. */
export const LIST_SEARCH_DEBOUNCE_MS = 250;

export type SortableField = "title" | "created_at" | "last_modified";

export interface ListSort {
  sortBy: SortableField;
  sortOrder: "asc" | "desc";
}

/** Newest first, so a just-created row lands on the first page. */
const DEFAULT_SORT: ListSort = { sortBy: "created_at", sortOrder: "desc" };

export interface ListPagingParams {
  limit: number;
  offset: number;
  q?: string;
  sort_by: SortableField;
  sort_order: "asc" | "desc";
}

/**
 * Server-side paging state for a list page: page index, page size, debounced
 * search text and column sort, exposed as list request params.
 *
 * The page resets to the first one when the search, sort, page size or
 * `filterKey` (any other server filter the page applies) changes.
 */
export function useListPaging(filterKey = "") {
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState<number>(LIST_PAGE_SIZES[0]);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<ListSort>(DEFAULT_SORT);
  const q = useDebounce(search.trim(), LIST_SEARCH_DEBOUNCE_MS) || undefined;

  useEffect(() => {
    setPageIndex(0);
  }, [q, filterKey, sort.sortBy, sort.sortOrder, pageSize]);

  const params: ListPagingParams = {
    limit: pageSize,
    offset: pageIndex * pageSize,
    q,
    sort_by: sort.sortBy,
    sort_order: sort.sortOrder,
  };

  /** Heimdall Table sort callback: a null direction restores the default sort. */
  const onSort = useCallback((key: string, direction: "asc" | "desc" | null) => {
    if (direction === null || !["title", "created_at", "last_modified"].includes(key)) {
      setSort(DEFAULT_SORT);
    } else {
      setSort({ sortBy: key as SortableField, sortOrder: direction });
    }
  }, []);

  /** Pager props for a response with this `total` (undefined until it loads). */
  const pagination = (total: number | undefined): ListPagerProps => ({
    total: total ?? 0,
    limit: pageSize,
    offset: pageIndex * pageSize,
    pageSizes: LIST_PAGE_SIZES,
    onPageChange: (nextOffset: number) => setPageIndex(Math.floor(nextOffset / pageSize)),
    onPageSizeChange: setPageSize,
  });

  /**
   * Step back when the current page is past the end (e.g. a delete emptied the
   * last page). Call with the latest response total.
   */
  const clampToTotal = useCallback(
    (total: number | undefined) => {
      if (total === undefined || pageIndex === 0) return;
      const lastPage = Math.max(0, Math.ceil(total / pageSize) - 1);
      if (pageIndex > lastPage) setPageIndex(lastPage);
    },
    [pageIndex, pageSize],
  );

  return {
    params,
    search,
    setSearch,
    hasSearch: !!q,
    onSort,
    pagination,
    clampToTotal,
    resetPage: () => setPageIndex(0),
  };
}
