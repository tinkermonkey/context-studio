import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import { StructureNode } from "@/api/types/structureNodes";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { BaseNodeTable } from "./node_table";
import { useTermNodes } from "@/api/hooks/structure_nodes/useStructureNodes";
import { useDeleteStructureNode } from "@/api/hooks/structure_nodes/useStructureNodeMutations";
import { TermForm } from "@/components/forms/term_form";
import { TermMoveForm } from "@/components/forms/term_move_form";
import type { FieldDefinition } from "@/components/misc/query_filters";

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
  columnHelper.accessor("parent_node_id", {
    cell: (info) => {
      const value = info.getValue() ?? "";
      return value ? renderShortUuid(value) : "";
    },
    header: () => "Parent",
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

// Define filter fields for terms
const domainFilterFields: FieldDefinition[] = [
  {
    field: "title",
    label: "Title",
    type: "text",
    operators: ["equals", "contains", "starts_with", "ends_with"],
  },
  {
    field: "definition",
    label: "Definition",
    type: "text",
    operators: ["contains"],
  },
  {
    field: "parent_node_id",
    label: "Parent",
    type: "select",
    operators: ["equals"],
    // TODO: Populate this from structure nodes API
    options: [],
  },
  {
    field: "created_at",
    label: "Created Date",
    type: "date",
    operators: ["gte", "lte", "between"],
  },
  {
    field: "last_modified",
    label: "Date Modified",
    type: "date",
    operators: ["gte", "lte", "between"],
  },
];

export interface TermsTableProps {
  data?: StructureNode[];
  onSelectionChange?: (count: number) => void;
  onEdit?: (id: string) => void;
  columnVisibility?: Record<string, boolean>;
  queryParams?: Record<string, unknown>;
  onQueryParamsChange?: (params: Record<string, unknown>) => void;
}

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
const TermsTable = React.forwardRef<any, TermsTableProps>((props) => {
  const { queryParams = {}, onQueryParamsChange } = props;

  // Use query params in the terms hook
  const {
    data: terms,
    isLoading,
    error,
    refetch,
  } = useTermNodes(undefined, queryParams);
  const { data: allTerms } = useTermNodes(); // Get all terms for finding children
  const deleteTerm = useDeleteStructureNode();

  const defaultColumnVisibility: Record<string, boolean> = {
    id: false,
    parent_node_id: false,
    version: false,
    created_at: false,
    last_modified: false,
  };
  const columnVisibility = {
    ...defaultColumnVisibility,
    ...props.columnVisibility,
  };

  // Get child terms for safe deletion workflow
  const getTermChildren = async (termId: string): Promise<StructureNode[]> => {
    if (!allTerms) return [];
    return (allTerms as StructureNode[]).filter(
      (term) => term.parent_node_id === termId,
    );
  };

  // Move child terms when orphaning them during parent deletion
  const moveTermChildren = async (
    childIds: string[],
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    newParentId: string | null,
  ) => {
    if (childIds.length === 0) return;

    // Find a target domain for the orphaned terms
    // We'll use the domain of the first child term since terms must belong to a domain
    const firstChild = allTerms?.find((term) => childIds.includes(term.id));
    if (!firstChild) return;

    // For orphaning, we need to use the structure node update API to set parent_node_id to null
    // Since we don't have a bulk move API, we update each term individually
    // This is a limitation we'll need to address in a future update
    console.warn(
      "Term orphaning not fully implemented - using move to same domain for now",
    );

    // TODO: Implement term moving with new structure node API
    // await updateStructureNode for each child term to change parent_node_id
    console.warn(
      "Term moving needs to be reimplemented with structure node API",
    );
  };

  return (
    <BaseNodeTable
      columns={columns}
      data={(terms ?? []) as StructureNode[]}
      isLoading={isLoading}
      error={error}
      onRefetch={refetch}
      onDelete={async (ids: string[]) => {
        await Promise.all(ids.map((id) => deleteTerm.mutateAsync(id)));
      }}
      createForm={({ onSuccess }) => <TermForm onSuccess={onSuccess} />}
      editForm={({ node, onSuccess }) => (
        <TermForm term={node} onSuccess={onSuccess} />
      )}
      moveForm={TermMoveForm}
      typeName="Term"
      getId={(item) => item.id}
      columnVisibility={columnVisibility}
      queryParams={queryParams}
      onQueryParamsChange={onQueryParamsChange}
      filterFields={domainFilterFields}
      searchPlaceholder="Search..."
      linkGenerator={(term: StructureNode) => `/app/structure_nodes/${term.id}`}
      onGetChildren={getTermChildren}
      onMoveChildren={moveTermChildren}
    />
  );
});

export { TermsTable };
