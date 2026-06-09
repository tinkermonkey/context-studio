import { useState, useEffect } from "react";
import { Table, Button, Icon, RowMenu, type Column } from "@tinkermonkey/heimdall-ui";

export type RowMenuAction =
  | { id: string; label: string; icon?: string; danger?: boolean; disabled?: boolean }
  | { type: "separator" };

interface SelectableTableProps<T extends { id: string }> {
  columns: Column<T>[];
  data: T[];
  isLoading?: boolean;
  selectedRows?: string[];
  onSelectRows?: (ids: string[]) => void;
  onRowClick?: (row: T) => void;
  rowMenuActions?: RowMenuAction[];
  onRowMenuAction?: (actionId: string, row: T) => void;
  testId?: string;
}

const PAGE_SIZE = 9;

export function SelectableTable<T extends { id: string }>({
  columns,
  data,
  isLoading,
  selectedRows = [],
  onSelectRows,
  onRowClick,
  rowMenuActions,
  onRowMenuAction,
  testId = "selectable-table",
}: SelectableTableProps<T>) {
  const [pageIndex, setPageIndex] = useState(0);

  const pageCount = Math.ceil(data.length / PAGE_SIZE);

  useEffect(() => {
    const maxPage = Math.max(0, pageCount - 1);
    if (pageIndex > maxPage) setPageIndex(maxPage);
  }, [data.length, pageCount, pageIndex]);

  const startIndex = pageIndex * PAGE_SIZE;
  const endIndex = Math.min(startIndex + PAGE_SIZE, data.length);
  const pagedData = data.slice(startIndex, endIndex);

  const tableColumns: Column<T>[] = [
    ...columns,
    ...(rowMenuActions && onRowMenuAction
      ? [
          {
            key: "id" as keyof T,
            label: "",
            width: "48px",
            render: (_value: T[keyof T], row: T) => (
              <div className="csb-rowmenu">
                <RowMenu
                  actions={rowMenuActions}
                  onAction={(actionId) => onRowMenuAction(actionId, row)}
                  triggerLabel="Row actions"
                />
              </div>
            ),
          },
        ]
      : []),
  ];

  if (isLoading) {
    return (
      <div className="schema-table-wrap" data-testid={testId}>
        <table className="t">
          <thead>
            <tr>
              <th colSpan={columns.length + 2}>&nbsp;</th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 6 }).map((_, i) => (
              <tr key={i}>
                <td colSpan={columns.length + 2}>
                  <div className="skeleton" style={{ height: 16 }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="schema-table-wrap" data-testid={testId}>
      <Table<T>
        columns={tableColumns}
        data={pagedData}
        rowKey="id"
        selectable
        selectedRows={selectedRows}
        onSelectRows={(keys) => onSelectRows?.(keys.map(String))}
        onRowClick={onRowClick}
      />

      {pageCount > 1 && (
        <div className="schema-table-footer" role="navigation" aria-label="Pagination">
          <span>
            {startIndex + 1}–{endIndex} of {data.length}
          </span>
          <div className="schema-table-footer__actions">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
              disabled={pageIndex === 0}
              aria-label="Previous page"
              data-testid="selectable-table-prev"
            >
              <Icon name="chevronLeft" size={13} />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPageIndex((p) => Math.min(pageCount - 1, p + 1))}
              disabled={pageIndex >= pageCount - 1}
              aria-label="Next page"
              data-testid="selectable-table-next"
            >
              <Icon name="chevronRight" size={13} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
