import { useState, useEffect, useRef } from "react";
import { Drawer } from "@/components/ui/Drawer";
import { Input, Textarea } from "@/components/ui/Input";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useUpdateProperty, useDeleteProperty } from "@/api/hooks/ontology/useProperties";
import { useAutosave } from "@/hooks/useAutosave";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { propertiesCopy } from "@/routes/app/schema/properties/-copy";
import type { components } from "@/api/types";

type PropertyDefinitionResponse = components["schemas"]["PropertyDefinitionResponse"];

interface PropertyDrawerProps {
  property: PropertyDefinitionResponse | null;
  onClose: () => void;
}

export function PropertyDrawer({ property, onClose }: PropertyDrawerProps) {
  const [title, setTitle] = useState(property?.title ?? "");
  const [description, setDescription] = useState(property?.description ?? "");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const lastSavedAtRef = useRef<Date | null>(null);

  const { toast } = useToasts();
  const updateMutation = useUpdateProperty();
  const deleteMutation = useDeleteProperty();
  const { performDelete, undo } = useUndoDelete({
    onDelete: (id: string) => deleteMutation.mutateAsync(id),
    onDeleteError: (id: string, error: Error) => {
      toast("error", `Failed to delete property: ${error.message}`);
    },
    undoWindowMs: 8000,
  });

  useEffect(() => {
    setTitle(property?.title ?? "");
    setDescription(property?.description ?? "");
    lastSavedAtRef.current = null;
  }, [property]);

  const isDirty = title !== property?.title || description !== property?.description;

  const updateData = {
    title,
    description: description || null,
  };

  const { status } = useAutosave({
    data: updateData,
    mutationFn: async () => {
      if (!property || !isDirty) return;
      await updateMutation.mutateAsync({
        id: property.id,
        data: {
          title,
          description: description || null,
        },
      });
      lastSavedAtRef.current = new Date();
    },
    onError: (error) => {
      toast("error", `Autosave failed: ${error.message}`);
    },
  });

  const revert = () => {
    if (property) {
      setTitle(property.title);
      setDescription(property.description ?? "");
    }
  };

  const handleDelete = async () => {
    if (!property) return;
    await performDelete(property.id);
    toast("success", propertiesCopy.delete.successToast, "Undo", {
      action: {
        label: "Undo",
        onAction: undo,
      },
      autoDismissMs: 8000,
    });
    onClose();
  };

  const handleDeleteClick = () => {
    setShowDeleteConfirm(true);
  };

  if (!property) return null;

  const autosaveState = status === "idle" ? undefined : (status as "saving" | "saved" | "error");

  return (
    <>
      <Drawer
        open={!!property}
        onClose={onClose}
        title={property.title}
        autosaveState={autosaveState}
        isDirty={isDirty}
        lastSavedAt={lastSavedAtRef.current || undefined}
        onRevert={revert}
        onDelete={handleDeleteClick}
        data-testid="property-drawer"
      >
        <div className="stack">
          <div>
            <label className="form-group-label">
              Identifier
            </label>
            <Input
              type="text"
              value={property.identifier}
              disabled
              mono
              data-testid="property-drawer-identifier"
            />
          </div>

          <div>
            <label className="form-group-label">
              Title
            </label>
            <Input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              data-testid="property-drawer-title-input"
            />
          </div>

          <div>
            <label className="form-group-label">
              Description
            </label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              data-testid="property-drawer-description-input"
              rows={4}
            />
          </div>

          <div style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--text-xs)" }}>
            <span style={{ color: "var(--canvas-fg-3)" }}>
              Created: {new Date(property.created_at ?? "").toLocaleDateString()}
            </span>
          </div>
        </div>
      </Drawer>

      <ConfirmDialog
        open={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        title={propertiesCopy.delete.confirmTitle}
        message="This property will be permanently deleted."
        confirmLabel={propertiesCopy.delete.confirmButton}
        onConfirm={handleDelete}
        danger
        isLoading={deleteMutation.isPending}
        data-testid="property-delete-confirm"
      />
    </>
  );
}
