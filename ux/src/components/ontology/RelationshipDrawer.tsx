import { useState } from "react";
import {
  InspectorPanel,
  RelationshipBuilder,
  type RelationshipBuilderValue,
  KVGrid,
  Button,
  ConfirmDialog,
} from "@tinkermonkey/heimdall-ui";
import { InlineInspector } from "@/components/ui/InlineInspector";
import { useDeleteRelationship, useCreateRelationship } from "@/api/hooks/ontology/useRelationships";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { useToasts } from "@/components/ui/Toast";
import { ApiError } from "@/api/client/interceptors";
import { relationshipsCopy } from "@/routes/app/schema/relationships/-copy";
import type { components } from "@/api/types";

type RelationshipResponse = components["schemas"]["RelationshipResponse"];

interface RelationshipDrawerProps {
  relationship: RelationshipResponse | null;
  sourceName: string;
  targetName: string;
  propertyName: string;
}

export function RelationshipDrawer({
  relationship,
  sourceName,
  targetName,
  propertyName,
}: RelationshipDrawerProps) {
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [editValue, setEditValue] = useState<RelationshipBuilderValue>({ predicate: "" });
  const [sourceQuery, setSourceQuery] = useState("");
  const [targetQuery, setTargetQuery] = useState("");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const { toast } = useToasts();
  const deleteMutation = useDeleteRelationship();
  const createMutation = useCreateRelationship();
  const { data: classesResponse } = useClasses();
  const { data: propertiesResponse } = useProperties();

  const allClasses = classesResponse?.items || [];
  const properties = propertiesResponse?.items || [];

  const predicates = properties.length > 0
    ? properties.map((p) => p.identifier)
    : ["related_to", "contains", "depends_on", "is_used_by"];

  const sourcePickerResults = allClasses
    .filter((c) => !sourceQuery || c.title.toLowerCase().includes(sourceQuery.toLowerCase()))
    .slice(0, 20)
    .map((c) => ({ id: c.id, label: c.title }));

  const targetPickerResults = allClasses
    .filter((c) => !targetQuery || c.title.toLowerCase().includes(targetQuery.toLowerCase()))
    .slice(0, 20)
    .map((c) => ({ id: c.id, label: c.title }));

  const handleEditStart = () => {
    if (!relationship) return;
    const sourceClass = allClasses.find((c) => c.id === relationship.source_id);
    const targetClass = allClasses.find((c) => c.id === relationship.target_id);
    const prop = properties.find((p) => p.id === relationship.property_definition_id);
    setEditValue({
      source: sourceClass ? { id: sourceClass.id, label: sourceClass.title } : undefined,
      target: targetClass ? { id: targetClass.id, label: targetClass.title } : undefined,
      predicate: prop?.identifier ?? "",
    });
    setSourceQuery("");
    setTargetQuery("");
    setMode("edit");
  };

  const handleSave = async () => {
    if (!relationship || !editValue.source?.id || !editValue.target?.id || !editValue.predicate) {
      return;
    }

    const prop = properties.find((p) => p.id === relationship.property_definition_id);
    const unchanged =
      editValue.source.id === relationship.source_id &&
      editValue.target.id === relationship.target_id &&
      editValue.predicate === (prop?.identifier ?? "");

    if (unchanged) {
      setMode("view");
      return;
    }

    setIsSaving(true);
    try {
      await deleteMutation.mutateAsync(relationship.id);
    } catch (error) {
      const message =
        error instanceof ApiError ? error.detail : "Failed to update relationship";
      toast("error", message);
      setIsSaving(false);
      return;
    }

    try {
      await createMutation.mutateAsync({
        source_id: editValue.source.id,
        target_id: editValue.target.id,
        relationship_type: editValue.predicate,
      });
      toast("success", "Relationship updated");
      setMode("view");
    } catch (error) {
      const message =
        error instanceof ApiError ? error.detail : "Failed to create updated relationship — the original has been removed";
      toast("error", message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!relationship) return;
    try {
      await deleteMutation.mutateAsync(relationship.id);
      toast("success", relationshipsCopy.delete.successToast);
    } catch (error) {
      const message =
        error instanceof ApiError ? error.detail : "Failed to delete relationship";
      toast("error", message);
    }
  };

  if (!relationship) return null;

  const canSave =
    !!editValue.source?.id && !!editValue.target?.id && !!editValue.predicate && !isSaving;

  return (
    <>
      <InlineInspector
        eyebrow="relationship"
        title={`${sourceName} → ${targetName}`}
        id={relationship.id}
        mode={mode}
        onEdit={handleEditStart}
        onDone={() => {
          if (mode === "edit") void handleSave();
          else setMode("view");
        }}
        onDelete={() => setShowDeleteConfirm(true)}
        editNote={false}
        data-testid="relationship-inspector"
      >
        {mode === "view" ? (
          <>
            <InspectorPanel.Section title="Details">
              <div className="drawer-triple" data-testid="relationship-triple">
                <span className="drawer-triple-node">{sourceName}</span>
                <span className="drawer-triple-predicate">{propertyName}</span>
                <span className="drawer-triple-node">{targetName}</span>
              </div>
            </InspectorPanel.Section>
            <InspectorPanel.Section title="Provenance">
              <KVGrid
                rows={[
                  {
                    key: "Created",
                    value: new Date(relationship.created_at ?? "").toLocaleDateString(),
                  },
                  { key: "Confidence", value: "—" },
                  { key: "Source", value: "—" },
                ]}
              />
            </InspectorPanel.Section>
          </>
        ) : (
          <InspectorPanel.Section title="Edit Relationship">
            <div className="stack">
              <RelationshipBuilder
                value={editValue}
                onChange={setEditValue}
                sourceResults={sourcePickerResults}
                targetResults={targetPickerResults}
                sourceQuery={sourceQuery}
                onSourceQueryChange={setSourceQuery}
                targetQuery={targetQuery}
                onTargetQueryChange={setTargetQuery}
                predicates={predicates}
                onSourceClear={() => {
                  setSourceQuery("");
                  setEditValue((v) => ({ ...v, source: undefined }));
                }}
                onTargetClear={() => {
                  setTargetQuery("");
                  setEditValue((v) => ({ ...v, target: undefined }));
                }}
              />
              <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setMode("view")}
                  disabled={isSaving}
                  data-testid="relationship-edit-cancel"
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => void handleSave()}
                  disabled={!canSave}
                  data-testid="relationship-edit-save"
                >
                  {isSaving ? "Saving…" : "Save"}
                </Button>
              </div>
            </div>
          </InspectorPanel.Section>
        )}
      </InlineInspector>

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        title={relationshipsCopy.delete.confirmTitle}
        message="This relationship and all its instances will be permanently deleted."
        confirmLabel={relationshipsCopy.delete.confirmButton}
        onConfirm={() => {
          void handleDelete();
        }}
        variant="danger"
      />
    </>
  );
}
