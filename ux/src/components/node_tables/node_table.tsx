import React from "react";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  getPaginationRowModel,
} from "@tanstack/react-table";
import {
  Badge,
  Button,
  Dropdown,
  DropdownItem,
  Label,
  Modal,
  ModalBody,
  ModalHeader,
  Pagination,
  Radio,
  Select,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeadCell,
  TableRow,
  TextInput,
} from "flowbite-react";
import {
  RefreshCcw,
  Plus,
  Search,
  CircleArrowRight,
  Move,
  AlertTriangle,
} from "lucide-react";
import {
  QueryFilters,
  type QueryFilter,
  type FieldDefinition,
} from "@/components/misc/query_filters";

export interface BaseNodeTableProps<T> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
  // Custom row action to replace default Edit action
  customRowAction?: {
    label: string | ((item: T) => string);
    onClick: (item: T) => void;
    className?: string | ((item: T) => string);
    disabled?: (item: T) => boolean;
  };
  // Additional bulk actions for the Actions dropdown
  customBulkActions?: Array<{
    label: string;
    onClick: (selectedItems: T[], selectedIds: string[]) => void;
    className?: string;
    disabled?: boolean;
  }>;
  // Optional custom button bar to replace the default create button
  buttonBar?: React.ReactNode;
  // Move functionality
  moveForm?: React.ComponentType<{
    selectedNodes: T[];
    onSuccess: () => void;
    onCancel: () => void;
  }>;
  // Safe deletion functionality
  onGetChildren?: (id: string) => Promise<T[]>;
  onMoveChildren?: (
    childIds: string[],
    newParentId: string | null,
  ) => Promise<void>;
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
  filterFields = [],
  filtersEnabled = false,
  linkGenerator,
  customRowAction,
  customBulkActions = [],
  buttonBar,
  moveForm: MoveForm,
  onGetChildren,
  onMoveChildren,
}: BaseNodeTableProps<T>) {
  const [showCreateModal, setShowCreateModal] = React.useState(false);
  const [showDeleteModal, setShowDeleteModal] = React.useState(false);
  const [showMoveModal, setShowMoveModal] = React.useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [pendingDeleteRows, setPendingDeleteRows] = React.useState<any[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [pendingMoveRows, setPendingMoveRows] = React.useState<any[]>([]);
  const [childrenToHandle, setChildrenToHandle] = React.useState<T[]>([]);
  const [deleteOption, setDeleteOption] = React.useState<"delete" | "orphan">(
    "orphan",
  );
  const [editNodeId, setEditNodeId] = React.useState<string | undefined>(
    undefined,
  );
  const [selectedCount, setSelectedCount] = React.useState(0);
  const [, setIsProcessing] = React.useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const tableRef = React.useRef<any>(null);
  const [columnVisibility, setColumnVisibility] = React.useState<
    Record<string, boolean>
  >({
    ...propColumnVisibility,
  });

  // Search state management - use ref to preserve focus
  const searchInputRef = React.useRef<HTMLInputElement>(null);
  const [searchTerm, setSearchTerm] = React.useState<string>("");

  // Track if we initiated the query change to avoid circular updates

  // Initialize search term from URL on mount only
  React.useEffect(() => {
    const initialQuery = (queryParams?.query as string) || "";
    if (initialQuery) {
      setSearchTerm(initialQuery);
    }
  }, []);

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

  // Debounced search for client-side filtering
  const [debouncedSearchTerm, setDebouncedSearchTerm] =
    React.useState(searchTerm);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, 300); // 300ms debounce

    return () => clearTimeout(timer);
  }, [searchTerm]);

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

  // Client-side filtering based on search term
  const filteredData = React.useMemo(() => {
    if (!debouncedSearchTerm.trim()) {
      return data;
    }

    const searchLower = debouncedSearchTerm.toLowerCase().trim();

    return (data ?? []).filter(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (item: any) => {
        // Search in title and definition fields
        const title = item.title?.toLowerCase() || "";
        const definition = item.definition?.toLowerCase() || "";
        const id = item.id?.toLowerCase() || "";

        return (
          title.includes(searchLower) ||
          definition.includes(searchLower) ||
          id.includes(searchLower)
        );
      },
    );
  }, [data, debouncedSearchTerm]);

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

  // Calculate total number of pages using filtered data
  const totalPages = React.useMemo(() => {
    return Math.max(1, Math.ceil((filteredData?.length || 0) / pageSize));
  }, [filteredData?.length, pageSize]);

  const table = useReactTable({
    data: filteredData ?? [],
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

  // Reset to first page if filtered data changes and current page is out of range
  React.useEffect(() => {
    if (pageIndex > 0 && pageIndex >= totalPages) {
      setPageIndex(0);
    }
  }, [filteredData, pageIndex, totalPages]);

  // Reset to first page when search term changes
  React.useEffect(() => {
    setPageIndex(0);
  }, [debouncedSearchTerm]);

  // Debug effect to track modal state changes
  React.useEffect(() => {
    console.log("showMoveModal changed to:", showMoveModal);
  }, [showMoveModal]);

  React.useEffect(() => {
    console.log("selectedCount changed to:", selectedCount);
  }, [selectedCount]);

  React.useEffect(() => {
    console.log("pendingMoveRows changed to:", pendingMoveRows.length);
  }, [pendingMoveRows]);

  if (isLoading) return <Spinner />;
  if (error) {
    console.error(error);
    return <div>Error loading {typeName.toLowerCase()}s</div>;
  }

  const handleMoveSelected = () => {
    console.log("handleMoveSelected called");
    const selectedRows = table.getSelectedRowModel().rows;
    console.log("Selected rows:", selectedRows.length);

    if (selectedRows.length === 0 || !MoveForm) {
      console.log("No rows selected or no move form");
      return;
    }

    setIsProcessing(true);
    setPendingMoveRows(selectedRows);
    setShowMoveModal(true);
    console.log("Move modal should be shown");
  };

  const handleDeleteSelected = () => {
    const selectedRows = table.getSelectedRowModel().rows;
    if (selectedRows.length === 0) return;

    setPendingDeleteRows(selectedRows);

    // Check for children only for terms (safe deletion workflow)
    // For layers and domains, deletion cascades automatically in the database
    if (onGetChildren && typeName.toLowerCase() === "term") {
      (async () => {
        try {
          let allChildren: T[] = [];
          for (const row of selectedRows) {
            const nodeId = getId(row.original);
            const children = await onGetChildren(nodeId);
            allChildren = [...allChildren, ...children];
          }

          setChildrenToHandle(allChildren);

          if (allChildren.length > 0) {
            // Show the safe deletion modal with options
            setDeleteOption("orphan"); // Default to orphan
            setShowDeleteModal(true);
          } else {
            // No children, proceed with normal deletion
            setShowDeleteModal(true);
          }
        } catch (err) {
          console.error("Failed to check for children:", err);
          // Fall back to normal delete modal
          setShowDeleteModal(true);
        }
      })();
    } else {
      // For layers/domains or no safe deletion workflow, show normal delete modal
      setShowDeleteModal(true);
    }
  };

  const confirmDeleteSelected = async () => {
    setShowDeleteModal(false);
    if (pendingDeleteRows.length === 0) return;

    try {
      // Handle children first if needed (only for terms)
      if (
        childrenToHandle.length > 0 &&
        onMoveChildren &&
        typeName.toLowerCase() === "term"
      ) {
        if (deleteOption === "orphan") {
          // Move children to orphan state (null parent)
          const childIds = childrenToHandle.map((child) => getId(child));
          await onMoveChildren(childIds, null);
        } else if (deleteOption === "delete") {
          // Delete children first
          const childIds = childrenToHandle.map((child) => getId(child));
          await onDelete(childIds);
        }
      }

      // Then delete the selected items
      await onDelete(
        pendingDeleteRows.map(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (row: any) => getId(row.original),
        ),
      );
      setPendingDeleteRows([]);
      setChildrenToHandle([]);

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

      <div
        className="mb-4 flex items-center justify-between"
        data-testid={`${typeName.toLowerCase()}-table-toolbar`}
      >
        <div className="flex grow justify-start">
          {searchEnabled && (
            <TextInput
              ref={searchInputRef}
              placeholder={searchPlaceholder || `Search ${typeName}s...`}
              icon={Search}
              value={searchTerm}
              onChange={handleSearchChange}
              className="max-w-md"
              data-testid={`${typeName.toLowerCase()}-search-input`}
            />
          )}
        </div>
        <div className="flex justify-end gap-2">
          {buttonBar ? (
            buttonBar
          ) : (
            <Button
              color="blue"
              size="sm"
              onClick={() => setShowCreateModal(true)}
              className="w-auto whitespace-nowrap"
              data-testid={`${typeName.toLowerCase()}-add-button`}
            >
              <Plus className="mr-2 h-4 w-4" />
              Add {typeName}
            </Button>
          )}

          <Dropdown
            label="Actions"
            color="light"
            size="sm"
            className="w-auto whitespace-nowrap"
            dismissOnClick={true}
            disabled={selectedCount === 0}
            data-testid={`${typeName.toLowerCase()}-actions-dropdown`}
          >
            {MoveForm && (
              <DropdownItem
                onClick={handleMoveSelected}
                data-testid={`${typeName.toLowerCase()}-move-selected-action`}
              >
                <Move className="mr-2 h-4 w-4" />
                Move Selected
              </DropdownItem>
            )}
            <DropdownItem
              onClick={handleDeleteSelected}
              data-testid={`${typeName.toLowerCase()}-delete-selected-action`}
            >
              Delete Selected
            </DropdownItem>
            {customBulkActions.map((action, index) => (
              <DropdownItem
                key={index}
                onClick={() => {
                  const selectedRows = table.getFilteredSelectedRowModel().rows;
                  const selectedItems = selectedRows.map((row) => row.original);
                  const selectedIds = selectedRows.map((row) =>
                    getId(row.original),
                  );
                  action.onClick(selectedItems, selectedIds);
                }}
                className={action.className}
                disabled={action.disabled}
              >
                {action.label}
              </DropdownItem>
            ))}
          </Dropdown>

          {onRefetch && (
            <Button color="light" size="sm" onClick={onRefetch}>
              <RefreshCcw className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      <Table
        hoverable
        className="max-w-full"
        data-testid={`${typeName.toLowerCase()}-table`}
      >
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
              data-testid={`${typeName.toLowerCase()}-row-${getId(row.original)}`}
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
                        rel="noopener noreferrer"
                        className="inline-flex items-center text-blue-600 hover:text-blue-800"
                        title="Open in new tab"
                      >
                        <CircleArrowRight className="h-4 w-4" />
                      </a>
                    ) : null;
                  })()}
                </TableCell>
              )}
              <TableCell>
                {customRowAction ? (
                  <a
                    onClick={() => customRowAction.onClick(row.original)}
                    className={
                      typeof customRowAction.className === "function"
                        ? customRowAction.className(row.original)
                        : customRowAction.className ||
                          "cursor-pointer text-blue-600 hover:underline"
                    }
                    style={{
                      pointerEvents: customRowAction.disabled?.(row.original)
                        ? "none"
                        : "auto",
                      opacity: customRowAction.disabled?.(row.original)
                        ? 0.5
                        : 1,
                    }}
                  >
                    {typeof customRowAction.label === "function"
                      ? customRowAction.label(row.original)
                      : customRowAction.label}
                  </a>
                ) : (
                  <a
                    onClick={() => {
                      setEditNodeId(getId(row.original));
                    }}
                    className="cursor-pointer text-blue-600 hover:underline"
                  >
                    Edit
                  </a>
                )}
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
                  {filteredData.length === 0 ? 0 : pageIndex * pageSize + 1}
                </span>
                -
                <span className="font-bold">
                  {Math.min((pageIndex + 1) * pageSize, filteredData.length)}
                </span>
                &nbsp;of&nbsp;
                <span className="font-bold">{filteredData.length}</span>
                {debouncedSearchTerm && (
                  <span className="ml-1 text-gray-500">
                    (filtered from {data.length})
                  </span>
                )}
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
              {filteredData.length === 0 ? 0 : pageIndex * pageSize + 1}
            </span>
            -
            <span className="font-bold">
              {Math.min((pageIndex + 1) * pageSize, filteredData.length)}
            </span>
            &nbsp;of&nbsp;
            <span className="font-bold">{filteredData.length}</span>
            {debouncedSearchTerm && (
              <span className="ml-1 text-gray-500">
                (filtered from {data.length})
              </span>
            )}
          </div>
        )}
      </div>
      <Modal
        show={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        data-testid={`${typeName.toLowerCase()}-delete-modal`}
      >
        <ModalHeader className="border-b-0">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            Confirm Delete
          </div>
        </ModalHeader>
        <ModalBody>
          <div className="mb-4">
            Are you sure you want to delete {pendingDeleteRows.length} selected{" "}
            {typeName.toLowerCase()}
            {pendingDeleteRows.length > 1 ? "s" : ""}?
          </div>

          {/* Show cascade warning for layers and domains */}
          {(typeName.toLowerCase() === "layer" ||
            typeName.toLowerCase() === "domain") && (
            <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4">
              <div className="mb-3 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-red-600" />
                <span className="font-medium text-red-800">
                  Warning: Cascade Delete
                </span>
              </div>
              <p className="text-sm text-red-700">
                Deleting {typeName.toLowerCase()}
                {pendingDeleteRows.length > 1 ? "s" : ""} will also permanently
                delete all child records (terms, domains, and relationships).
              </p>
            </div>
          )}

          {/* Show child handling options only for terms */}
          {childrenToHandle.length > 0 && typeName.toLowerCase() === "term" && (
            <div className="mb-6 rounded-lg border border-yellow-200 bg-yellow-50 p-4">
              <div className="mb-3 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-yellow-600" />
                <span className="font-medium text-yellow-800">
                  Warning: {childrenToHandle.length} child{" "}
                  {typeName.toLowerCase()}
                  {childrenToHandle.length > 1 ? "s" : ""} found
                </span>
              </div>
              <p className="mb-4 text-sm text-yellow-700">
                What would you like to do with the child{" "}
                {typeName.toLowerCase()}s?
              </p>

              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Radio
                    id="orphan"
                    value="orphan"
                    checked={deleteOption === "orphan"}
                    onChange={(e) =>
                      setDeleteOption(e.target.value as "delete" | "orphan")
                    }
                  />
                  <Label htmlFor="orphan" className="text-sm">
                    Keep children but remove parent relationship (orphan them)
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <Radio
                    id="delete"
                    value="delete"
                    checked={deleteOption === "delete"}
                    onChange={(e) =>
                      setDeleteOption(e.target.value as "delete" | "orphan")
                    }
                  />
                  <Label htmlFor="delete" className="text-sm text-red-600">
                    Delete children as well (cascade delete)
                  </Label>
                </div>
              </div>
            </div>
          )}

          <div className="mb-4 text-sm text-gray-600">
            This action cannot be undone.
          </div>

          <div className="flex justify-end gap-2">
            <Button
              color="gray"
              onClick={() => setShowDeleteModal(false)}
              data-testid={`${typeName.toLowerCase()}-delete-cancel-button`}
            >
              Cancel
            </Button>
            <Button
              color="red"
              onClick={confirmDeleteSelected}
              data-testid={`${typeName.toLowerCase()}-delete-confirm-button`}
            >
              Delete
            </Button>
          </div>
        </ModalBody>
      </Modal>

      {/* Move Modal */}
      {MoveForm && (
        <Modal
          show={showMoveModal}
          onClose={() => {
            console.log("Move modal closing");
            setShowMoveModal(false);
            setPendingMoveRows([]);
            setIsProcessing(false);
          }}
          data-testid={`${typeName.toLowerCase()}-move-modal`}
        >
          <ModalHeader className="border-b-0">
            Move {pendingMoveRows.length} {typeName.toLowerCase()}
            {pendingMoveRows.length > 1 ? "s" : ""}
          </ModalHeader>
          <ModalBody>
            <MoveForm
              selectedNodes={pendingMoveRows.map((row) => row.original)}
              onSuccess={() => {
                console.log("Move success");
                setShowMoveModal(false);
                setPendingMoveRows([]);
                setIsProcessing(false);
                if (typeof table.resetRowSelection === "function") {
                  table.resetRowSelection();
                }
              }}
              onCancel={() => {
                console.log("Move cancelled");
                setShowMoveModal(false);
                setPendingMoveRows([]);
                setIsProcessing(false);
              }}
            />
          </ModalBody>
        </Modal>
      )}
      {/* Create Modal */}
      <Modal
        show={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        data-testid={`${typeName.toLowerCase()}-create-modal`}
      >
        <ModalHeader className="border-b-0">Create New {typeName}</ModalHeader>
        <ModalBody>
          <CreateForm onSuccess={() => setShowCreateModal(false)} />
        </ModalBody>
      </Modal>
      {/* Edit Modal */}
      <Modal
        show={!!editNodeId}
        onClose={() => setEditNodeId(undefined)}
        data-testid={`${typeName.toLowerCase()}-edit-modal`}
      >
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
