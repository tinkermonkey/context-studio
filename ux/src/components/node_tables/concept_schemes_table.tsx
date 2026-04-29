import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import { StructureNode } from "@/api/types/structureNodes";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { BaseNodeTable } from "./node_table";
import { useConceptSchemes } from "@/api/hooks/conceptSchemes";
import { useOntologyClasses } from "@/api/hooks/ontologyClasses";
import { useDeleteStructureNode } from "@/api/hooks/structure_nodes/useStructureNodeMutations";
import { ConceptSchemeForm } from "@/components/forms/concept_scheme_form";
import { ConceptSchemeMoveForm } from "@/components/forms/concept_scheme_move_form";
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
    header: () => "Taxonomy",
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
    header: () => "Structural Property",
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

// Define filter fields for concept schemes
const conceptSchemeFilterFields: FieldDefinition[] = [
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
    label: "Taxonomy",
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

export interface ConceptSchemesTableProps {
  data?: StructureNode[];
  onSelectionChange?: (count: number) => void;
  onEdit?: (id: string) => void;
  columnVisibility?: Record<string, boolean>;
  queryParams?: Record<string, unknown>;
  onQueryParamsChange?: (params: Record<string, unknown>) => void;
}


const ConceptSchemesTable = React.forwardRef<any, ConceptSchemesTableProps>((props) => {
  const { queryParams = {}, onQueryParamsChange } = props;

  // Use query params in the concept schemes hook
  const {
    data: conceptSchemes,
    isLoading,
    error,
    refetch,
  } = useConceptSchemes(
    queryParams?.parent_node_id as string | undefined,
    queryParams,
  );
  const deleteConceptScheme = useDeleteStructureNode();
  const { data: allClasses } = useOntologyClasses();

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

  // Get classes that belong to a concept scheme (for safe deletion)
  const getConceptSchemeChildren = async (conceptSchemeId: string) => {
    if (!allClasses) return [];
    return allClasses.filter((ontologyClass) => ontologyClass.parent_node_id === conceptSchemeId);
  };

  // Move classes when orphaning them during concept scheme deletion
  const moveConceptSchemeChildren = async (
    childIds: string[],
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    newParentId: string | null,
  ) => {
    if (childIds.length === 0) return;

    // For concept scheme deletion, we need to move classes to another concept scheme or orphan them
    // Since we can't have classes without concept schemes, we'll need to handle this differently
    // For now, this will be implemented when we have a better strategy
    console.warn(
      "Moving concept scheme children not yet implemented - classes need a concept scheme",
    );
  };

  return (
    <BaseNodeTable
      columns={columns}
      data={(conceptSchemes ?? []) as StructureNode[]}
      isLoading={isLoading}
      error={error}
      onRefetch={refetch}
      onDelete={async (ids: string[]) => {
        await Promise.all(ids.map((id) => deleteConceptScheme.mutateAsync(id)));
      }}
      createForm={({ onSuccess }) => <ConceptSchemeForm onSuccess={onSuccess} />}
      editForm={({ node, onSuccess }) => (
        <ConceptSchemeForm conceptScheme={node as StructureNode} onSuccess={onSuccess} />
      )}
      moveForm={ConceptSchemeMoveForm}
      typeName="Concept Scheme"
      getId={(item) => item.id}
      columnVisibility={columnVisibility}
      queryParams={queryParams}
      onQueryParamsChange={onQueryParamsChange}
      filterFields={conceptSchemeFilterFields}
      searchPlaceholder="Search..."
      linkGenerator={(item: StructureNode) => `/app/concept-schemes/${item.id}`}
      onGetChildren={getConceptSchemeChildren}
      onMoveChildren={moveConceptSchemeChildren}
    />
  );
});

export { ConceptSchemesTable };
