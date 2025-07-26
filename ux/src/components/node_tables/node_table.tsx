import React from "react";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  getPaginationRowModel,
} from "@tanstack/react-table";
import {
  Table,
  TableHead,
  TableHeadCell,
  TableBody,
  TableRow,
  TableCell,
  Button,
  Badge,
  Spinner,
  Modal,
  ModalHeader,
  ModalBody,
  Dropdown,
  DropdownItem,
  TextInput,
  Pagination,
  Select,
} from "flowbite-react";
import { RefreshCcw, Plus, Search, ExternalLink } from "lucide-react";
import {
  QueryFilters,
  type QueryFilter,
  type FieldDefinition,
} from "@/components/misc/query_filters";

export interface BaseNodeTableProps<T> {
  columns: any[];
  data: T[];
  isLoading?: boolean;
  error?: unknown;
  onRefetch?: () => void;
  onDelete: (ids: string[]) => Promise<void>;
  createForm: React.ComponentType<{ onSuccess: () => void }>;
  editForm: React.ComponentType<{ node: T; onSuccess: () => void }>;
  typeName: string;
  getId: (item: T) => string;
  columnVisibility?: Record<string, boolean>;
  pageSizeOptions?: number[];
  defaultPageSize?: number;
  // Query criteria for filtering, searching, etc.
  queryParams?: Record<string, unknown>;
  onQueryParamsChange?: (params: Record<string, unknown>) => void;
  // Built-in search functionality
  searchEnabled?: boolean;
  searchPlaceholder?: string;
  onSearchChange?: (searchTerm: string) => void;
  // Advanced filtering
  filterFields?: FieldDefinition[];
  filtersEnabled?: boolean;
  // Link generation for external links
  linkGenerator?: (item: T) => string | null | undefined;
}

function BaseNodeTable<T>({
  columns,
  data,
  isLoading,
  error,
  onRefetch,
  onDelete,
  createForm: CreateForm,
  editForm: EditForm,
  typeName,
  getId,
  columnVisibility: propColumnVisibility,
  pageSizeOptions = [10, 20, 50, 100],
  defaultPageSize = 20,
  queryParams = {},
  onQueryParamsChange,
  searchEnabled = true,
  searchPlaceholder,
  onSearchChange,
  filterFields = [],
  filtersEnabled = false,
  linkGenerator,
}: BaseNodeTableProps<T>) {
  const [showCreateModal, setShowCreateModal] = React.useState(false);
  const [showDeleteModal, setShowDeleteModal] = React.useState(false);
  const [pendingDeleteRows, setPendingDeleteRows] = React.useState<any[]>([]);
  const [editNodeId, setEditNodeId] = React.useState<string | undefined>(
    undefined,
  );
  const [selectedCount, setSelectedCount] = React.useState(0);
  const tableRef = React.useRef<any>(null);
  const [columnVisibility, setColumnVisibility] = React.useState<
    Record<string, boolean>
  >({
    ...propColumnVisibility,
  });

  // Search state management
  const [searchTerm, setSearchTerm] = React.useState<string>(
    (queryParams?.query as string) || "",
  );

  // Update search term when queryParams change (e.g., from URL navigation)
  React.useEffect(() => {
    const newSearchTerm = (queryParams?.query as string) || "";
    if (searchTerm !== newSearchTerm) {
      setSearchTerm(newSearchTerm);
    }
  }, [queryParams?.query]);

  // Filter state management
  const [filters, setFilters] = React.useState<QueryFilter[]>(() => {
    const initialFilters: QueryFilter[] = [];
    Object.entries(queryParams).forEach(([key, value]) => {
      if (
        key !== "query" &&
        key !== "skip" &&
        key !== "limit" &&
        key !== "sort"
      ) {
        const fieldDef = filterFields.find((f) => f.field === key);
        if (fieldDef && value !== undefined && value !== null && value !== "") {
          initialFilters.push({
            field: key,
            operator: "equals",
            value: value as string | number,
            label: fieldDef.label,
          });
        }
      }
    });
    return initialFilters;
  });

  // Update filters when queryParams change (e.g., from URL navigation)
  React.useEffect(() => {
    const newFilters: QueryFilter[] = [];
    Object.entries(queryParams).forEach(([key, value]) => {
      if (
        key !== "query" &&
        key !== "skip" &&
        key !== "limit" &&
        key !== "sort"
      ) {
        const fieldDef = filterFields.find((f) => f.field === key);
        if (fieldDef && value !== undefined && value !== null && value !== "") {
          newFilters.push({
            field: key,
            operator: "equals",
            value: value as string | number,
            label: fieldDef.label,
          });
        }
      }
    });

    // Only update if filters actually changed
    const filtersChanged =
      filters.length !== newFilters.length ||
      filters.some(
        (f, i) =>
          !newFilters[i] ||
          f.field !== newFilters[i].field ||
          f.value !== newFilters[i].value ||
          f.operator !== newFilters[i].operator,
      );

    if (filtersChanged) {
      setFilters(newFilters);
    }
  }, [queryParams, filterFields]);

  // Debounced search to avoid excessive API calls
  const [debouncedSearchTerm, setDebouncedSearchTerm] =
    React.useState(searchTerm);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, 300); // 300ms debounce

    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Update query params when debounced search term changes
  // Only update if the search term actually changed from user input
  React.useEffect(() => {
    // Don't update on initial mount - only when user actually changes search
    if (debouncedSearchTerm === ((queryParams?.query as string) || "")) {
      return; // No change needed
    }

    if (onSearchChange) {
      onSearchChange(debouncedSearchTerm);
    } else if (onQueryParamsChange) {
      const newParams = { ...queryParams };
      if (debouncedSearchTerm.trim()) {
        newParams.query = debouncedSearchTerm.trim();
      } else {
        delete newParams.query;
      }
      onQueryParamsChange(newParams);
    }
  }, [debouncedSearchTerm, onSearchChange, onQueryParamsChange]);

  // Update query params when filters change
  // Only update if the filters actually changed from user input
  React.useEffect(() => {
    if (!onQueryParamsChange) return;

    // Check if current filters match what's in queryParams to avoid unnecessary updates
    const currentFilterParams: Record<string, unknown> = {};
    filters.forEach((filter) => {
      if (
        filter.value !== undefined &&
        filter.value !== null &&
        filter.value !== ""
      ) {
        if (filter.operator === "between" && Array.isArray(filter.value)) {
          const [min, max] = filter.value;
          if (min) currentFilterParams[`${filter.field}_min`] = min;
          if (max) currentFilterParams[`${filter.field}_max`] = max;
        } else if (filter.operator === "in" && Array.isArray(filter.value)) {
          currentFilterParams[filter.field] = filter.value.join(",");
        } else {
          currentFilterParams[filter.field] = filter.value;
        }
      }
    });

    // Compare current filter params with queryParams (excluding non-filter params)
    const existingFilterParams: Record<string, unknown> = {};
    Object.entries(queryParams).forEach(([key, value]) => {
      if (
        key !== "query" &&
        key !== "skip" &&
        key !== "limit" &&
        key !== "sort"
      ) {
        existingFilterParams[key] = value;
      }
    });

    // Only update if there's actually a difference
    const hasChanges =
      Object.keys(currentFilterParams).length !==
        Object.keys(existingFilterParams).length ||
      Object.entries(currentFilterParams).some(
        ([key, value]) => existingFilterParams[key] !== value,
      );

    if (!hasChanges) return;

    const newParams = { ...queryParams };

    // Remove existing filter params (except query, skip, limit, sort)
    Object.keys(newParams).forEach((key) => {
      if (
        key !== "query" &&
        key !== "skip" &&
        key !== "limit" &&
        key !== "sort"
      ) {
        delete newParams[key];
      }
    });

    // Add current filters
    Object.assign(newParams, currentFilterParams);

    onQueryParamsChange(newParams);
  }, [filters, onQueryParamsChange]);

  // Handle search input change
  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(event.target.value);
  };

  // Handle filter changes
  const handleFiltersChange = (newFilters: QueryFilter[]) => {
    setFilters(newFilters);
  };

  // Find the node object for editing
  const editNode = React.useMemo(() => {
    if (!editNodeId) return undefined;
    return data.find((item) => getId(item) === editNodeId);
  }, [editNodeId, data, getId]);

  const [pageIndex, setPageIndex] = React.useState(0);
  const [pageSize, setPageSize] = React.useState(defaultPageSize);

  // Calculate total number of pages
  const totalPages = React.useMemo(() => {
    return Math.max(1, Math.ceil((data?.length || 0) / pageSize));
  }, [data?.length, pageSize]);

  const table = useReactTable({
    data: data ?? [],
    columns,
    state: {
      columnVisibility,
      pagination: { pageIndex, pageSize },
    },
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    enableRowSelection: true,
    manualPagination: false,
    pageCount: totalPages,
  });
  React.useImperativeHandle(tableRef, () => table, [table]);

  React.useEffect(() => {
    setSelectedCount(table.getSelectedRowModel().rows.length);
  }, [table.getSelectedRowModel().rows.length]);

  // Reset to first page if data changes and current page is out of range
  React.useEffect(() => {
    if (pageIndex > 0 && pageIndex >= totalPages) {
      setPageIndex(0);
    }
  }, [data, pageIndex, totalPages]);

  if (isLoading) return <Spinner />;
  if (error) {
    console.error(error);
    return <div>Error loading {typeName.toLowerCase()}s</div>;
  }

  const handleDeleteSelected = () => {
    const selectedRows = table.getSelectedRowModel().rows;
    if (selectedRows.length === 0) return;
    setPendingDeleteRows(selectedRows);
    setShowDeleteModal(true);
  };

  const confirmDeleteSelected = async () => {
    setShowDeleteModal(false);
    if (pendingDeleteRows.length === 0) return;
    try {
      await onDelete(pendingDeleteRows.map((row: any) => getId(row.original)));
      setPendingDeleteRows([]);
      if (typeof table.resetRowSelection === "function") {
        table.resetRowSelection();
      }
    } catch (err) {
      console.error(
        `Failed to delete selected ${typeName.toLowerCase()}s:`,
        err,
      );
    }
  };

  return (
    <>
      {/* Advanced Filters */}
      {filtersEnabled && filterFields.length > 0 && (
        <QueryFilters
          fields={filterFields}
          filters={filters}
          onFiltersChange={handleFiltersChange}
          title={`Filter ${typeName}s`}
        />
      )}

      <div className="mb-4 flex items-center justify-between">
        <div className="flex grow justify-start">
          {searchEnabled && (
            <TextInput
              placeholder={searchPlaceholder || `Search ${typeName}s...`}
              icon={Search}
              value={searchTerm}
              onChange={handleSearchChange}
              className="max-w-md"
            />
          )}
        </div>
        <div className="flex justify-end gap-2">
          <Button
            color="blue"
            size="sm"
            onClick={() => setShowCreateModal(true)}
            className="w-auto whitespace-nowrap"
          >
            <Plus className="mr-2 h-4 w-4" />
            Add {typeName}
          </Button>

          <Dropdown
            label="Actions"
            color="light"
            size="sm"
            className="w-auto whitespace-nowrap"
            dismissOnClick={true}
            disabled={selectedCount === 0}
          >
            <DropdownItem onClick={handleDeleteSelected}>
              Delete Selected
            </DropdownItem>
          </Dropdown>

          {onRefetch && (
            <Button color="light" size="sm" onClick={onRefetch}>
              <RefreshCcw className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      <Table hoverable className="max-w-full">
        <TableHead>
          <TableRow>
            {table
              .getHeaderGroups()
              .map((headerGroup) =>
                headerGroup.headers.map((header) => (
                  <TableHeadCell key={header.id}>
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext(),
                    )}
                  </TableHeadCell>
                )),
              )}
            {linkGenerator && <TableHeadCell>Link</TableHeadCell>}
            <TableHeadCell />
          </TableRow>
        </TableHead>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow 
              key={row.id}
              onDoubleClick={() => {
                setEditNodeId(getId(row.original));
              }}
              className="cursor-pointer"
            >
              {row.getVisibleCells().map((cell) => (
                <TableCell key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
              {linkGenerator && (
                <TableCell>
                  {(() => {
                    const url = linkGenerator(row.original);
                    return url ? (
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center text-blue-600 hover:text-blue-800"
                        title="Open in new tab"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    ) : null;
                  })()}
                </TableCell>
              )}
              <TableCell>
                <a
                  onClick={() => {
                    setEditNodeId(getId(row.original));
                  }}
                  className="cursor-pointer text-blue-600 hover:underline"
                >
                  Edit
                </a>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className="mt-4 flex w-full items-center justify-between px-4">
        {totalPages > 1 ? (
          <>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-2">
                <Select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setPageIndex(0);
                  }}
                  className="w-20"
                >
                  {pageSizeOptions.map((size) => (
                    <option key={size} value={size}>
                      {size}
                    </option>
                  ))}
                </Select>
                <span className="text-sm text-gray-600">per page,</span>
              </div>
              <div className="text-sm font-normal text-gray-700">
                showing{" "}
                <Badge className="inline" color="gray">
                  {typeName.toLowerCase()}s
                </Badge>{" "}
                <span className="font-bold">
                  {data.length === 0 ? 0 : pageIndex * pageSize + 1}
                </span>
                -
                <span className="font-bold">
                  {Math.min((pageIndex + 1) * pageSize, data.length)}
                </span>
                &nbsp;of&nbsp;<span className="font-bold">{data.length}</span>
              </div>
            </div>
            <div>
              <Pagination
                layout="pagination"
                currentPage={pageIndex + 1}
                totalPages={totalPages}
                onPageChange={(page) => setPageIndex(page - 1)}
                showIcons
                nextLabel=""
                previousLabel=""
              />
            </div>
          </>
        ) : (
          <div className="text-sm font-normal text-gray-700">
            Showing{" "}
            <Badge className="inline" color="gray">
              {typeName.toLowerCase()}s
            </Badge>{" "}
            <span className="font-bold">
              {data.length === 0 ? 0 : pageIndex * pageSize + 1}
            </span>
            -
            <span className="font-bold">
              {Math.min((pageIndex + 1) * pageSize, data.length)}
            </span>
            &nbsp;of&nbsp;<span className="font-bold">{data.length}</span>
          </div>
        )}
      </div>
      {/* Delete Confirmation Modal */}
      <Modal show={showDeleteModal} onClose={() => setShowDeleteModal(false)}>
        <ModalHeader className="border-b-0">Confirm Delete</ModalHeader>
        <ModalBody>
          <div className="mb-4">
            Are you sure you want to delete {pendingDeleteRows.length} selected{" "}
            {typeName.toLowerCase()}
            {pendingDeleteRows.length > 1 ? "s" : ""}? This action cannot be
            undone.
          </div>
          <div className="flex justify-end gap-2">
            <Button color="gray" onClick={() => setShowDeleteModal(false)}>
              Cancel
            </Button>
            <Button color="red" onClick={confirmDeleteSelected}>
              Delete
            </Button>
          </div>
        </ModalBody>
      </Modal>
      {/* Create Modal */}
      <Modal show={showCreateModal} onClose={() => setShowCreateModal(false)}>
        <ModalHeader className="border-b-0">Create New {typeName}</ModalHeader>
        <ModalBody>
          <CreateForm onSuccess={() => setShowCreateModal(false)} />
        </ModalBody>
      </Modal>
      {/* Edit Modal */}
      <Modal show={!!editNodeId} onClose={() => setEditNodeId(undefined)}>
        <ModalHeader className="border-b-0">Edit {typeName}</ModalHeader>
        <ModalBody>
          {editNode && (
            <EditForm
              node={editNode}
              onSuccess={() => setEditNodeId(undefined)}
            />
          )}
        </ModalBody>
      </Modal>
    </>
  );
}

export { BaseNodeTable };
