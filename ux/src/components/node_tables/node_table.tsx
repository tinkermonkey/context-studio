import React from "react";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import {
  Table,
  TableHead,
  TableHeadCell,
  TableBody,
  TableRow,
  TableCell,
  Button,
  Spinner,
  Modal,
  ModalHeader,
  ModalBody,
} from "flowbite-react";
import { RefreshCcw, Plus } from "lucide-react";

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

  // Find the node object for editing
  const editNode = React.useMemo(() => {
    if (!editNodeId) return undefined;
    return data.find((item) => getId(item) === editNodeId);
  }, [editNodeId, data, getId]);

  const table = useReactTable({
    data: data ?? [],
    columns,
    state: { columnVisibility },
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    enableRowSelection: true,
  });
  React.useImperativeHandle(tableRef, () => table, [table]);

  React.useEffect(() => {
    setSelectedCount(table.getSelectedRowModel().rows.length);
  }, [table.getSelectedRowModel().rows.length]);

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
      <div className="mb-4 flex items-center justify-between">
        <div className="flex grow justify-start">

        </div>
        <div className="flex justify-end gap-2">
          <Button
            color="blue"
            size="sm"
            onClick={() => setShowCreateModal(true)}
            className="w-auto whitespace-nowrap"
          >
            <Plus className="h-4 w-4 mr-2" />
            Add {typeName}
          </Button>

          <Button
            color="light"
            size="sm"
            onClick={handleDeleteSelected}
            disabled={selectedCount === 0}
          >
            Delete Selected
          </Button>

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
            <TableHeadCell />
          </TableRow>
        </TableHead>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <TableCell key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
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
