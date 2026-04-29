import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import type { Taxonomy } from "@/api/types/ontology";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { useTaxonomies, useDeleteTaxonomy } from "@/api/hooks/taxonomies";
import { TaxonomyForm } from "@/components/forms/taxonomy_form";
import { BaseNodeTable } from "./node_table";

const columnHelper = createColumnHelper<Taxonomy>();

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
  columnHelper.accessor("description", {
    cell: (info) => {
      const value = info.getValue();
      if (!value) return <span className="text-gray-400">No description</span>;
      const truncated =
        value.length > 100 ? value.substring(0, 100) + "..." : value;
      return (
        <span title={value} className="cursor-help">
          {truncated}
        </span>
      );
    },
    header: () => "Description",
  }),
  columnHelper.accessor("created_at", {
    cell: (info) => {
      const value = info.getValue();
      return value !== null && value !== undefined
        ? renderShortDateTime(value)
        : "";
    },
    header: () => "Created",
  }),
  columnHelper.accessor("last_modified", {
    cell: (info) => {
      const value = info.getValue();
      return value !== null && value !== undefined
        ? renderShortDateTime(value)
        : "";
    },
    header: () => "Modified",
  }),
];

export interface TaxonomiesTableProps {
  data?: Taxonomy[];
  onSelectionChange?: (count: number) => void;
  onEdit?: (id: string) => void;
  columnVisibility?: Record<string, boolean>;
}


const TaxonomiesTable = React.forwardRef<any, TaxonomiesTableProps>((props, ref) => {
  const { data: taxonomies, isLoading, error, refetch } = useTaxonomies();
  const deleteTaxonomy = useDeleteTaxonomy();

  // Default hidden columns: id, created_at, last_modified
  const defaultColumnVisibility: Record<string, boolean> = {
    id: false,
    created_at: false,
    last_modified: false,
  };
  const columnVisibility = {
    ...defaultColumnVisibility,
    ...props.columnVisibility,
  };

  return (
    <BaseNodeTable
      columns={columns}
      data={taxonomies ?? []}
      isLoading={isLoading}
      error={error}
      onRefetch={refetch}
      onDelete={async (ids: string[]) => {
        await Promise.all(ids.map((id) => deleteTaxonomy.mutateAsync(id)));
      }}
      createForm={({ onSuccess }) => <TaxonomyForm onSuccess={onSuccess} />}
      editForm={({ node, onSuccess }) => (
        <TaxonomyForm taxonomy={node} onSuccess={onSuccess} />
      )}
      typeName="Taxonomy"
      getId={(item) => item.id}
      columnVisibility={columnVisibility}
      linkGenerator={(taxonomy: Taxonomy) =>
        `/app/taxonomies/${taxonomy.id}`
      }
    />
  );
});

export { TaxonomiesTable };
