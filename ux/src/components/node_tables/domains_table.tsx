import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox, Badge } from "flowbite-react";
import { StructureNode } from "@/api/types/structureNodes";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { BaseNodeTable } from "./node_table";
import {
  useDomainNodes,
  useTermNodes,
} from "@/api/hooks/structure_nodes/useStructureNodes";
import { useDeleteStructureNode } from "@/api/hooks/structure_nodes/useStructureNodeMutations";
import { DomainForm } from "@/components/forms/domain_form";
import { DomainMoveForm } from "@/components/forms/domain_move_form";
import { usePredicates } from "@/api/hooks/predicates";
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
    header: () => "Layer",
  }),
  columnHelper.accessor("structural_predicate_id", {
    cell: (info) => {
      const value = info.getValue();
      return value ? (
        renderShortUuid(value)
      ) : (
        <span className="text-gray-400">None</span>
      );
    },
    header: () => "Structural Predicate",
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

// Define filter fields for domains
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
    label: "Layer",
    type: "select",
    operators: ["equals"],
    // TODO: Populate this from the structure nodes API
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

export interface DomainsTableProps {
  data?: StructureNode[];
  onSelectionChange?: (count: number) => void;
  onEdit?: (id: string) => void;
  columnVisibility?: Record<string, boolean>;
  queryParams?: Record<string, unknown>;
  onQueryParamsChange?: (params: Record<string, unknown>) => void;
}

const DomainsTable = React.forwardRef<any, DomainsTableProps>((props, ref) => {
  const { queryParams = {}, onQueryParamsChange } = props;

  // Use query params in the domains hook
  const {
    data: domains,
    isLoading,
    error,
    refetch,
  } = useDomainNodes(
    queryParams?.parent_node_id as string | undefined,
    queryParams,
  );
  const deleteDomain = useDeleteStructureNode();
  const { data: allTerms } = useTermNodes();

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

  // Get terms that belong to a domain (for safe deletion)
  const getDomainsChildren = async (domainId: string) => {
    if (!allTerms) return [];
    return allTerms.filter((term) => term.parent_node_id === domainId);
  };

  // Move terms when orphaning them during domain deletion
  const moveDomainsChildren = async (
    childIds: string[],
    newParentId: string | null,
  ) => {
    if (childIds.length === 0) return;

    // For domain deletion, we need to move terms to another domain or orphan them
    // Since we can't have terms without domains, we'll need to handle this differently
    // For now, this will be implemented when we have a better strategy
    console.warn(
      "Moving domain children not yet implemented - terms need a domain",
    );
  };

  return (
    <BaseNodeTable
      columns={columns}
      data={(domains ?? []) as StructureNode[]}
      isLoading={isLoading}
      error={error}
      onRefetch={refetch}
      onDelete={async (ids: string[]) => {
        await Promise.all(ids.map((id) => deleteDomain.mutateAsync(id)));
      }}
      createForm={({ onSuccess }) => <DomainForm onSuccess={onSuccess} />}
      editForm={({ node, onSuccess }) => (
        <DomainForm domain={node as StructureNode} onSuccess={onSuccess} />
      )}
      moveForm={DomainMoveForm}
      typeName="Domain"
      getId={(item) => item.id}
      columnVisibility={columnVisibility}
      queryParams={queryParams}
      onQueryParamsChange={onQueryParamsChange}
      filterFields={domainFilterFields}
      searchPlaceholder="Search..."
      linkGenerator={(item: StructureNode) => `/app/structure_nodes/${item.id}`}
      onGetChildren={getDomainsChildren}
      onMoveChildren={moveDomainsChildren}
    />
  );
});

export { DomainsTable };
