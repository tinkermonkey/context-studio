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
import { useUpdateScheme, useDeleteScheme } from "@/api/hooks/ontology/useSchemes";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useAutosave } from "@/hooks/useAutosave";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { schemesCopy } from "@/routes/app/schema/schemes/-copy";
import type { components } from "@/api/types";

type ConceptSchemeResponse = components["schemas"]["ConceptSchemeResponse"];

interface SchemeDrawerProps {
  scheme: ConceptSchemeResponse | null;
  taxonomyName: string;
  onClose?: () => void;
}

export function SchemeDrawer({ scheme, taxonomyName }: SchemeDrawerProps) {
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [title, setTitle] = useState(scheme?.title ?? "");
  const [description, setDescription] = useState(scheme?.description ?? "");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const lastSavedAtRef = useRef<Date | null>(null);

  const { toast } = useToasts();
  const updateMutation = useUpdateScheme();
  const deleteMutation = useDeleteScheme();
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
    setTitle(scheme?.title ?? "");
    setDescription(scheme?.description ?? "");
    lastSavedAtRef.current = null;
    setMode("view");
  }, [scheme]);

  const isDirty = title !== scheme?.title || description !== scheme?.description;

  const updateData = { title, description };

  const { status } = useAutosave({
    data: updateData,
    mutationFn: async () => {
      if (!scheme || !isDirty || mode !== "edit") return;
      await updateMutation.mutateAsync({
        id: scheme.id,
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

  const autosaveStatus = status === "idle" ? undefined : (status as "saving" | "saved" | "error");

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
        autosaveStatus={autosaveStatus}
        lastSavedAt={lastSavedAtRef.current}
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
                  { key: "Classes", value: String(classes.length) },
                  {
                    key: "Created",
                    value: new Date(scheme.created_at ?? "").toLocaleDateString(),
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
                  <label className="form-group-label">ID</label>
                  <Input
                    type="text"
                    value={scheme.id}
                    disabled
                    mono
                    data-testid="scheme-drawer-id"
                  />
                </div>

                <div>
                  <label className="form-group-label">Title</label>
                  <Input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    data-testid="scheme-drawer-title-input"
                  />
                </div>

                <div>
                  <label className="form-group-label">Description</label>
                  <SuggestField
                    entityId={scheme.id}
                    value={description}
                    onChange={setDescription}
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

                {isDirty && (
                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        if (scheme) {
                          setTitle(scheme.title);
                          setDescription(scheme.description ?? "");
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
        message={deleteMessage}
        confirmLabel={schemesCopy.delete.confirmButton}
        onConfirm={() => {
          void handleDelete();
        }}
        variant="danger"
      />
    </>
  );
}
