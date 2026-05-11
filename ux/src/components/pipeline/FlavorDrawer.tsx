import { useState, Fragment } from "react";
import { Drawer } from "@/components/ui/Drawer";
import { Input, Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  useDeletePipelineFlavor,
  useCreatePipelineFromFlavor,
  useUpdatePipelineFlavor,
} from "@/api/hooks/pipeline";
import { useToasts } from "@/components/ui/Toast";
import { FlavorForm } from "@/components/pipeline/FlavorForm";
import type { PipelineFlavorResponse } from "@/api/services/pipeline";

interface FlavorDrawerProps {
  flavor: PipelineFlavorResponse | null;
  onClose: () => void;
}

export function FlavorDrawer({ flavor, onClose }: FlavorDrawerProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const { toast } = useToasts();
  const deleteMutation = useDeletePipelineFlavor();
  const createPipelineMutation = useCreatePipelineFromFlavor();
  const updateMutation = useUpdatePipelineFlavor();

  const handleDelete = async () => {
    if (!flavor) return;
    try {
      await deleteMutation.mutateAsync(flavor.id);
      toast("success", `Deleted flavor "${flavor.name}"`);
      onClose();
    } catch (error) {
      toast(
        "error",
        `Failed to delete flavor: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  };

  const handleCreatePipeline = async () => {
    if (!flavor) return;
    try {
      const title = `Pipeline from ${flavor.name}`;
      await createPipelineMutation.mutateAsync({
        flavorId: flavor.id,
        title,
      });
      toast("success", `Created pipeline from flavor "${flavor.name}"`);
    } catch (error) {
      toast(
        "error",
        `Failed to create pipeline: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  };

  const handleUpdateSubmit = async (data: {
    name: string;
    description?: string;
    steps: Array<Record<string, unknown>>;
  }) => {
    if (!flavor) return;
    setEditError(null);
    try {
      await updateMutation.mutateAsync({
        id: flavor.id,
        data,
      });
      setShowEditModal(false);
      toast("success", `Updated flavor "${data.name}"`);
    } catch (error) {
      setEditError(error instanceof Error ? error.message : "Failed to update flavor");
    }
  };

  if (!flavor) return null;

  const createdDate = new Date(flavor.created_at).toLocaleDateString();
  const updatedDate = new Date(flavor.last_updated).toLocaleDateString();

  return (
    <>
      <Drawer
        open={!!flavor}
        onClose={onClose}
        title={flavor.name}
        onDelete={() => setShowDeleteConfirm(true)}
        data-testid="flavor-drawer"
      >
        <div className="stack-lg">
          <div>
            <label className="form-group-label">ID</label>
            <Input
              type="text"
              value={flavor.id.slice(0, 8)}
              disabled
              mono
              data-testid="flavor-drawer-id"
            />
          </div>

          <div>
            <label className="form-group-label">Name</label>
            <Input type="text" value={flavor.name} disabled data-testid="flavor-drawer-name" />
          </div>

          <div>
            <label className="form-group-label">Description</label>
            <Textarea
              value={flavor.description || ""}
              disabled
              data-testid="flavor-drawer-description"
              rows={3}
            />
          </div>

          <div>
            <label className="form-group-label">Step Count</label>
            <Input
              type="text"
              value={flavor.step_count.toString()}
              disabled
              mono
              data-testid="flavor-drawer-step-count"
            />
          </div>

          <div className="kv">
            {(
              [
                ["Created", createdDate],
                ["Updated", updatedDate],
              ] as [string, string][]
            ).map(([k, v]) => (
              <Fragment key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </Fragment>
            ))}
          </div>

          <div className="stack" style={{ marginTop: "var(--space-4)" }}>
            <Button
              variant="primary"
              onClick={handleCreatePipeline}
              disabled={createPipelineMutation.isPending}
              data-testid="flavor-drawer-create-pipeline-button"
              aria-label="Create a new pipeline from this flavor"
            >
              {createPipelineMutation.isPending ? "Creating..." : "Create Pipeline"}
            </Button>
            <Button
              variant="accent"
              onClick={() => setShowEditModal(true)}
              data-testid="flavor-drawer-edit-button"
              aria-label="Edit this flavor"
            >
              Edit
            </Button>
            <Button
              variant="ghost"
              onClick={() => setShowDeleteConfirm(true)}
              data-testid="flavor-drawer-delete-button"
              aria-label="Delete this flavor"
            >
              Delete
            </Button>
          </div>
        </div>
      </Drawer>

      <ConfirmDialog
        open={showDeleteConfirm}
        title="Delete Flavor"
        message={`Are you sure you want to delete "${flavor.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={handleDelete}
        onClose={() => setShowDeleteConfirm(false)}
        danger
        isLoading={deleteMutation.isPending}
      />

      <Modal
        open={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditError(null);
        }}
        title="Edit Pipeline Flavor"
        size="lg"
        data-testid="flavor-edit-modal"
      >
        {editError && (
          <div style={{ marginBottom: "var(--space-3)" }}>
            <ErrorBanner
              error={new Error(editError)}
              onRetry={() => setEditError(null)}
              message="Failed to update flavor"
            />
          </div>
        )}
        <FlavorForm
          onSubmit={handleUpdateSubmit}
          isLoading={updateMutation.isPending}
          initialData={{
            name: flavor.name,
            description: flavor.description,
            steps: flavor.steps || [],
          }}
        />
      </Modal>
    </>
  );
}
