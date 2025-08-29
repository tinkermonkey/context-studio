
import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Checkbox, Badge, Tooltip } from "flowbite-react";
import { Info } from "lucide-react";
import { DomainOut } from "@/api/services/domains";
import { renderShortDateTime, renderShortUuid } from "@/utils/renderers";
import { BaseNodeTable } from './node_table';
import { useDomains } from '@/api/hooks/domains';
import { useDeleteDomain } from '@/api/hooks/domains';
import { DomainForm } from '@/components/forms/domain_form';
import { DomainMoveForm } from '@/components/forms/domain_move_form';
import { useTerms } from '@/api/hooks/terms';
import { useMoveTerms } from '@/api/hooks/terms';
import { usePredicates } from '@/api/hooks/predicates';
import type { FieldDefinition } from "@/components/misc/query_filters";

const columnHelper = createColumnHelper<DomainOut>();

const columns = [
  columnHelper.display({
    id: 'select',
    header: ({ table }) => {
      const { rows } = table.getRowModel();
      const selectedCount = rows.filter(row => row.getIsSelected()).length;
      const isAllSelected = rows.length > 0 && selectedCount === rows.length;
      const isSomeSelected = selectedCount > 0 && selectedCount < rows.length;
      
      return (
        <Checkbox
          checked={isAllSelected}
          indeterminate={isSomeSelected}
          onChange={() => {
            if (isAllSelected || isSomeSelected) {
              // Deselect all visible rows
              rows.forEach(row => row.toggleSelected(false));
            } else {
              // Select all visible rows
              rows.forEach(row => row.toggleSelected(true));
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
  columnHelper.accessor("primary_predicate", {
    cell: (info) => {
      const value = info.getValue();
      return value ? (
        <Badge color="blue" size="sm">
          {value}
        </Badge>
      ) : (
        <span className="text-gray-400">None</span>
      );
    },
    header: () => "Structural Predicate",
  }),
  columnHelper.accessor("predicate_set", {
    cell: (info) => {
      const predicateSet = info.getValue();
      const primaryPredicate = info.row.original.primary_predicate;
      
      if (!predicateSet || predicateSet.length === 0) {
        return <span className="text-gray-400">None</span>;
      }
      
      return (
        <div className="flex flex-wrap gap-1">
          {/* Show primary predicate first with special styling if it exists */}
          {primaryPredicate && (
            <Badge color="blue" size="sm">
              {primaryPredicate}
            </Badge>
          )}
          
          {/* Show count of additional predicates */}
          {predicateSet.length > 1 && (
            <Badge color="gray" size="sm">
              +{predicateSet.length - 1} more
            </Badge>
          )}
          
          {/* Tooltip with full list on hover */}
          {predicateSet.length > 1 && (
            <Tooltip content={
              <div>
                <p className="font-medium">All Predicates:</p>
                <ul className="mt-1">
                  {predicateSet.map((id: string) => (
                    <li key={id}>• {id}</li>
                  ))}
                </ul>
              </div>
            }>
              <Info className="h-3 w-3 text-gray-400 ml-1" />
            </Tooltip>
          )}
        </div>
      );
    },
    header: () => "Predicates",
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
  const { data: allTerms } = useTerms();
  const moveTerms = useMoveTerms();
  
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

  // Get terms that belong to a domain (for safe deletion)
  const getDomainsChildren = async (domainId: string) => {
    if (!allTerms) return [];
    return allTerms.filter(term => term.domain_id === domainId);
  };

  // Move terms when orphaning them during domain deletion
  const moveDomainsChildren = async (childIds: string[], newParentId: string | null) => {
    if (childIds.length === 0) return;
    
    // For domain deletion, we need to move terms to another domain or orphan them
    // Since we can't have terms without domains, we'll need to handle this differently
    // For now, this will be implemented when we have a better strategy
    console.warn('Moving domain children not yet implemented - terms need a domain');
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
      moveForm={DomainMoveForm}
      typeName="Domain"
      getId={(item) => item.id}
      columnVisibility={columnVisibility}
      queryParams={queryParams}
      onQueryParamsChange={onQueryParamsChange}
      filterFields={domainFilterFields}
      searchPlaceholder="Search..."
      linkGenerator={(domain: DomainOut) => `/app/nodes/domain/${domain.id}`}
      onGetChildren={getDomainsChildren}
      onMoveChildren={moveDomainsChildren}
    />
  );
});

export { DomainsTable };
