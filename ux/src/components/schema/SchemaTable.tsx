import { useState } from "react";
import { Table, Button, Icon, type Column } from "@tinkermonkey/heimdall-ui";

export type { Column } from "@tinkermonkey/heimdall-ui";

interface SchemaTableProps<T extends { id: string }> {
  columns: Column<T>[];
  data: T[];
  isLoading?: boolean;
  onRowSelect?: (rowId: string) => void;
  selectedId?: string;
  testIdPrefix?: string;
  tableTestId?: string;
}

const PAGE_SIZE = 20;

export function SchemaTable<T extends { id: string }>({
  columns,
  data,
  isLoading,
  onRowSelect,
  selectedId,
  tableTestId,
}: SchemaTableProps<T>) {
  const [pageIndex, setPageIndex] = useState(0);

  const pageCount = Math.ceil(data.length / PAGE_SIZE);
  const pagedData = data.slice(pageIndex * PAGE_SIZE, (pageIndex + 1) * PAGE_SIZE);

  if (isLoading) {
    return (
      <div className="table-wrap">
        <table className="t">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 6 }).map((_, i) => (
              <tr key={i}>
                <td colSpan={3}>
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
    <div className="schema-table-wrap" data-testid={tableTestId || "schema-table"}>
      <Table<T>
        columns={columns}
        data={pagedData}
        rowKey="id"
        selectedRows={selectedId ? [selectedId] : []}
        onRowClick={(row) => onRowSelect?.((row as { id: string }).id)}
      />

      {pageCount > 1 && (
        <div className="schema-table-footer">
          <span>
            Page {pageIndex + 1} of {pageCount}
          </span>
          <div className="schema-table-footer__actions">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
              disabled={pageIndex === 0}
              data-testid="schema-pagination-prev"
            >
              <Icon name="chevronLeft" size={13} />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPageIndex((p) => Math.min(pageCount - 1, p + 1))}
              disabled={pageIndex >= pageCount - 1}
              data-testid="schema-pagination-next"
            >
              <Icon name="chevronRight" size={13} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
