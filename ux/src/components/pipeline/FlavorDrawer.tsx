import { useState } from "react";
import { Button, ConfirmDialog } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
// TODO: PipelineFlavorResponse not yet in OpenAPI spec (Phase 2 work)
type PipelineFlavorResponse = any;

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
    try {
      await onDelete(flavor.id);
      onClose();
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      toast("error", `Delete failed: ${err.message}`);
    }
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
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        title="Delete Flavor"
        message="Are you sure you want to delete this flavor? This action cannot be undone."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={() => { void handleDelete(); }}
      />
    </>
  );
}
