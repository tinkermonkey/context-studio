import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import { StructureNode } from "@/api/types/structureNodes";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { BaseNodeTable } from "./node_table";
import { useOntologyClasses, useOntologyClass } from "@/api/hooks/ontologyClasses";
import { useDeleteStructureNode } from "@/api/hooks/structure_nodes/useStructureNodeMutations";
import { ClassForm } from "@/components/forms/class_form";
import { ClassMoveForm } from "@/components/forms/class_move_form";
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
    field: "parent_node_id",
    label: "Parent",
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
  data?: StructureNode[];
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
  } = useOntologyClasses(undefined, queryParams);
  const { data: allClasses } = useOntologyClasses(); // Get all classes for finding children
  const deleteClass = useDeleteStructureNode();

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

  // Get child classes for safe deletion workflow
  const getClassChildren = async (classId: string): Promise<StructureNode[]> => {
    if (!allClasses) return [];
    return (allClasses as StructureNode[]).filter(
      (ontologyClass) => ontologyClass.parent_node_id === classId,
    );
  };

  // Move child classes when orphaning them during parent deletion
  const moveClassChildren = async (
    childIds: string[],
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    newParentId: string | null,
  ) => {
    if (childIds.length === 0) return;

    // Find a target concept scheme for the orphaned classes
    // We'll use the concept scheme of the first child class since classes must belong to a concept scheme
    const firstChild = allClasses?.find((ontologyClass) => childIds.includes(ontologyClass.id));
    if (!firstChild) return;

    // For orphaning, we need to use the structure node update API to set parent_node_id to null
    // Since we don't have a bulk move API, we update each class individually
    // This is a limitation we'll need to address in a future update
    console.warn(
      "Class orphaning not fully implemented - using move to same concept scheme for now",
    );

    // TODO: Implement class moving with new ontology API
    // await updateOntologyClass for each child class to change parent_node_id
    console.warn(
      "Class moving needs to be reimplemented with ontology API",
    );
  };

  return (
    <BaseNodeTable
      columns={columns}
      data={(classes ?? []) as StructureNode[]}
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
      linkGenerator={(ontologyClass: StructureNode) => `/app/classes/${ontologyClass.id}`}
      onGetChildren={getClassChildren}
      onMoveChildren={moveClassChildren}
    />
  );
});

export { ClassesTable };
