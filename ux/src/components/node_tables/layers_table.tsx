import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import { LayerOut } from "@/api/services/layers";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { useLayers } from '@/api/hooks/layers';
import { useDeleteLayer } from '@/api/hooks/layers';
import { LayerForm } from '@/components/forms/layer_form';
import { BaseNodeTable } from './node_table';

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
  columnVisibility?: Record<string, boolean>;
}


const LayersTable = React.forwardRef<any, LayersTableProps>((props, ref) => {
  const { data: layers, isLoading, error, refetch } = useLayers();
  const deleteLayer = useDeleteLayer();
  
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
      data={layers ?? []}
      isLoading={isLoading}
      error={error}
      onRefetch={refetch}
      onDelete={async (ids: string[]) => {
        await Promise.all(ids.map((id) => deleteLayer.mutateAsync(id)));
      }}
      createForm={({ onSuccess }) => <LayerForm onSuccess={onSuccess} />}
      editForm={({ node, onSuccess }) => <LayerForm layer={node} onSuccess={onSuccess} />}
      typeName="Layer"
      getId={(item) => item.id}
      columnVisibility={columnVisibility}
    />
  );
});

export { LayersTable };
