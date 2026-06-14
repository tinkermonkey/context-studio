import { useState, useEffect } from "react";
import {
  InspectorPanel,
  TextInput as Input,
  KVGrid,
  ConfirmDialog,
  SegmentedControl,
} from "@tinkermonkey/heimdall-ui";
import { InlineInspector } from "@/components/ui/InlineInspector";
import { EditableField } from "@/components/ui/EditableField";
import { SuggestField } from "@/components/ontology/suggesters/SuggestField";
import {
  useUpdateProperty,
  useDeleteProperty,
  useCreateProperty,
} from "@/api/hooks/ontology/useProperties";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { propertiesCopy } from "@/routes/app/schema/properties/-copy";
import { ApiError } from "@/api/client/interceptors";
import type { components } from "@/api/types";

type PropertyDefinitionResponse = components["schemas"]["PropertyDefinitionResponse"];

interface PropertyDrawerProps {
  property: PropertyDefinitionResponse | null;
}

const RELEVANCE_OPTIONS = [
  { value: "none", label: "Not Evaluated" },
  { value: "true", label: "Relevant" },
  { value: "false", label: "Irrelevant" },
];

function relevanceToString(value: boolean | null | undefined): string {
  if (value === true) return "true";
  if (value === false) return "false";
  return "none";
}

function stringToRelevance(value: string): boolean | null {
  if (value === "true") return true;
  if (value === "false") return false;
  return null;
}

export function PropertyDrawer({ property }: PropertyDrawerProps) {
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [descriptionDraft, setDescriptionDraft] = useState(property?.description ?? "");
  const [relevanceValue, setRelevanceValue] = useState<boolean | null>(
    property?.is_relevant ?? null,
  );

  const { toast } = useToasts();
  const updateMutation = useUpdateProperty();
  const deleteMutation = useDeleteProperty();
  const createMutation = useCreateProperty();

  const { data: relationshipsResponse } = useRelationships({ property_id: property?.id });
  const propertyRelationships = relationshipsResponse?.items || [];
  const { data: classesResponse } = useClasses();
  const classMap = new Map((classesResponse?.items || []).map((c) => [c.id, c.title]));

  const { performDelete, undo } = useUndoDelete({
    onDelete: (id: string) => deleteMutation.mutateAsync(id),
    onDeleteError: (id: string, error: Error) => {
      toast("error", `Failed to delete property: ${error.message}`);
    },
    undoWindowMs: 8000,
  });

  useEffect(() => {
    setMode("view");
    setDescriptionDraft(property?.description ?? "");
    setRelevanceValue(property?.is_relevant ?? null);
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
      await createMutation.mutateAsync({
        identifier: baseIdentifier,
        title: `Copy of ${property.title}`,
        description: property.description ?? undefined,
      });
      toast("success", "Property duplicated");
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Failed to duplicate property";
      toast("error", message);
    }
  };

  const handleSaveDescription = async (value: string) => {
    if (value === (property.description ?? "")) return;
    try {
      await updateMutation.mutateAsync({ id: property.id, data: { description: value || null } });
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Failed to save description";
      toast("error", message);
      setDescriptionDraft(property.description ?? "");
    }
  };

  const handleRelevanceChange = async (value: string) => {
    const newIsRelevant = stringToRelevance(value);
    setRelevanceValue(newIsRelevant);
    try {
      await updateMutation.mutateAsync({ id: property.id, data: { is_relevant: newIsRelevant } });
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Failed to update relevance";
      toast("error", message);
      setRelevanceValue(property.is_relevant ?? null);
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
        onDuplicate={() => {
          void handleDuplicate();
        }}
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

            <InspectorPanel.Section title="Used By Relationships">
              {propertyRelationships.length === 0 ? (
                <KVGrid rows={[{ key: "Relationships", value: "None" }]} />
              ) : (
                <KVGrid
                  rows={[
                    { key: "Total", value: String(propertyRelationships.length) },
                    ...propertyRelationships.slice(0, 5).map((rel) => ({
                      key: classMap.get(rel.source_id) ?? rel.source_id.slice(0, 8),
                      value: `→ ${classMap.get(rel.target_id) ?? rel.target_id.slice(0, 8)}`,
                    })),
                  ]}
                />
              )}
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
                  validate={(v) => (!v.trim() ? "Title is required" : undefined)}
                  data-testid="property-drawer-title-field"
                />

                <div
                  onBlur={(e) => {
                    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                      void handleSaveDescription(descriptionDraft);
                    }
                  }}
                >
                  <label className="form-group-label">Description</label>
                  <SuggestField
                    entityId={property.id}
                    value={descriptionDraft}
                    onChange={setDescriptionDraft}
                    rows={4}
                    testId="property-drawer-description-input"
                  />
                </div>

                <div>
                  <label className="form-group-label">Relevance</label>
                  <SegmentedControl
                    value={relevanceToString(relevanceValue)}
                    onChange={(v) => {
                      void handleRelevanceChange(String(v));
                    }}
                    options={RELEVANCE_OPTIONS}
                    data-testid="property-drawer-relevance-control"
                  />
                </div>
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
        message={
          <span data-testid="property-delete-confirm">
            This property will be permanently deleted.
          </span>
        }
        confirmLabel={propertiesCopy.delete.confirmButton}
        onConfirm={() => {
          void handleDelete();
        }}
        variant="danger"
      />
    </>
  );
}
