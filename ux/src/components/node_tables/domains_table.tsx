
import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import { DomainOut } from "@/api/services/domains";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { BaseNodeTable } from './node_table';
import { useDomains } from '@/api/hooks/domains';
import { useDeleteDomain } from '@/api/hooks/domains';
import { DomainForm } from '@/components/forms/domain_form';
import type { FieldDefinition } from "@/components/misc/query_filters";

const columnHelper = createColumnHelper<DomainOut>();

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


// Define filter fields for domains
const domainFilterFields: FieldDefinition[] = [
  {
    field: 'title',
    label: 'Title',
    type: 'text',
    operators: ['equals', 'contains', 'starts_with', 'ends_with'],
  },
  {
    field: 'definition',
    label: 'Definition',
    type: 'text',
    operators: ['contains'],
  },
  {
    field: 'layer_id',
    label: 'Layer',
    type: 'select',
    operators: ['equals'],
    // TODO: Populate this from the layers API and use the LayerSelector component
    options: [
      { value: 'layer1', label: 'Layer 1' },
      { value: 'layer2', label: 'Layer 2' },
    ],
  },
  {
    field: 'created_at',
    label: 'Created Date',
    type: 'date',
    operators: ['gte', 'lte', 'between'],
  },
  {
    field: 'last_modified',
    label: 'Date Modified',
    type: 'date',
    operators: ['gte', 'lte', 'between'],
  },
];

export interface DomainsTableProps {
  data?: DomainOut[];
  onSelectionChange?: (count: number) => void;
  onEdit?: (id: string) => void;
  columnVisibility?: Record<string, boolean>;
  queryParams?: Record<string, unknown>;
  onQueryParamsChange?: (params: Record<string, unknown>) => void;
}

const DomainsTable = React.forwardRef<any, DomainsTableProps>((props, ref) => {
  const { 
    queryParams = {}, 
    onQueryParamsChange 
  } = props;
  
  // Use query params in the domains hook
  const { data: domains, isLoading, error, refetch } = useDomains(queryParams);
  const deleteDomain = useDeleteDomain();
  
  const defaultColumnVisibility: Record<string, boolean> = {
    id: false,
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
      data={domains ?? []}
      isLoading={isLoading}
      error={error}
      onRefetch={refetch}
      onDelete={async (ids: string[]) => {
        await Promise.all(ids.map((id) => deleteDomain.mutateAsync(id)));
      }}
      createForm={({ onSuccess }) => <DomainForm onSuccess={onSuccess} />}
      editForm={({ node, onSuccess }) => <DomainForm domain={node} onSuccess={onSuccess} />}
      typeName="Domain"
      getId={(item) => item.id}
      columnVisibility={columnVisibility}
      queryParams={queryParams}
      onQueryParamsChange={onQueryParamsChange}
      filterFields={domainFilterFields}
      searchPlaceholder="Search..."
    />
  );
});

export { DomainsTable };
