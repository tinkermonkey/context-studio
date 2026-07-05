import { useState, useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  InspectorPanel,
  TextInput as Input,
  KVGrid,
  ConfirmDialog,
} from "@tinkermonkey/heimdall-ui";
import { InlineInspector } from "@/components/ui/InlineInspector";
import { EditableField } from "@/components/ui/EditableField";
import { SuggestField } from "@/components/ontology/suggesters/SuggestField";
import { useUpdateScheme, useDeleteScheme, useCreateScheme } from "@/api/hooks/ontology/useSchemes";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { schemesCopy } from "@/routes/app/schema/schemes/-copy";
import { ApiError } from "@/api/client/interceptors";
import type { components } from "@/api/types";

type ConceptSchemeResponse = components["schemas"]["ConceptSchemeResponse"];

interface SchemeDrawerProps {
  scheme: ConceptSchemeResponse | null;
  taxonomyName: string;
}

const CLASSES_DISPLAY_CAP = 20;

export function SchemeDrawer({ scheme, taxonomyName }: SchemeDrawerProps) {
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [descriptionDraft, setDescriptionDraft] = useState(scheme?.description ?? "");

  const navigate = useNavigate();
  const { toast } = useToasts();
  const updateMutation = useUpdateScheme();
  const deleteMutation = useDeleteScheme();
  const createMutation = useCreateScheme();
  const { data: classesResponse } = useClasses({
    concept_scheme_id: scheme?.id,
  });
  const classes = classesResponse?.items || [];

  const { performDelete, undo } = useUndoDelete({
    onDelete: (id: string) => deleteMutation.mutateAsync(id),
    onDeleteError: (id: string, error: Error) => {
      toast("error", `Failed to delete scheme: ${error.message}`);
    },
    undoWindowMs: 8000,
  });

  useEffect(() => {
    setMode("view");
    setDescriptionDraft(scheme?.description ?? "");
  }, [scheme]);

  const handleDelete = async () => {
    if (!scheme) return;
    await performDelete(scheme.id);
    toast("success", schemesCopy.delete.successToast, "Undo", {
      action: {
        label: "Undo",
        onAction: undo,
      },
      autoDismissMs: 8000,
    });
  };

  if (!scheme) return null;

  const handleSaveDescription = async (value: string) => {
    if (value === (scheme.description ?? "")) return;
    try {
      await updateMutation.mutateAsync({ id: scheme.id, data: { description: value || null } });
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Failed to save description";
      toast("error", message);
      setDescriptionDraft(scheme.description ?? "");
    }
  };

  const handleDuplicate = async () => {
    try {
      await createMutation.mutateAsync({
        taxonomyId: scheme.taxonomy_id,
        data: { title: `Copy of ${scheme.title}`, description: scheme.description ?? undefined },
      });
      toast("success", "Concept scheme duplicated");
    } catch (error) {
      const message =
        error instanceof ApiError ? error.detail : "Failed to duplicate concept scheme";
      toast("error", message);
    }
  };

  const classCountText =
    classes.length === 1
      ? "This will delete 1 class"
      : `This will delete ${classes.length} classes`;
  const deleteMessage =
    classes.length > 0 ? classCountText + " and cannot be undone." : "This cannot be undone.";

  return (
    <>
      <InlineInspector
        eyebrow="concept scheme"
        title={scheme.title}
        id={scheme.id}
        mode={mode}
        onEdit={() => setMode("edit")}
        onDone={() => setMode("view")}
        onDelete={() => setShowDeleteConfirm(true)}
        onDuplicate={() => {
          void handleDuplicate();
        }}
        data-testid="scheme-inspector"
      >
        {mode === "view" ? (
          <>
            <InspectorPanel.Section title="Details">
              <KVGrid
                rows={[
                  { key: "Title", value: scheme.title },
                  { key: "Parent Taxonomy", value: taxonomyName },
                  { key: "Description", value: scheme.description || "—" },
                  {
                    key: "Created",
                    value: new Date(scheme.created_at ?? "").toLocaleDateString(),
                  },
                ]}
              />
            </InspectorPanel.Section>
            <InspectorPanel.Section title={`Classes (${classes.length})`}>
              {classes.length === 0 ? (
                <p className="drawer-empty-note" data-testid="scheme-classes-empty">
                  No classes
                </p>
              ) : (
                <div className="stack" data-testid="scheme-classes-list">
                  {classes.slice(0, CLASSES_DISPLAY_CAP).map((cls) => (
                    <div
                      key={cls.id}
                      className="drawer-list-item"
                      data-testid={`scheme-class-${cls.id}`}
                    >
                      {cls.title}
                    </div>
                  ))}
                  {classes.length > CLASSES_DISPLAY_CAP && (
                    <button
                      type="button"
                      className="drawer-show-all-link"
                      onClick={() => navigate({ to: "/app/schema/classes" })}
                      data-testid="scheme-classes-show-all"
                    >
                      Show all {classes.length} classes
                    </button>
                  )}
                </div>
              )}
            </InspectorPanel.Section>
          </>
        ) : (
          <>
            <InspectorPanel.Section title="Details">
              <div className="stack">
                <div>
                  <label className="form-group-label">ID</label>
                  <Input
                    type="text"
                    value={scheme.id}
                    disabled
                    mono
                    data-testid="scheme-drawer-id"
                  />
                </div>

                <EditableField
                  label="Title"
                  value={scheme.title}
                  onSave={async (v) => {
                    await updateMutation.mutateAsync({ id: scheme.id, data: { title: v } });
                  }}
                  validate={(v) => (!v.trim() ? "Title is required" : undefined)}
                  data-testid="scheme-drawer-title-field"
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
                    entityId={scheme.id}
                    value={descriptionDraft}
                    onChange={setDescriptionDraft}
                    rows={4}
                    testId="scheme-drawer-description-input"
                  />
                </div>

                <div>
                  <label className="form-group-label">Parent Taxonomy</label>
                  <Input
                    type="text"
                    value={taxonomyName}
                    disabled
                    data-testid="scheme-drawer-parent-taxonomy"
                  />
                </div>
              </div>
            </InspectorPanel.Section>

            <InspectorPanel.Section title="Metrics">
              <KVGrid
                rows={[
                  {
                    key: "Created",
                    value: new Date(scheme.created_at ?? "").toLocaleDateString(),
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
        title={schemesCopy.delete.confirmTitle}
        message={<span data-testid="scheme-delete-confirm">{deleteMessage}</span>}
        confirmLabel={schemesCopy.delete.confirmButton}
        onConfirm={() => {
          void handleDelete();
        }}
        variant="danger"
      />
    </>
  );
}
