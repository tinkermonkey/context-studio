import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import {
  Table,
  TableHead,
  TableHeadCell,
  TableBody,
  TableRow,
  TableCell,
} from "flowbite-react";
import { DomainOut } from "@/api/services/domains";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";

const columnHelper = createColumnHelper<DomainOut>();

const columns = [
  columnHelper.accessor("id", {
    cell: (info) => info.getValue() ? renderShortUuid(info.getValue()) : "null",
    header: () => "ID",
  }),
  columnHelper.accessor("title", {
    cell: (info) => info.getValue() ?? "",
    header: () => "Title",
  }),
  columnHelper.accessor("definition", {
    cell: (info) => info.getValue() ?? "",
    header: () => "Definition",
  }),
  columnHelper.accessor("layer_id", {
    cell: (info) => info.getValue() ? renderShortUuid(info.getValue()) : "",
    header: () => "Layer",
  }),
  columnHelper.accessor("version", {
    cell: (info) => info.getValue() ?? "",
    header: () => "Version",
  }),
  columnHelper.accessor("created_at", {
    cell: (info) => {
      const value = info.getValue();
      return value !== null && value !== undefined ? renderShortDateTime(value) : "";
    },
    header: () => "Created",
  }),
  columnHelper.accessor("last_modified", {
    cell: (info) => {
      const value = info.getValue();
      return value !== null && value !== undefined ? renderShortDateTime(value) : "";
    },
    header: () => "Modified",
  }),
];

export function DomainsTable({ data }: { data?: DomainOut[] }) {
  const table = useReactTable({
    data: data ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <Table hoverable className="max-w-full">
      <TableHead>
        <TableRow>
          {table
            .getHeaderGroups()
            .map((headerGroup) =>
              headerGroup.headers.map((header) => (
                <TableHeadCell key={header.id}>
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext(),
                  )}
                </TableHeadCell>
              )),
            )}
        </TableRow>
      </TableHead>
      <TableBody>
        {table.getRowModel().rows.map((row) => (
          <TableRow key={row.id}>
            {row.getVisibleCells().map((cell) => (
              <TableCell key={cell.id}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
