import { useState, useEffect, useRef } from "react";
import { Loader, AlertCircle } from "lucide-react";
import {
  InspectorPanel,
  TextInput as Input,
  Button,
  KVGrid,
} from "@tinkermonkey/heimdall-ui";
import { SuggestField } from "./suggesters";
import { ConfirmDialog } from "@tinkermonkey/heimdall-ui";
import { useUpdateProperty, useDeleteProperty } from "@/api/hooks/ontology/useProperties";
import { useAutosave } from "@/hooks/useAutosave";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { propertiesCopy } from "@/routes/app/schema/properties/-copy";
import { formatTimeAgo } from "@/utils/dateFormatting";
import type { components } from "@/api/types";

type PropertyDefinitionResponse = components["schemas"]["PropertyDefinitionResponse"];

interface PropertyDrawerProps {
  property: PropertyDefinitionResponse | null;
  onClose?: () => void;
}

export function PropertyDrawer({ property }: PropertyDrawerProps) {
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
  };

  const handleDeleteClick = () => {
    setShowDeleteConfirm(true);
  };

  if (!property) return null;

  const autosaveState = status === "idle" ? undefined : (status as "saving" | "saved" | "error");

  const inspectorActions = (
    <>
      <span data-testid="inspector-autosave-status" style={{ display: "contents" }}>
        {autosaveState === "saving" && <Loader size={14} className="spin" />}
        {autosaveState === "saved" && lastSavedAtRef.current && (
          <span style={{ fontSize: "var(--text-xs)", color: "rgb(var(--canvas-fg-3))" }}>
            Saved {formatTimeAgo(lastSavedAtRef.current)}
          </span>
        )}
        {autosaveState === "error" && (
          <AlertCircle size={14} style={{ color: "rgb(var(--status-rose))" }} />
        )}
      </span>
      {isDirty && (
        <Button variant="ghost" size="sm" onClick={revert} data-testid="inspector-revert-button">
          Revert
        </Button>
      )}
      <Button
        variant="danger"
        size="sm"
        onClick={handleDeleteClick}
        data-testid="inspector-delete-button"
      >
        Delete
      </Button>
    </>
  );

  return (
    <>
      <InspectorPanel
        eyebrow="property"
        title={property.title}
        id={property.id}
        actions={inspectorActions}
        data-testid="property-inspector"
      >
        <InspectorPanel.Section title="Details">
          <div className="stack">
            <div>
              <label className="form-group-label">Identifier</label>
              <Input
                type="text"
                value={property.identifier}
                disabled
                mono
                data-testid="property-drawer-identifier"
              />
            </div>

            <div>
              <label className="form-group-label">Title</label>
              <Input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                data-testid="property-drawer-title-input"
              />
            </div>

            <div>
              <label className="form-group-label">Description</label>
              <SuggestField
                entityId={property.id}
                value={description}
                onChange={setDescription}
                rows={4}
                testId="property-drawer-description-input"
              />
            </div>
          </div>
        </InspectorPanel.Section>

        <InspectorPanel.Section title="Metrics">
          <KVGrid
            rows={[
              { key: "Created", value: new Date(property.created_at ?? "").toLocaleDateString() },
            ]}
          />
        </InspectorPanel.Section>
      </InspectorPanel>

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        title={propertiesCopy.delete.confirmTitle}
        message="This property will be permanently deleted."
        confirmLabel={propertiesCopy.delete.confirmButton}
        onConfirm={() => {
          void handleDelete();
        }}
        variant="danger"
      />
    </>
  );
}
