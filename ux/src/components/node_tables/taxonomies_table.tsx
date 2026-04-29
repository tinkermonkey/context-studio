import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import { StructureNode } from "@/api/types/structureNodes";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { useTaxonomies } from "@/api/hooks/taxonomies";
import { useDeleteStructureNode } from "@/api/hooks/structure_nodes/useStructureNodeMutations";
import { TaxonomyForm } from "@/components/forms/taxonomy_form";
import { BaseNodeTable } from "./node_table";

const columnHelper = createColumnHelper<StructureNode>();

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
    cell: (info) => info.getValue() ?? "",
    header: () => "Definition",
  }),
  columnHelper.accessor("version", {
    cell: (info) => info.getValue() ?? "",
    header: () => "Version",
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
  data?: StructureNode[];
  onSelectionChange?: (count: number) => void;
  onEdit?: (id: string) => void;
  columnVisibility?: Record<string, boolean>;
}


const TaxonomiesTable = React.forwardRef<any, TaxonomiesTableProps>((props) => {
  const { data: taxonomies, isLoading, error, refetch } = useTaxonomies();
  const deleteTaxonomy = useDeleteStructureNode();

  // Default hidden columns: id, version, created_at, last_modified
  const defaultColumnVisibility: Record<string, boolean> = {
    id: false,
    version: false,
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
      data={(taxonomies ?? []) as StructureNode[]}
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
      linkGenerator={(taxonomy: StructureNode) =>
        `/app/taxonomies/${taxonomy.id}`
      }
    />
  );
});

export { TaxonomiesTable };
