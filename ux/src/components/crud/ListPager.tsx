import { Button, Icon, SegmentedControl } from "@tinkermonkey/heimdall-ui";

export interface ListPagerProps {
  /** Total matching rows reported by the server. */
  total: number;
  /** Page size (the request `limit`). */
  limit: number;
  /** Row offset of the current page. */
  offset: number;
  /** Page sizes the user can pick from; omit to hide the size control. */
  pageSizes?: readonly number[];
  onPageChange: (offset: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  testId?: string;
}

/**
 * Footer pager for server-paginated tables: "1–50 of 208", page size choice
 * and previous/next controls. Renders nothing when there are no rows.
 */
export function ListPager({
  total,
  limit,
  offset,
  pageSizes,
  onPageChange,
  onPageSizeChange,
  testId = "list-pager",
}: ListPagerProps) {
  if (total <= 0) return null;

  const first = Math.min(offset + 1, total);
  const last = Math.min(offset + limit, total);
  const pageCount = Math.max(1, Math.ceil(total / limit));
  const page = Math.min(pageCount, Math.floor(offset / limit) + 1);
  const atFirst = offset <= 0;
  const atLast = offset + limit >= total;

  return (
    <div
      className="schema-table-footer list-pager"
      role="navigation"
      aria-label="Pagination"
      data-testid={testId}
    >
      <span className="list-pager__range" aria-live="polite" data-testid={`${testId}-range`}>
        {first}–{last} of {total}
      </span>
      <div className="schema-table-footer__actions list-pager__actions">
        {pageSizes && onPageSizeChange && (
          <SegmentedControl
            className="list-pager__size"
            aria-label="Rows per page"
            value={limit}
            onChange={(v) => onPageSizeChange(Number(v))}
            options={pageSizes.map((size) => ({ value: size, label: String(size) }))}
            data-testid={`${testId}-size`}
          />
        )}
        <span className="list-pager__page" data-testid={`${testId}-page`}>
          Page {page} of {pageCount}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onPageChange(Math.max(0, offset - limit))}
          disabled={atFirst}
          aria-disabled={atFirst}
          aria-label="Previous page"
          data-testid={`${testId}-prev`}
        >
          <Icon name="chevronLeft" size={13} />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onPageChange(offset + limit)}
          disabled={atLast}
          aria-disabled={atLast}
          aria-label="Next page"
          data-testid={`${testId}-next`}
        >
          <Icon name="chevronRight" size={13} />
        </Button>
      </div>
    </div>
  );
}
