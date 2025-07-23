import React from "react";
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
  Checkbox
} from "flowbite-react";
import { LayerOut } from "@/api/services/layers";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { Edit } from "lucide-react";

const columnHelper = createColumnHelper<LayerOut>();

const columns = [
  columnHelper.display({
    id: 'select',
    header: ({ table }) => (
      <Checkbox
        checked={table.getIsAllRowsSelected()}
        indeterminate={table.getIsSomeRowsSelected()}
        onChange={() => {
          if (table.getIsAllRowsSelected() || table.getIsSomeRowsSelected()) {
            table.toggleAllRowsSelected(false);
          } else {
            table.toggleAllRowsSelected(true);
          }
        }}
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onChange={() => row.toggleSelected()}
      />
    ),
    size: 32,
  }),
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
  columnHelper.accessor("primary_predicate", {
    cell: (info) => info.getValue() ?? "",
    header: () => "Primary Predicate",
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

export interface LayersTableProps {
  data?: LayerOut[];
  onSelectionChange?: (count: number) => void;
  onEdit?: (id: string) => void;
}

const LayersTable = React.forwardRef<any, LayersTableProps>((props, ref) => {
  const table = useReactTable({
    data: props.data ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    enableRowSelection: true,
  });

  React.useImperativeHandle(ref, () => table, [table]);

  React.useEffect(() => {
    if (props.onSelectionChange) {
      props.onSelectionChange(table.getSelectedRowModel().rows.length);
    }
  }, [table.getSelectedRowModel().rows.length]);

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
            <TableHeadCell/>
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
            <TableCell>
              <Edit
                className="cursor-pointer hover:stroke-primary-600"
                onClick={() => {
                  const id = row.original.id;
                  if (props.onEdit && id) {
                    props.onEdit(id);
                  } else {
                    console.log("Edit", row.id);
                  }
                }}
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
});

export { LayersTable };
