import { useState, useEffect, useRef } from "react";
import {
  InspectorPanel,
  TextInput as Input,
  KVGrid,
  Button,
  ConfirmDialog,
} from "@tinkermonkey/heimdall-ui";
import { SuggestField } from "./suggesters";
import { InlineInspector } from "@/components/ui/InlineInspector";
import { useUpdateProperty, useDeleteProperty } from "@/api/hooks/ontology/useProperties";
import { useAutosave } from "@/hooks/useAutosave";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { propertiesCopy } from "@/routes/app/schema/properties/-copy";
import type { components } from "@/api/types";

type PropertyDefinitionResponse = components["schemas"]["PropertyDefinitionResponse"];

interface PropertyDrawerProps {
  property: PropertyDefinitionResponse | null;
  onClose?: () => void;
}

export function PropertyDrawer({ property }: PropertyDrawerProps) {
  const [mode, setMode] = useState<"view" | "edit">("view");
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
    setMode("view");
  }, [property]);

  const isDirty = title !== property?.title || description !== property?.description;

  const updateData = {
    title,
    description: description || null,
  };

  const { status } = useAutosave({
    data: updateData,
    mutationFn: async () => {
      if (!property || !isDirty || mode !== "edit") return;
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

  if (!property) return null;

  const autosaveStatus = status === "idle" ? undefined : (status as "saving" | "saved" | "error");

  return (
    <>
      <InlineInspector
        eyebrow="property"
        title={property.title}
        id={property.id}
        mode={mode}
        onEdit={() => setMode("edit")}
        onDone={() => setMode("view")}
        onDelete={() => setShowDeleteConfirm(true)}
        autosaveStatus={autosaveStatus}
        lastSavedAt={lastSavedAtRef.current}
        data-testid="property-inspector"
      >
        {mode === "view" ? (
          <>
            <InspectorPanel.Section title="Details">
              <KVGrid
                rows={[
                  { key: "Identifier", value: property.identifier },
                  { key: "Title", value: property.title },
                  { key: "Description", value: property.description || "—" },
                  {
                    key: "Created",
                    value: new Date(property.created_at ?? "").toLocaleDateString(),
                  },
                ]}
              />
            </InspectorPanel.Section>
          </>
        ) : (
          <>
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

                {isDirty && (
                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        if (property) {
                          setTitle(property.title);
                          setDescription(property.description ?? "");
                        }
                      }}
                      data-testid="inspector-revert-button"
                    >
                      Revert
                    </Button>
                  </div>
                )}
              </div>
            </InspectorPanel.Section>

            <InspectorPanel.Section title="Metrics">
              <KVGrid
                rows={[
                  {
                    key: "Created",
                    value: new Date(property.created_at ?? "").toLocaleDateString(),
                  },
                ]}
              />
            </InspectorPanel.Section>
          </>
        )}
      </InlineInspector>

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
