/**
 * Predicates Table Component
 *
 * Table for displaying and managing predicates
 */

import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import { PredicateOut } from "@/api/services/predicates";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { usePredicates } from "@/api/hooks/predicates";
import { useDeletePredicate } from "@/api/hooks/predicates";
import { PredicateForm } from "@/components/forms/predicate_form";
import { BaseNodeTable } from "./node_table";

const columnHelper = createColumnHelper<PredicateOut>();

const columns = [
  columnHelper.display({
    id: "select",
    header: ({ table }) => {
      const { rows } = table.getRowModel();
      const selectedCount = rows.filter((row) => row.getIsSelected()).length;
      const isAllSelected = rows.length > 0 && selectedCount === rows.length;
      const isSomeSelected = selectedCount > 0 && selectedCount < rows.length;

      return (
        <Checkbox
          checked={isAllSelected}
          indeterminate={isSomeSelected}
          onChange={() => {
            if (isAllSelected || isSomeSelected) {
              // Deselect all visible rows
              rows.forEach((row) => row.toggleSelected(false));
            } else {
              // Select all visible rows
              rows.forEach((row) => row.toggleSelected(true));
            }
          }}
        />
      );
    },
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onChange={() => row.toggleSelected()}
      />
    ),
    size: 32,
  }),
  columnHelper.accessor("id", {
    cell: (info) =>
      info.getValue() ? renderShortUuid(info.getValue()) : "null",
    header: () => "ID",
  }),
  columnHelper.accessor("title", {
    cell: (info) => info.getValue() ?? "",
    header: () => "Title",
  }),
  columnHelper.accessor("definition", {
    cell: (info) => {
      const value = info.getValue();
      if (!value) return <span className="text-gray-400">No definition</span>;
      // Truncate long definitions with ellipsis
      const truncated =
        value.length > 100 ? value.substring(0, 100) + "..." : value;
      return (
        <span title={value} className="cursor-help">
          {truncated}
        </span>
      );
    },
    header: () => "Definition",
  }),
  columnHelper.accessor("identifier", {
    cell: (info) => (
      <code className="rounded bg-gray-100 px-2 py-1 text-sm dark:bg-gray-800">
        {info.getValue() ?? ""}
      </code>
    ),
    header: () => "Identifier",
  }),
  columnHelper.accessor("date_created", {
    cell: (info) => {
      const value = info.getValue();
      return value !== null && value !== undefined
        ? renderShortDateTime(value)
        : "";
    },
    header: () => "Created",
  }),
  columnHelper.accessor("date_modified", {
    cell: (info) => {
      const value = info.getValue();
      return value !== null && value !== undefined
        ? renderShortDateTime(value)
        : "";
    },
    header: () => "Modified",
  }),
];

export interface PredicatesTableProps {
  data?: PredicateOut[];
  onSelectionChange?: (count: number) => void;
  onEdit?: (id: string) => void;
  columnVisibility?: Record<string, boolean>;
}

 
const PredicatesTable = React.forwardRef<any, PredicatesTableProps>((props) => {
  const { data: predicates, isLoading, error, refetch } = usePredicates();
  const deletePredicate = useDeletePredicate();

  // Default hidden columns: id, mapping, date_created, date_modified
  const defaultColumnVisibility: Record<string, boolean> = {
    id: false,
    mapping: false,
    date_created: false,
    date_modified: false,
  };
  const columnVisibility = {
    ...defaultColumnVisibility,
    ...props.columnVisibility,
  };

  return (
    <BaseNodeTable
      columns={columns}
      data={predicates?.data ?? []}
      isLoading={isLoading}
      error={error}
      onRefetch={refetch}
      onDelete={async (ids: string[]) => {
        await Promise.all(ids.map((id) => deletePredicate.mutateAsync(id)));
      }}
      createForm={({ onSuccess }) => <PredicateForm onSuccess={onSuccess} />}
      editForm={({ node, onSuccess }) => (
        <PredicateForm predicate={node} onSuccess={onSuccess} />
      )}
      typeName="Predicate"
      getId={(item) => item.id}
      columnVisibility={columnVisibility}
      linkGenerator={(predicate: PredicateOut) =>
        `/app/nodes/predicate/${predicate.id}`
      }
    />
  );
});

export { PredicatesTable };
