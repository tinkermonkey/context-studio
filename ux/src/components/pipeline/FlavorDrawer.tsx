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
import { COPY } from "@/routes/app/pipelines/-copy";
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
      toast("success", COPY.FLAVOR_DELETED(flavor.name));
      onClose();
    } catch (error) {
      toast(
        "error",
        COPY.FLAVOR_DELETE_ERROR(error instanceof Error ? error.message : "Unknown error"),
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
      toast("success", COPY.FLAVOR_PIPELINE_CREATED(flavor.name));
    } catch (error) {
      toast(
        "error",
        COPY.FLAVOR_PIPELINE_CREATE_ERROR(error instanceof Error ? error.message : "Unknown error"),
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
      toast("success", COPY.FLAVOR_UPDATED(data.name));
    } catch (error) {
      setEditError(error instanceof Error ? error.message : COPY.FLAVOR_UPDATE_ERROR);
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
            <label className="form-group-label">{COPY.FLAVOR_DRAWER_ID_LABEL}</label>
            <Input
              type="text"
              value={flavor.id.slice(0, 8)}
              disabled
              mono
              data-testid="flavor-drawer-id"
            />
          </div>

          <div>
            <label className="form-group-label">{COPY.FLAVOR_DRAWER_NAME_LABEL}</label>
            <Input type="text" value={flavor.name} disabled data-testid="flavor-drawer-name" />
          </div>

          <div>
            <label className="form-group-label">{COPY.FLAVOR_DRAWER_DESCRIPTION_LABEL}</label>
            <Textarea
              value={flavor.description || ""}
              disabled
              data-testid="flavor-drawer-description"
              rows={3}
            />
          </div>

          <div>
            <label className="form-group-label">{COPY.FLAVOR_DRAWER_STEP_COUNT_LABEL}</label>
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
                [COPY.FLAVOR_DRAWER_CREATED_LABEL, createdDate],
                [COPY.FLAVOR_DRAWER_UPDATED_LABEL, updatedDate],
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
              {createPipelineMutation.isPending ? COPY.FLAVOR_CREATE_PIPELINE_CREATING : COPY.FLAVOR_CREATE_PIPELINE_BUTTON}
            </Button>
            <Button
              variant="accent"
              onClick={() => setShowEditModal(true)}
              data-testid="flavor-drawer-edit-button"
              aria-label="Edit this flavor"
            >
              {COPY.FLAVOR_EDIT_BUTTON}
            </Button>
            <Button
              variant="ghost"
              onClick={() => setShowDeleteConfirm(true)}
              data-testid="flavor-drawer-delete-button"
              aria-label="Delete this flavor"
            >
              {COPY.FLAVOR_DELETE_BUTTON}
            </Button>
          </div>
        </div>
      </Drawer>

      <ConfirmDialog
        open={showDeleteConfirm}
        title={COPY.DELETE_FLAVOR_TITLE}
        message={COPY.FLAVOR_DELETE_CONFIRM_MESSAGE(flavor.name)}
        confirmLabel={COPY.DELETE_CONFIRM_LABEL}
        cancelLabel={COPY.CANCEL_LABEL}
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
        title={COPY.EDIT_FLAVOR_MODAL_TITLE}
        size="lg"
        data-testid="flavor-edit-modal"
      >
        {editError && (
          <div style={{ marginBottom: "var(--space-3)" }}>
            <ErrorBanner
              error={new Error(editError)}
              onRetry={() => setEditError(null)}
              message={COPY.FLAVOR_UPDATE_ERROR}
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
