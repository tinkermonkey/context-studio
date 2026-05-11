import { useState, useEffect, useRef } from "react";
import { Drawer } from "@/components/ui/Drawer";
import { Input, Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import {
  useUpdatePipelineFlavor,
  useDeletePipelineFlavor,
  useCreatePipelineFromFlavor,
} from "@/api/hooks/pipeline";
import { useToasts } from "@/components/ui/Toast";
import type { PipelineFlavorResponse } from "@/api/services/pipeline";

interface FlavorDrawerProps {
  flavor: PipelineFlavorResponse | null;
  onClose: () => void;
}

export function FlavorDrawer({ flavor, onClose }: FlavorDrawerProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const { toast } = useToasts();
  const deleteMutation = useDeletePipelineFlavor();
  const createPipelineMutation = useCreatePipelineFromFlavor();

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

          <div
            className="kv"
            style={{
              display: "grid",
              gridTemplateColumns: "100px 1fr",
              gap: "8px 16px",
              alignItems: "center",
            }}
          >
            {(
              [
                ["Created", createdDate],
                ["Updated", updatedDate],
              ] as [string, string][]
            ).map(([k, v]) => (
              <div key={k}>
                <dt style={{ fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)" }}>{k}</dt>
                <dd style={{ margin: 0, fontSize: "var(--text-sm)" }}>{v}</dd>
              </div>
            ))}
          </div>

          <div className="stack" style={{ marginTop: "var(--space-4)" }}>
            <Button
              variant="primary"
              onClick={handleCreatePipeline}
              disabled={createPipelineMutation.isPending}
              data-testid="flavor-drawer-create-pipeline-button"
            >
              {createPipelineMutation.isPending ? "Creating..." : "Create Pipeline"}
            </Button>
            <Button
              variant="ghost"
              onClick={() => setShowDeleteConfirm(true)}
              data-testid="flavor-drawer-delete-button"
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
    </>
  );
}
