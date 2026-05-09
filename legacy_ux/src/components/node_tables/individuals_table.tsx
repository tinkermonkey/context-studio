import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox } from "flowbite-react";
import type { components } from "@/api/client/types";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { BaseNodeTable } from "./node_table";
import { useIndividuals, useDeleteIndividual } from "@/api/hooks/individuals";
import { IndividualForm } from "@/components/forms/individual_form";
import type { FieldDefinition } from "@/components/misc/query_filters";

type IndividualResponse = components["schemas"]["IndividualResponse"];

const columnHelper = createColumnHelper<IndividualResponse>();

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
  columnHelper.accessor("class_ids", {
    cell: (info) => {
      const classIds = info.getValue() ?? [];
      return classIds.length > 0 ? `${classIds.length} class(es)` : "-";
    },
    header: () => "Parent Classes",
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

// Define filter fields for individuals
const individualFilterFields: FieldDefinition[] = [
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

export interface IndividualsTableProps {
  data?: IndividualResponse[];
  onSelectionChange?: (count: number) => void;
  onEdit?: (id: string) => void;
  columnVisibility?: Record<string, boolean>;
  queryParams?: Record<string, unknown>;
  onQueryParamsChange?: (params: Record<string, unknown>) => void;
}

const IndividualsTable = React.forwardRef<any, IndividualsTableProps>(
  (props) => {
    const { queryParams = {}, onQueryParamsChange } = props;

    const {
      data: individuals,
      isLoading,
      error,
      refetch,
    } = useIndividuals(queryParams as any);
    const deleteIndividual = useDeleteIndividual();

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
        data={individuals ?? []}
        isLoading={isLoading}
        error={error}
        onRefetch={refetch}
        onDelete={async (ids: string[]) => {
          await Promise.all(ids.map((id) => deleteIndividual.mutateAsync(id)));
        }}
        createForm={({ onSuccess }) => <IndividualForm onSuccess={onSuccess} />}
        editForm={({ node, onSuccess }) => (
          <IndividualForm individual={node} onSuccess={onSuccess} />
        )}
        typeName="Individual"
        getId={(item) => item.id}
        columnVisibility={columnVisibility}
        queryParams={queryParams}
        onQueryParamsChange={onQueryParamsChange}
        filterFields={individualFilterFields}
        searchPlaceholder="Search individuals..."
        linkGenerator={(individual: IndividualResponse) =>
          `/app/individuals/${individual.id}`
        }
      />
    );
  },
);

export { IndividualsTable };
