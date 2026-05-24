import { useState } from "react";
import { Button } from "@tinkermonkey/heimdall-ui";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useToasts } from "@/components/ui/Toast";
import type { components } from "@/api/types";

type PipelineFlavorResponse = components["schemas"]["PipelineFlavorResponse"];

interface FlavorDrawerProps {
  flavor: PipelineFlavorResponse;
  onClose: () => void;
  onDelete: (id: string) => Promise<void>;
  isDeleting?: boolean;
}

export function FlavorDrawer({ flavor, onClose, onDelete, isDeleting = false }: FlavorDrawerProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const { toast } = useToasts();

  const handleDelete = async () => {
    await onDelete(flavor.id);
    onClose();
  };

  return (
    <>
      <div data-testid="flavor-drawer" className="drawer-body stack-lg">
        <div>
          <h3 className="form-group-label">{flavor.name}</h3>
          <p className="text-secondary">{flavor.description}</p>
        </div>

        <dl className="kv">
          <dt>ID</dt>
          <dd data-testid="flavor-drawer-id">{flavor.id}</dd>

          <dt>Steps</dt>
          <dd data-testid="flavor-drawer-step-count">
            {flavor.step_count} step{flavor.step_count !== 1 ? "s" : ""}
          </dd>

          <dt>Created</dt>
          <dd>{new Date(flavor.created_at).toLocaleDateString()}</dd>
        </dl>
      </div>

      <div className="drawer-actions">
        <Button
          variant="danger"
          onClick={() => setShowDeleteConfirm(true)}
          disabled={isDeleting}
          data-testid="flavor-drawer-delete-button"
        >
          {isDeleting ? "Deleting..." : "Delete"}
        </Button>
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>

      <ConfirmDialog
        open={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        title="Delete Flavor"
        message="Are you sure you want to delete this flavor? This action cannot be undone."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        danger
        onConfirm={handleDelete}
        onError={(error) => {
          toast("error", `Delete failed: ${error.message}`);
        }}
        isLoading={isDeleting}
      />
    </>
  );
}
