import { useState } from "react";
import { Drawer } from "@/components/ui/Drawer";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input, Textarea } from "@/components/ui/Input";
import { useUpdateProperty, useDeleteProperty } from "@/api/hooks/ontology/useProperties";
import type { components } from "@/api/types";

type PropertyDefinitionResponse = components["schemas"]["PropertyDefinitionResponse"];
type PropertyDefinitionUpdateRequest = components["schemas"]["PropertyDefinitionUpdateRequest"];
type AutosaveState = "idle" | "saving" | "saved" | "error";

interface PropertyDrawerProps {
  property: PropertyDefinitionResponse | null;
  onClose: () => void;
}

export function PropertyDrawer({ property, onClose }: PropertyDrawerProps) {
  const [title, setTitle] = useState(property?.title ?? "");
  const [description, setDescription] = useState(property?.description ?? "");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const updateMutation = useUpdateProperty();
  const deleteMutation = useDeleteProperty();

  const handleConfirmDelete = async () => {
    if (!property) return;
    try {
      await deleteMutation.mutateAsync(property.id);
      onClose();
    } catch {
      // Error handled by mutation
    }
  };

  if (!property) return null;

  return (
    <>
      <Drawer
        open={!!property}
        onClose={onClose}
        title={property.title}
        data-testid="property-drawer"
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
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
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
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
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
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
        title="Delete Property?"
        message="Are you sure you want to delete this property definition?"
        confirmLabel="Delete"
        cancelLabel="Cancel"
        danger
        onConfirm={handleConfirmDelete}
        isLoading={deleteMutation.isPending}
        data-testid="property-delete-confirm"
      />
    </>
  );
}
