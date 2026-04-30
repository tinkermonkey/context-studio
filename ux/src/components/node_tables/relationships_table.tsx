import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import type { Relationship } from "@/api/types/ontology";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import {
  useRelationships,
  useDeleteRelationship,
} from "@/api/hooks/relationships";
import { BaseNodeTable } from "./node_table";

const columnHelper = createColumnHelper<Relationship>();

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
              rows.forEach((row) => row.toggleSelected(false));
            } else {
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
  columnHelper.accessor("source_id", {
    cell: (info) => (info.getValue() ? renderShortUuid(info.getValue()) : "-"),
    header: () => "Source ID",
  }),
  columnHelper.accessor("target_id", {
    cell: (info) => (info.getValue() ? renderShortUuid(info.getValue()) : "-"),
    header: () => "Target ID",
  }),
  columnHelper.accessor("property_definition_id", {
    cell: (info) => (info.getValue() ? renderShortUuid(info.getValue()) : "-"),
    header: () => "Property Definition ID",
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

export interface RelationshipsTableProps {
  data?: Relationship[];
  onSelectionChange?: (count: number) => void;
  columnVisibility?: Record<string, boolean>;
}

const RelationshipsTable = React.forwardRef<any, RelationshipsTableProps>(
  (props) => {
    const {
      data: relationships,
      isLoading,
      error,
      refetch,
    } = useRelationships();
    const deleteRelationship = useDeleteRelationship();

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
        data={relationships ?? []}
        isLoading={isLoading}
        error={error}
        onRefetch={refetch}
        onDelete={async (ids: string[]) => {
          await Promise.all(
            ids.map((id) => deleteRelationship.mutateAsync(id)),
          );
        }}
        createForm={({ onSuccess: _onSuccess }) => (
          <div className="p-4">
            <p className="text-gray-600">
              Create relationship functionality coming soon
            </p>
          </div>
        )}
        editForm={({ node: _node, onSuccess: _onSuccess }) => (
          <div className="p-4">
            <p className="text-gray-600">
              Edit relationship functionality coming soon
            </p>
          </div>
        )}
        typeName="Relationship"
        getId={(item) => item.id}
        columnVisibility={columnVisibility}
      />
    );
  },
);

export { RelationshipsTable };
