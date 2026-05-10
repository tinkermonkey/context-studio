import { useState } from "react";
import { Drawer } from "@/components/ui/Drawer";
import { Input } from "@/components/ui/Input";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useDeleteRelationship } from "@/api/hooks/ontology/useRelationships";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { ApiError } from "@/api/client/interceptors";
import { relationshipsCopy } from "@/routes/app/schema/relationships/-copy";
import type { components } from "@/api/types";

type RelationshipResponse = components["schemas"]["RelationshipResponse"];

interface RelationshipDrawerProps {
  relationship: RelationshipResponse | null;
  sourceName: string;
  targetName: string;
  propertyName: string;
  onClose: () => void;
}

export function RelationshipDrawer({
  relationship,
  sourceName,
  targetName,
  propertyName,
  onClose,
}: RelationshipDrawerProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const { toast } = useToasts();
  const deleteMutation = useDeleteRelationship();
  const { performDelete, undo } = useUndoDelete({
    onDelete: (id: string) => deleteMutation.mutateAsync(id),
    onDeleteError: (id: string, error: Error) => {
      toast("error", `Failed to delete relationship: ${error.message}`);
    },
    undoWindowMs: 8000,
  });

  const handleDelete = async () => {
    if (!relationship) return;
    try {
      await performDelete(relationship.id);
      toast("success", relationshipsCopy.delete.successToast, "Undo", {
        action: {
          label: "Undo",
          onAction: undo,
        },
        autoDismissMs: 8000,
      });
      onClose();
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Failed to delete relationship";
      toast("error", message);
    }
  };

  const handleDeleteClick = () => {
    setShowDeleteConfirm(true);
  };

  if (!relationship) return null;

  return (
    <>
      <Drawer
        open={!!relationship}
        onClose={onClose}
        title={`${sourceName} → ${targetName}`}
        isDirty={false}
        onDelete={handleDeleteClick}
        data-testid="relationship-drawer"
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
              ID
            </label>
            <Input
              type="text"
              value={relationship.id}
              disabled
              mono
              data-testid="relationship-drawer-id"
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
              Source Class
            </label>
            <Input
              type="text"
              value={sourceName}
              disabled
              data-testid="relationship-drawer-source-class"
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
              Target Class
            </label>
            <Input
              type="text"
              value={targetName}
              disabled
              data-testid="relationship-drawer-target-class"
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
              Relationship Type
            </label>
            <Input
              type="text"
              value={propertyName}
              disabled
              data-testid="relationship-drawer-property-type"
            />
          </div>

          <div style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--text-xs)" }}>
            <span style={{ color: "var(--canvas-fg-3)" }}>
              Created: {new Date(relationship.created_at ?? "").toLocaleDateString()}
            </span>
          </div>
        </div>
      </Drawer>

      <ConfirmDialog
        open={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        title={relationshipsCopy.delete.confirmTitle}
        message="This relationship and all its instances will be permanently deleted."
        confirmLabel={relationshipsCopy.delete.confirmButton}
        onConfirm={handleDelete}
        danger
        isLoading={deleteMutation.isPending}
        data-testid="relationship-delete-confirm"
      />
    </>
  );
}
