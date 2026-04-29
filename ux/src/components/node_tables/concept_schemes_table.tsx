import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import type { ConceptScheme } from "@/api/types/ontology";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { BaseNodeTable } from "./node_table";
import {
  useConceptSchemes,
  useDeleteConceptScheme,
} from "@/api/hooks/conceptSchemes";
import { ConceptSchemeForm } from "@/components/forms/concept_scheme_form";
import { ConceptSchemeMoveForm } from "@/components/forms/concept_scheme_move_form";
import type { FieldDefinition } from "@/components/misc/query_filters";

const columnHelper = createColumnHelper<ConceptScheme>();

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
  columnHelper.accessor("taxonomy_id", {
    cell: (info) => {
      const value = info.getValue() ?? "";
      return value ? renderShortUuid(value) : "";
    },
    header: () => "Taxonomy",
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
    field: "description",
    label: "Description",
    type: "text",
    operators: ["contains"],
  },
  {
    field: "taxonomy_id",
    label: "Taxonomy",
    type: "select",
    operators: ["equals"],
    // TODO: Populate this from the taxonomies API
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
  data?: ConceptScheme[];
  onSelectionChange?: (count: number) => void;
  onEdit?: (id: string) => void;
  columnVisibility?: Record<string, boolean>;
  queryParams?: Record<string, unknown>;
  onQueryParamsChange?: (params: Record<string, unknown>) => void;
}

const ConceptSchemesTable = React.forwardRef<any, ConceptSchemesTableProps>(
  (props) => {
    const { queryParams = {}, onQueryParamsChange } = props;

    // Use query params in the concept schemes hook
    const {
      data: conceptSchemes,
      isLoading,
      error,
      refetch,
    } = useConceptSchemes(queryParams as any);
    const deleteConceptScheme = useDeleteConceptScheme();

    const defaultColumnVisibility: Record<string, boolean> = {
      id: false,
      taxonomy_id: false,
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
        data={conceptSchemes ?? []}
        isLoading={isLoading}
        error={error}
        onRefetch={refetch}
        onDelete={async (ids: string[]) => {
          await Promise.all(
            ids.map((id) => deleteConceptScheme.mutateAsync(id)),
          );
        }}
        createForm={({ onSuccess }) => (
          <ConceptSchemeForm onSuccess={onSuccess} />
        )}
        editForm={({ node, onSuccess }) => (
          <ConceptSchemeForm conceptScheme={node} onSuccess={onSuccess} />
        )}
        moveForm={ConceptSchemeMoveForm}
        typeName="Concept Scheme"
        getId={(item) => item.id}
        columnVisibility={columnVisibility}
        queryParams={queryParams}
        onQueryParamsChange={onQueryParamsChange}
        filterFields={conceptSchemeFilterFields}
        searchPlaceholder="Search..."
        linkGenerator={(item: ConceptScheme) =>
          `/app/concept-schemes/${item.id}`
        }
      />
    );
  },
);

export { ConceptSchemesTable };
