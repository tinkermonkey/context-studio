import React from "react";
import { useTerms } from "@/api/hooks/terms";
import { createFileRoute } from "@tanstack/react-router";
import { TermsTable } from "@/components/node_tables/terms_table";
import { useDeleteTerm } from "@/api/hooks/terms/useTermMutations";
import { Button, Spinner, Modal, ModalHeader, ModalBody } from "flowbite-react";
import { RefreshCcw, PlusCircle, CircleX } from "lucide-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { TermForm } from "@/components/forms/term_form";


export const Route = createFileRoute("/app/terms")({
  component: TermsPage,
});

function TermsPage() {
  const { data: terms, isLoading, error, refetch } = useTerms();
  const deleteTerm = useDeleteTerm();
  const [showModal, setShowModal] = React.useState(false);
  const [selectedCount, setSelectedCount] = React.useState(0);
  const tableRef = React.useRef<any>(null);
  const [showDeleteModal, setShowDeleteModal] = React.useState(false);
  const [pendingDeleteRows, setPendingDeleteRows] = React.useState<any[]>([]);
  const [editTermId, setEditTermId] = React.useState<string | undefined>(undefined);

  // Find the term object for editing
  const editTerm = React.useMemo(() => {
    if (!editTermId || !terms) return undefined;
    return terms.find((t: any) => t.id === editTermId);
  }, [editTermId, terms]);

  if (isLoading) {
    return <Spinner />;
  }
  if (error) {
    console.error(error);
    return <div>Error loading Terms</div>;
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
          deleteTerm.mutateAsync(row.original.id),
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
      console.error("Failed to delete selected terms:", err);
    }
  };

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Terms</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle>Terms</CsMainTitle>
        <TermsTable
          ref={tableRef}
          data={terms}
          onSelectionChange={setSelectedCount}
          onEdit={(id: string) => setEditTermId(id)}
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
            New Term
          </Button>
        </div>
        {/* Delete Confirmation Modal */}
        <Modal show={showDeleteModal} onClose={() => setShowDeleteModal(false)}>
          <ModalHeader className="border-b-0">Confirm Delete</ModalHeader>
          <ModalBody>
            <div className="mb-4">
              Are you sure you want to delete {pendingDeleteRows.length}{" "}
              selected term{pendingDeleteRows.length > 1 ? "s" : ""}? This
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
        {/* Create Term Modal */}
        <Modal show={showModal} onClose={() => setShowModal(false)}>
          <ModalHeader className="border-b-0">Create New Term</ModalHeader>
          <ModalBody>
            <TermForm
              onSuccess={() => {
                setShowModal(false);
              }}
            />
          </ModalBody>
        </Modal>
        {/* Edit Term Modal */}
        <Modal show={!!editTermId} onClose={() => setEditTermId(undefined)}>
          <ModalHeader className="border-b-0">Edit Term</ModalHeader>
          <ModalBody>
            {editTerm && (
              <TermForm
                term={editTerm}
                onSuccess={() => {
                  setEditTermId(undefined);
                }}
              />
            )}
          </ModalBody>
        </Modal>
      </CsMain>
    </>
  );
}
