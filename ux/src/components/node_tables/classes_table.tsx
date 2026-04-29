import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import type { OntologyClass } from "@/api/types/ontology";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { BaseNodeTable } from "./node_table";
import { useOntologyClasses, useDeleteOntologyClass } from "@/api/hooks/ontologyClasses";
import { ClassForm } from "@/components/forms/class_form";
import { ClassMoveForm } from "@/components/forms/class_move_form";
import type { FieldDefinition } from "@/components/misc/query_filters";

const columnHelper = createColumnHelper<OntologyClass>();

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
    cell: (info) => {
      const value = info.getValue();
      if (!value) return <span className="text-gray-400">No definition</span>;
      const truncated =
        value.length > 100 ? value.substring(0, 100) + "..." : value;
      return (
        <span title={value} className="cursor-help">
          {truncated}
        </span>
      );
    },
    header: () => "Definition",
  }),
  columnHelper.accessor("parent_class_id", {
    cell: (info) => {
      const value = info.getValue() ?? "";
      return value ? renderShortUuid(value) : "-";
    },
    header: () => "Parent Class",
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

// Define filter fields for classes
const classFilterFields: FieldDefinition[] = [
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
    field: "parent_class_id",
    label: "Parent Class",
    type: "select",
    operators: ["equals"],
    // TODO: Populate this from ontology classes API
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

export interface ClassesTableProps {
  data?: OntologyClass[];
  onSelectionChange?: (count: number) => void;
  onEdit?: (id: string) => void;
  columnVisibility?: Record<string, boolean>;
  queryParams?: Record<string, unknown>;
  onQueryParamsChange?: (params: Record<string, unknown>) => void;
}


const ClassesTable = React.forwardRef<any, ClassesTableProps>((props) => {
  const { queryParams = {}, onQueryParamsChange } = props;

  // Use query params in the classes hook
  const {
    data: classes,
    isLoading,
    error,
    refetch,
  } = useOntologyClasses(queryParams as any);
  const deleteClass = useDeleteOntologyClass();

  const defaultColumnVisibility: Record<string, boolean> = {
    id: false,
    parent_class_id: false,
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
      data={classes ?? []}
      isLoading={isLoading}
      error={error}
      onRefetch={refetch}
      onDelete={async (ids: string[]) => {
        await Promise.all(ids.map((id) => deleteClass.mutateAsync(id)));
      }}
      createForm={({ onSuccess }) => <ClassForm onSuccess={onSuccess} />}
      editForm={({ node, onSuccess }) => (
        <ClassForm ontologyClass={node} onSuccess={onSuccess} />
      )}
      moveForm={ClassMoveForm}
      typeName="Class"
      getId={(item) => item.id}
      columnVisibility={columnVisibility}
      queryParams={queryParams}
      onQueryParamsChange={onQueryParamsChange}
      filterFields={classFilterFields}
      searchPlaceholder="Search..."
      linkGenerator={(ontologyClass: OntologyClass) => `/app/classes/${ontologyClass.id}`}
    />
  );
});

export { ClassesTable };
