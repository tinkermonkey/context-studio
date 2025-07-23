import React from "react";
import { useDomains } from "@/api/hooks/domains";
import { createFileRoute } from "@tanstack/react-router";
import { DomainsTable } from "@/components/node_tables/domains_table";
import { useDeleteDomain } from "@/api/hooks/domains/useDomainMutations";
import { Button, Spinner, Modal, ModalHeader, ModalBody } from "flowbite-react";
import { RefreshCcw, PlusCircle, CircleX } from "lucide-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { DomainForm } from "@/components/forms/domain_form";


export const Route = createFileRoute("/app/domains")({
  component: DomainsPage,
});

function DomainsPage() {
  const { data: domains, isLoading, error, refetch } = useDomains();
  const deleteDomain = useDeleteDomain();
  const [showModal, setShowModal] = React.useState(false);
  const [selectedCount, setSelectedCount] = React.useState(0);
  const tableRef = React.useRef<any>(null);
  const [showDeleteModal, setShowDeleteModal] = React.useState(false);
  const [pendingDeleteRows, setPendingDeleteRows] = React.useState<any[]>([]);
  const [editDomainId, setEditDomainId] = React.useState<string | undefined>(undefined);

  // Find the domain object for editing
  const editDomain = React.useMemo(() => {
    if (!editDomainId || !domains) return undefined;
    return domains.find((d: any) => d.id === editDomainId);
  }, [editDomainId, domains]);

  if (isLoading) {
    return <Spinner />;
  }
  if (error) {
    console.error(error);
    return <div>Error loading Domains</div>;
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
          deleteDomain.mutateAsync(row.original.id),
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
      console.error("Failed to delete selected domains:", err);
    }
  };

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Domains</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle>Domains</CsMainTitle>
        <DomainsTable
          ref={tableRef}
          data={domains}
          onSelectionChange={setSelectedCount}
          onEdit={(id: string) => setEditDomainId(id)}
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
            New Domain
          </Button>
        </div>
        {/* Delete Confirmation Modal */}
        <Modal show={showDeleteModal} onClose={() => setShowDeleteModal(false)}>
          <ModalHeader className="border-b-0">Confirm Delete</ModalHeader>
          <ModalBody>
            <div className="mb-4">
              Are you sure you want to delete {pendingDeleteRows.length}{" "}
              selected domain{pendingDeleteRows.length > 1 ? "s" : ""}? This
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
        {/* Create Domain Modal */}
        <Modal show={showModal} onClose={() => setShowModal(false)}>
          <ModalHeader className="border-b-0">Create New Domain</ModalHeader>
          <ModalBody>
            <DomainForm
              onSuccess={() => {
                setShowModal(false);
              }}
            />
          </ModalBody>
        </Modal>
        {/* Edit Domain Modal */}
        <Modal show={!!editDomainId} onClose={() => setEditDomainId(undefined)}>
          <ModalHeader className="border-b-0">Edit Domain</ModalHeader>
          <ModalBody>
            {editDomain && (
              <DomainForm
                domain={editDomain}
                onSuccess={() => {
                  setEditDomainId(undefined);
                }}
              />
            )}
          </ModalBody>
        </Modal>
      </CsMain>
    </>
  );
}
