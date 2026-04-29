/**
 * Property Definitions Table Component
 *
 * Table for displaying and managing property definitions
 */

import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import type { PropertyDefinition } from "@/api/types/ontology";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { usePropertyDefinitions } from "@/api/hooks/propertyDefinitions";
import { useDeletePropertyDefinition } from "@/api/hooks/propertyDefinitions";
import { PropertyDefinitionForm } from "@/components/forms/property_definition_form";
import { BaseNodeTable } from "./node_table";

const columnHelper = createColumnHelper<PropertyDefinition>();

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
      // Truncate long descriptions with ellipsis
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
  columnHelper.accessor("range", {
    cell: (info) => info.getValue() ?? "-",
    header: () => "Range",
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

export interface PropertiesTableProps {
  data?: PropertyDefinition[];
  onSelectionChange?: (count: number) => void;
  onEdit?: (id: string) => void;
  columnVisibility?: Record<string, boolean>;
}

const PropertiesTable = React.forwardRef<any, PropertiesTableProps>((props) => {
  const {
    data: properties,
    isLoading,
    error,
    refetch,
  } = usePropertyDefinitions();
  const deleteProperty = useDeletePropertyDefinition();

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
      data={properties ?? []}
      isLoading={isLoading}
      error={error}
      onRefetch={refetch}
      onDelete={async (ids: string[]) => {
        await Promise.all(ids.map((id) => deleteProperty.mutateAsync(id)));
      }}
      createForm={({ onSuccess }) => (
        <PropertyDefinitionForm onSuccess={onSuccess} />
      )}
      editForm={({ node, onSuccess }) => (
        <PropertyDefinitionForm
          propertyDefinition={node}
          onSuccess={onSuccess}
        />
      )}
      typeName="Property Definition"
      getId={(item) => item.id}
      columnVisibility={columnVisibility}
      linkGenerator={(propertyDefinition: PropertyDefinition) =>
        `/app/properties/${propertyDefinition.id}`
      }
    />
  );
});

export { PropertiesTable };
