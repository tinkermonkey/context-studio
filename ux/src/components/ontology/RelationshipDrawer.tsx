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
import {
  useDeleteRelationship,
  useCreateRelationship,
} from "@/api/hooks/ontology/useRelationships";
import { useProperties, usePropertiesByIds } from "@/api/hooks/ontology/useProperties";
import { useClassSearch } from "@/api/hooks/ontology/useEntitySearch";
import { useToasts } from "@/components/ui/Toast";
import { ApiError } from "@/api/client/interceptors";
import { relationshipsCopy } from "@/routes/app/schema/relationships/-copy";
import type { components } from "@/api/types";
import { PREDICATE_CHOICES_LIMIT } from "@/api/config";
import {
  attributeEntries,
  formatAttributeValue,
} from "@/components/ontology/RelationshipAttributes";

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
  const isEditing = mode === "edit";
  // Source/target pickers search classes server-side as the user types.
  const { data: sourceSearch } = useClassSearch(sourceQuery, undefined, { enabled: isEditing });
  const { data: targetSearch } = useClassSearch(targetQuery, undefined, { enabled: isEditing });
  const { data: currentPropertyResponse } = usePropertiesByIds([
    relationship?.property_definition_id,
  ]);
  const { data: predicateChoicesResponse } = useProperties(
    undefined,
    { limit: PREDICATE_CHOICES_LIMIT, sort_by: "title" },
    { enabled: isEditing },
  );

  const currentProperty = currentPropertyResponse?.items?.[0];
  const attributes = attributeEntries(relationship?.attributes);
  const predicateChoices = predicateChoicesResponse?.items ?? [];
  const predicates =
    predicateChoices.length > 0
      ? [
          ...new Set([
            ...(currentProperty ? [currentProperty.identifier] : []),
            ...predicateChoices.map((p) => p.identifier),
          ]),
        ]
      : ["related_to", "contains", "depends_on", "is_used_by"];

  const sourcePickerResults = (sourceSearch?.items ?? []).map((c) => ({
    id: c.id,
    label: c.title,
  }));
  const targetPickerResults = (targetSearch?.items ?? []).map((c) => ({
    id: c.id,
    label: c.title,
  }));

  const handleEditStart = () => {
    if (!relationship) return;
    setEditValue({
      source: { id: relationship.source_id, label: sourceName },
      target: { id: relationship.target_id, label: targetName },
      predicate: currentProperty?.identifier ?? "",
    });
    setSourceQuery("");
    setTargetQuery("");
    setMode("edit");
  };

  const handleSave = async () => {
    if (!relationship) return;
    if (!editValue.source?.id || !editValue.target?.id || !editValue.predicate) {
      toast("error", "Source, target, and predicate are all required");
      return;
    }

    const unchanged =
      editValue.source.id === relationship.source_id &&
      editValue.target.id === relationship.target_id &&
      editValue.predicate === (currentProperty?.identifier ?? "");

    if (unchanged) {
      setMode("view");
      return;
    }

    // There is no relationship-update endpoint, so editing is create + delete.
    // Create the replacement FIRST so a failure cannot destroy the original.
    setIsSaving(true);
    try {
      await createMutation.mutateAsync({
        source_id: editValue.source.id,
        target_id: editValue.target.id,
        relationship_type: editValue.predicate,
        // Carried over: a replacement keeps the edge's values (refused if the new type disallows them).
        attributes: relationship.attributes,
      });
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Failed to update relationship";
      toast("error", message);
      setIsSaving(false);
      return; // original is left untouched
    }

    // Replacement exists; now remove the original triple.
    try {
      await deleteMutation.mutateAsync(relationship.id);
      toast("success", "Relationship updated");
    } catch {
      toast(
        "error",
        "Updated relationship created, but the original could not be removed — you may now have a duplicate.",
      );
    } finally {
      setMode("view");
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!relationship) return;
    try {
      await deleteMutation.mutateAsync(relationship.id);
      toast("success", relationshipsCopy.delete.successToast);
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Failed to delete relationship";
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
            {attributes.length > 0 && (
              <InspectorPanel.Section title="Attributes">
                <KVGrid
                  data-testid="relationship-attributes-grid"
                  rows={attributes.map(([name, value]) => ({
                    key: name,
                    value: formatAttributeValue(value),
                  }))}
                />
              </InspectorPanel.Section>
            )}
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
        message={
          <span data-testid="relationship-delete-confirm">
            This relationship and all its instances will be permanently deleted.
          </span>
        }
        confirmLabel={relationshipsCopy.delete.confirmButton}
        onConfirm={() => {
          void handleDelete();
        }}
        variant="danger"
      />
    </>
  );
}
