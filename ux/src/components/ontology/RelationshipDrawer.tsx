import { useState } from "react";
import { InspectorPanel, TextInput as Input, Button, KVGrid } from "@tinkermonkey/heimdall-ui";
import { ConfirmDialog } from "@tinkermonkey/heimdall-ui";
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
  onClose?: () => void;
}

export function RelationshipDrawer({
  relationship,
  sourceName,
  targetName,
  propertyName,
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
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Failed to delete relationship";
      toast("error", message);
    }
  };

  const handleDeleteClick = () => {
    setShowDeleteConfirm(true);
  };

  if (!relationship) return null;

  const inspectorActions = (
    <Button variant="danger" size="sm" onClick={handleDeleteClick} data-testid="inspector-delete-button">
      Delete
    </Button>
  );

  return (
    <>
      <InspectorPanel
        eyebrow="relationship"
        title={`${sourceName} → ${targetName}`}
        id={relationship.id}
        actions={inspectorActions}
        data-testid="relationship-inspector"
      >
        <InspectorPanel.Section title="Details">
          <div>
            <label className="form-group-label">ID</label>
            <Input
              type="text"
              value={relationship.id}
              disabled
              mono
              data-testid="relationship-drawer-id"
            />
          </div>

          <div>
            <label className="form-group-label">Source Class</label>
            <Input
              type="text"
              value={sourceName}
              disabled
              data-testid="relationship-drawer-source-class"
            />
          </div>

          <div>
            <label className="form-group-label">Target Class</label>
            <Input
              type="text"
              value={targetName}
              disabled
              data-testid="relationship-drawer-target-class"
            />
          </div>

          <div>
            <label className="form-group-label">Relationship Type</label>
            <Input
              type="text"
              value={propertyName}
              disabled
              data-testid="relationship-drawer-property-type"
            />
          </div>
        </InspectorPanel.Section>

        <InspectorPanel.Section title="Metrics">
          <KVGrid
            rows={[
              { key: "Created", value: new Date(relationship.created_at ?? "").toLocaleDateString() },
            ]}
          />
        </InspectorPanel.Section>
      </InspectorPanel>

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        title={relationshipsCopy.delete.confirmTitle}
        message="This relationship and all its instances will be permanently deleted."
        confirmLabel={relationshipsCopy.delete.confirmButton}
        onConfirm={() => { void handleDelete(); }}
        variant="danger"
      />
    </>
  );
}
