import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import { TermOut } from "@/api/services/terms";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { Term } from "@/components/nodes/term";
import { BaseNodeTable } from "./node_table";
import { useTerms } from "@/api/hooks/terms";
import { useDeleteTerm } from "@/api/hooks/terms";
import { TermForm } from "@/components/forms/term_form";
import type { FieldDefinition } from "@/components/misc/query_filters";

const columnHelper = createColumnHelper<TermOut>();

const columns = [
  columnHelper.display({
    id: "select",
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
  columnHelper.accessor("domain_id", {
    cell: (info) => renderShortUuid(info.getValue() ?? ""),
    header: () => "Domain",
  }),
  columnHelper.accessor("layer_id", {
    cell: (info) => {
      const value = info.getValue() ?? "";
      return value ? renderShortUuid(value) : "";
    },
    header: () => "Layer",
  }),
  columnHelper.accessor("parent_term_id", {
    cell: (info) => {
      const value = info.getValue() ?? "";
      return value ? <Term term_id={value} /> : "";
    },
    header: () => "Parent Term",
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
    field: "layer_id",
    label: "Layer",
    type: "select",
    operators: ["equals"],
    // TODO: Populate this from the layers API and use the LayerSelector component
    options: [
      { value: "layer1", label: "Layer 1" },
      { value: "layer2", label: "Layer 2" },
    ],
  },
  {
    field: "domain_id",
    label: "Domain",
    type: "select",
    operators: ["equals"],
    // TODO: Populate this from the domains API and use the DomainSelector component
    options: [
      { value: "domain1", label: "Domain 1" },
      { value: "domain2", label: "Domain 2" },
    ],
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
  data?: TermOut[];
  onSelectionChange?: (count: number) => void;
  onEdit?: (id: string) => void;
  columnVisibility?: Record<string, boolean>;
  queryParams?: Record<string, unknown>;
  onQueryParamsChange?: (params: Record<string, unknown>) => void;
}

const TermsTable = React.forwardRef<any, TermsTableProps>((props, ref) => {
  const { 
    queryParams = {}, 
    onQueryParamsChange 
  } = props;
  
  // Use query params in the terms hook
  const { data: terms, isLoading, error, refetch } = useTerms(queryParams);
  const deleteTerm = useDeleteTerm();

  const defaultColumnVisibility: Record<string, boolean> = {
    id: false,
    domain_id: false,
    layer_id: false,
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
      data={terms ?? []}
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
      typeName="Term"
      getId={(item) => item.id}
      columnVisibility={columnVisibility}
      queryParams={queryParams}
      onQueryParamsChange={onQueryParamsChange}
      filterFields={domainFilterFields}
      searchPlaceholder="Search..."
    />
  );
});

export { TermsTable };
