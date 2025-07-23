import React from "react";
import { useLayers } from "@/api/hooks/layers";
import { createFileRoute } from "@tanstack/react-router";
import { LayersTable } from "@/components/node_tables/layers_table";
import { useDeleteLayer } from "@/api/hooks/layers";
import { Button, Spinner, Modal, ModalHeader, ModalBody } from "flowbite-react";
import { RefreshCcw, PlusCircle, CircleX } from "lucide-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { LayerSelector } from "@/components/node_selectors/layer_selector";
import { LayerForm } from "@/components/forms/layer_form";

export const Route = createFileRoute("/app/layers")({
  component: LayersPage,
});


function LayersPage() {
  const { data: layers, isLoading, error, refetch } = useLayers();
  const deleteLayer = useDeleteLayer();
  const [showModal, setShowModal] = React.useState(false);
  const [selectedCount, setSelectedCount] = React.useState(0);
  const tableRef = React.useRef<any>(null);
  const [showDeleteModal, setShowDeleteModal] = React.useState(false);
  const [pendingDeleteRows, setPendingDeleteRows] = React.useState<any[]>([]);
  const [editLayerId, setEditLayerId] = React.useState<string | undefined>(undefined);

  // Find the layer object for editing
  const editLayer = React.useMemo(() => {
    if (!editLayerId || !layers) return undefined;
    return layers.find((l: any) => l.id === editLayerId);
  }, [editLayerId, layers]);

  if (isLoading) {
    return <Spinner />;
  }
  if (error) {
    console.error(error);
    return <div>Error loading layers</div>;
  }

  const handleDeleteSelected = () => {
    if (!tableRef.current) return;
    const selectedRows = tableRef.current.getSelectedRowModel().rows;
    if (selectedRows.length === 0) return;
    setPendingDeleteRows(selectedRows);
    setShowDeleteModal(true);
  };

  const confirmDeleteSelected = async () => {
    setShowDeleteModal(false);
    if (pendingDeleteRows.length === 0) return;
    try {
      await Promise.all(
        pendingDeleteRows.map((row: any) =>
          deleteLayer.mutateAsync(row.original.id),
        ),
      );
      setPendingDeleteRows([]);
      // No need to call refetch; TanStack Query will update all consumers automatically
      // Reset the selection in the table
      if (
        tableRef.current &&
        typeof tableRef.current.resetRowSelection === "function"
      ) {
        tableRef.current.resetRowSelection();
      }
    } catch (err) {
      console.error("Failed to delete selected layers:", err);
    }
  };

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Layers</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle>Layers</CsMainTitle>
        <LayersTable
          ref={tableRef}
          data={layers}
          onSelectionChange={setSelectedCount}
          onEdit={(id: string) => setEditLayerId(id)}
        />
        <div className="mt-4 flex items-center justify-between gap-3 whitespace-nowrap">
          <Button
            color="red"
            onClick={handleDeleteSelected}
            disabled={selectedCount === 0}
          >
            <CircleX className="mr-2 h-4 w-4" />
            Delete Selected
          </Button>
          <Button color="blue" onClick={() => refetch()}>
            <RefreshCcw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button
            color="green"
            onClick={() => setShowModal(true)}
            className="w-auto whitespace-nowrap"
          >
            <PlusCircle className="mr-2 h-4 w-4" />
            New Layer
          </Button>
        </div>
        {/* Delete Confirmation Modal */}
        <Modal show={showDeleteModal} onClose={() => setShowDeleteModal(false)}>
          <ModalHeader className="border-b-0">Confirm Delete</ModalHeader>
          <ModalBody>
            <div className="mb-4">
              Are you sure you want to delete {pendingDeleteRows.length}{" "}
              selected layer{pendingDeleteRows.length > 1 ? "s" : ""}? This
              action cannot be undone.
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
        {/* Create Layer Modal */}
        <Modal show={showModal} onClose={() => setShowModal(false)}>
          <ModalHeader className="border-b-0">Create New Layer</ModalHeader>
          <ModalBody>
            <LayerForm
              onSuccess={() => {
                setShowModal(false);
              }}
            />
          </ModalBody>
        </Modal>
        {/* Edit Layer Modal */}
        <Modal show={!!editLayerId} onClose={() => setEditLayerId(undefined)}>
          <ModalHeader className="border-b-0">Edit Layer</ModalHeader>
          <ModalBody>
            {editLayer && (
              <LayerForm
                layer={editLayer}
                onSuccess={() => {
                  setEditLayerId(undefined);
                }}
              />
            )}
          </ModalBody>
        </Modal>
      </CsMain>
    </>
  );
}
