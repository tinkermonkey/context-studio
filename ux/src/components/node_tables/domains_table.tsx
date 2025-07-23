
import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import { DomainOut } from "@/api/services/domains";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { BaseNodeTable } from './node_table';
import { useDomains } from '@/api/hooks/domains';
import { useDeleteDomain } from '@/api/hooks/domains';
import { DomainForm } from '@/components/forms/domain_form';

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


export interface DomainsTableProps {
  data?: DomainOut[];
  onSelectionChange?: (count: number) => void;
  onEdit?: (id: string) => void;
  columnVisibility?: Record<string, boolean>;
}




const DomainsTable = React.forwardRef<any, DomainsTableProps>((props, ref) => {
  const { data: domains, isLoading, error, refetch } = useDomains();
  const deleteDomain = useDeleteDomain();
  
  // Default hidden columns: id, layer_id, version, created_at, last_modified
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
    />
  );
});

export { DomainsTable };
