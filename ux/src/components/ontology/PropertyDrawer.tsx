import { useState, useEffect } from "react";
import {
  InspectorPanel,
  TextInput as Input,
  KVGrid,
  ConfirmDialog,
} from "@tinkermonkey/heimdall-ui";
import { InlineInspector } from "@/components/ui/InlineInspector";
import { EditableField } from "@/components/ui/EditableField";
import { useUpdateProperty, useDeleteProperty, useCreateProperty } from "@/api/hooks/ontology/useProperties";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { propertiesCopy } from "@/routes/app/schema/properties/-copy";
import type { components } from "@/api/types";

type PropertyDefinitionResponse = components["schemas"]["PropertyDefinitionResponse"];

interface PropertyDrawerProps {
  property: PropertyDefinitionResponse | null;
}

export function PropertyDrawer({ property }: PropertyDrawerProps) {
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { toast } = useToasts();
  const updateMutation = useUpdateProperty();
  const deleteMutation = useDeleteProperty();
  const createMutation = useCreateProperty();
  const { performDelete, undo } = useUndoDelete({
    onDelete: (id: string) => deleteMutation.mutateAsync(id),
    onDeleteError: (id: string, error: Error) => {
      toast("error", `Failed to delete property: ${error.message}`);
    },
    undoWindowMs: 8000,
  });

  useEffect(() => {
    setMode("view");
  }, [property]);

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

  const handleDuplicate = async () => {
    try {
      const baseIdentifier = property.identifier + "_copy";
      await createMutation.mutateAsync({ identifier: baseIdentifier, title: `Copy of ${property.title}`, description: property.description ?? undefined });
      toast("success", "Property duplicated");
    } catch {
      toast("error", "Failed to duplicate property");
    }
  };

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
        onDuplicate={() => { void handleDuplicate(); }}
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

                <EditableField
                  label="Title"
                  value={property.title}
                  onSave={async (v) => {
                    await updateMutation.mutateAsync({ id: property.id, data: { title: v } });
                  }}
                  validate={(v) => !v.trim() ? "Title is required" : undefined}
                  data-testid="property-drawer-title-field"
                />

                <EditableField
                  label="Description"
                  type="textarea"
                  rows={4}
                  value={property.description ?? ""}
                  onSave={async (v) => {
                    await updateMutation.mutateAsync({ id: property.id, data: { description: v || null } });
                  }}
                  data-testid="property-drawer-description-field"
                />
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
