import { useState } from "react";
import { Table, Button, type Column } from "@tinkermonkey/heimdall-ui";
import { ChevronLeft, ChevronRight } from "lucide-react";

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
    <div
      data-testid={tableTestId || "schema-table"}
      style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}
    >
      <Table<T>
        columns={columns}
        data={pagedData}
        rowKey="id"
        selectable={!!onRowSelect}
        selectedRows={selectedId ? [selectedId] : []}
        onSelectRows={(keys) => onRowSelect?.(String(keys[0]))}
      />

      {pageCount > 1 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "var(--text-sm)",
            color: "var(--canvas-fg-2)",
          }}
        >
          <div>
            Page {pageIndex + 1} of {pageCount}
          </div>
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <Button
              variant="ghost"
              onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
              disabled={pageIndex === 0}
              data-testid="schema-pagination-prev"
            >
              <ChevronLeft size={14} />
            </Button>
            <Button
              variant="ghost"
              onClick={() => setPageIndex((p) => Math.min(pageCount - 1, p + 1))}
              disabled={pageIndex >= pageCount - 1}
              data-testid="schema-pagination-next"
            >
              <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
