import { useState, useMemo } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  getFilteredRowModel,
  ColumnDef,
  SortingState,
  PaginationState,
  flexRender,
} from "@tanstack/react-table";
import { ChevronLeft, ChevronRight, MoreVertical } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";

interface SchemaTableProps<T extends { id: string }> {
  columns: ColumnDef<T>[];
  data: T[];
  isLoading?: boolean;
  onRowSelect?: (rowId: string) => void;
  selectedId?: string;
  renderRowActions?: (row: T) => React.ReactNode;
}

export function SchemaTable<T extends { id: string }>({
  columns,
  data,
  isLoading,
  onRowSelect,
  selectedId,
  renderRowActions,
}: SchemaTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 20,
  });

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      pagination,
    },
    onSortingChange: setSorting,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const rowModel = table.getRowModel();

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
                  <Skeleton style={{ height: 16 }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <div className="table-wrap">
        <table className="t">
          <thead>
            <tr>
              {table.getHeaderGroups().map((headerGroup) =>
                headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    onClick={header.column.getToggleSortingHandler()}
                    style={{
                      cursor: header.column.getCanSort() ? "pointer" : "default",
                      userSelect: "none",
                    }}
                    data-testid={`schema-header-${header.id}`}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getIsSorted() === "asc" && (
                        <span style={{ fontSize: 10 }}>↑</span>
                      )}
                      {header.column.getIsSorted() === "desc" && (
                        <span style={{ fontSize: 10 }}>↓</span>
                      )}
                    </div>
                  </th>
                ))
              )}
              <th style={{ width: 40 }} />
            </tr>
          </thead>
          <tbody>
            {rowModel.rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length + 1} style={{ textAlign: "center", padding: "40px 0" }}>
                  <div style={{ color: "var(--canvas-fg-3)", fontSize: "var(--text-sm)" }}>
                    No items
                  </div>
                </td>
              </tr>
            ) : (
              rowModel.rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => onRowSelect?.(row.original.id)}
                  className={selectedId === row.original.id ? "selected" : ""}
                  data-testid={`schema-row-${row.original.id}`}
                  style={{ cursor: onRowSelect ? "pointer" : "default" }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                  <td style={{ width: 40, textAlign: "right" }}>
                    {renderRowActions && (
                      <div onClick={(e) => e.stopPropagation()}>
                        {renderRowActions(row.original)}
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination controls */}
      {table.getPageCount() > 1 && (
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
            Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
          </div>
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              data-testid="schema-pagination-prev"
            >
              <ChevronLeft size={14} />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
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
