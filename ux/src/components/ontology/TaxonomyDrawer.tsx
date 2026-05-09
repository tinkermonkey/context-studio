import { useState, useEffect, useRef } from "react";
import { Drawer } from "@/components/ui/Drawer";
import { Input, Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useUpdateTaxonomy, useDeleteTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { useAutosave } from "@/hooks/useAutosave";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { taxonomiesCopy } from "@/routes/app/schema/taxonomies/-copy";
import { TaxonomyPublishDialog } from "./TaxonomyPublishDialog";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];

interface TaxonomyDrawerProps {
  taxonomy: TaxonomyResponse | null;
  onClose: () => void;
}

export function TaxonomyDrawer({ taxonomy, onClose }: TaxonomyDrawerProps) {
  const [title, setTitle] = useState(taxonomy?.title ?? "");
  const [description, setDescription] = useState(taxonomy?.description ?? "");
  const [showPublishDialog, setShowPublishDialog] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const lastSavedAtRef = useRef<Date | null>(null);

  const { toast } = useToasts();
  const updateMutation = useUpdateTaxonomy();
  const deleteMutation = useDeleteTaxonomy();
  const { performDelete, undo } = useUndoDelete({
    onDelete: (id: string) => deleteMutation.mutateAsync(id),
    undoWindowMs: 8000,
  });

  useEffect(() => {
    setTitle(taxonomy?.title ?? "");
    setDescription(taxonomy?.description ?? "");
    lastSavedAtRef.current = null;
  }, [taxonomy]);

  const isDirty = title !== taxonomy?.title || description !== taxonomy?.description;

  const updateData = {
    title,
    description,
  };

  const { status } = useAutosave({
    data: updateData,
    mutationFn: async () => {
      if (!taxonomy || !isDirty) return;
      await updateMutation.mutateAsync({
        id: taxonomy.id,
        data: {
          title,
          description: description || null,
        },
      });
      lastSavedAtRef.current = new Date();
    },
  });

  const revert = () => {
    if (taxonomy) {
      setTitle(taxonomy.title);
      setDescription(taxonomy.description ?? "");
    }
  };

  const handleDelete = async () => {
    if (!taxonomy) return;
    try {
      await performDelete(taxonomy.id);
      toast("success", taxonomiesCopy.delete.successToast, "Undo", {
        action: {
          label: "Undo",
          onAction: undo,
        },
        autoDismissMs: 8000,
      });
      onClose();
    } catch {
      toast("error", "Failed to delete taxonomy");
    }
  };

  const handleDeleteClick = () => {
    setShowDeleteConfirm(true);
  };

  if (!taxonomy) return null;

  const autosaveState = status === "idle" ? undefined : (status as "saving" | "saved" | "error");

  return (
    <>
      <Drawer
        open={!!taxonomy}
        onClose={onClose}
        title={taxonomy.title}
        autosaveState={autosaveState}
        isDirty={isDirty}
        lastSavedAt={lastSavedAtRef.current || undefined}
        onRevert={revert}
        onDelete={handleDeleteClick}
        headerAction={
          taxonomy.status === "draft" && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowPublishDialog(true)}
              data-testid="taxonomy-drawer-publish-button"
            >
              Publish…
            </Button>
          )
        }
        data-testid="taxonomy-drawer"
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
              ID
            </label>
            <Input
              type="text"
              value={taxonomy.id}
              disabled
              mono
              data-testid="taxonomy-drawer-id"
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
              Title
            </label>
            <Input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              data-testid="taxonomy-drawer-title-input"
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
              Description
            </label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              data-testid="taxonomy-drawer-description-input"
              rows={4}
            />
          </div>

          <div style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--text-xs)" }}>
            <span style={{ color: "var(--canvas-fg-3)" }}>
              Status: <span style={{ fontWeight: 500 }}>{taxonomy.status}</span>
            </span>
          </div>

          <div style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--text-xs)" }}>
            <span style={{ color: "var(--canvas-fg-3)" }}>
              Created: {new Date(taxonomy.created_at ?? "").toLocaleDateString()}
            </span>
          </div>
        </div>
      </Drawer>

      <TaxonomyPublishDialog
        open={showPublishDialog}
        onClose={() => setShowPublishDialog(false)}
        taxonomy={taxonomy}
        onPublish={() => {
          toast("success", taxonomiesCopy.publish.successToast(taxonomy.title, taxonomy.version + 1));
          setShowPublishDialog(false);
        }}
      />

      <ConfirmDialog
        open={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        title={taxonomiesCopy.delete.confirmTitle}
        message="This taxonomy and all its concept schemes will be permanently deleted."
        confirmLabel={taxonomiesCopy.delete.confirmButton}
        onConfirm={handleDelete}
        danger
        isLoading={deleteMutation.isPending}
        data-testid="taxonomy-delete-confirm"
      />
    </>
  );
}
