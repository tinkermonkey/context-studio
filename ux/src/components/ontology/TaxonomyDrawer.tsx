import { useState, useEffect, useRef } from "react";
import {
  InspectorPanel,
  TextInput as Input,
  KVGrid,
  Button,
  VersionPill,
  ConfirmDialog,
} from "@tinkermonkey/heimdall-ui";
import { SuggestField } from "./suggesters";
import { InlineInspector } from "@/components/ui/InlineInspector";
import { useUpdateTaxonomy, useDeleteTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { useAutosave } from "@/hooks/useAutosave";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { taxonomiesCopy } from "@/routes/app/schema/taxonomies/-copy";
import { TaxonomyPublishDialog } from "./TaxonomyPublishDialog";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];

interface TaxonomyDrawerProps {
  taxonomy: TaxonomyResponse | null;
  onClose?: () => void;
}

export function TaxonomyDrawer({ taxonomy }: TaxonomyDrawerProps) {
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [title, setTitle] = useState(taxonomy?.title ?? "");
  const [description, setDescription] = useState(taxonomy?.description ?? "");
  const [showPublishDialog, setShowPublishDialog] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const lastSavedAtRef = useRef<Date | null>(null);

  const { toast } = useToasts();
  const updateMutation = useUpdateTaxonomy();
  const deleteMutation = useDeleteTaxonomy();
  const { performDelete, undo } = useUndoDelete({
    onDelete: (id: string) => deleteMutation.mutateAsync(id),
    onDeleteError: (id: string, error: Error) => {
      toast("error", `Failed to delete taxonomy: ${error.message}`);
    },
    undoWindowMs: 8000,
  });

  useEffect(() => {
    setTitle(taxonomy?.title ?? "");
    setDescription(taxonomy?.description ?? "");
    lastSavedAtRef.current = null;
    setMode("view");
  }, [taxonomy]);

  const isDirty = title !== taxonomy?.title || description !== taxonomy?.description;

  const updateData = { title, description };

  const { status } = useAutosave({
    data: updateData,
    mutationFn: async () => {
      if (!taxonomy || !isDirty || mode !== "edit") return;
      await updateMutation.mutateAsync({
        id: taxonomy.id,
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
    if (!taxonomy) return;
    await performDelete(taxonomy.id);
    toast("success", taxonomiesCopy.delete.successToast, "Undo", {
      action: {
        label: "Undo",
        onAction: undo,
      },
      autoDismissMs: 8000,
    });
  };

  if (!taxonomy) return null;

  const autosaveStatus = status === "idle" ? undefined : (status as "saving" | "saved" | "error");

  const publishAction =
    taxonomy.status === "draft" ? (
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setShowPublishDialog(true)}
        data-testid="taxonomy-drawer-publish-button"
      >
        Publish…
      </Button>
    ) : undefined;

  return (
    <>
      <InlineInspector
        eyebrow="taxonomy"
        title={taxonomy.title}
        id={taxonomy.id}
        version={taxonomy.version}
        mode={mode}
        onEdit={() => setMode("edit")}
        onDone={() => setMode("view")}
        onDelete={() => setShowDeleteConfirm(true)}
        autosaveStatus={autosaveStatus}
        lastSavedAt={lastSavedAtRef.current}
        extraViewActions={publishAction}
        data-testid="taxonomy-inspector"
      >
        {mode === "view" ? (
          <>
            <InspectorPanel.Section title="Details">
              <KVGrid
                rows={[
                  { key: "Title", value: taxonomy.title },
                  { key: "Description", value: taxonomy.description || "—" },
                  { key: "Status", value: taxonomy.status },
                  {
                    key: "Version",
                    value: <VersionPill>v{taxonomy.version}</VersionPill>,
                  },
                  {
                    key: "Created",
                    value: new Date(taxonomy.created_at ?? "").toLocaleDateString(),
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
                    value={taxonomy.id}
                    disabled
                    mono
                    data-testid="taxonomy-drawer-id"
                  />
                </div>

                <div>
                  <label className="form-group-label">Title</label>
                  <Input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    data-testid="taxonomy-drawer-title-input"
                  />
                </div>

                <div>
                  <label className="form-group-label">Description</label>
                  <SuggestField
                    entityId={taxonomy.id}
                    value={description}
                    onChange={setDescription}
                    rows={4}
                    testId="taxonomy-drawer-description-input"
                  />
                </div>

                {isDirty && (
                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        if (taxonomy) {
                          setTitle(taxonomy.title);
                          setDescription(taxonomy.description ?? "");
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
                  { key: "Status", value: taxonomy.status },
                  { key: "Version", value: <VersionPill>v{taxonomy.version}</VersionPill> },
                  {
                    key: "Created",
                    value: new Date(taxonomy.created_at ?? "").toLocaleDateString(),
                  },
                ]}
              />
            </InspectorPanel.Section>
          </>
        )}
      </InlineInspector>

      <TaxonomyPublishDialog
        open={showPublishDialog}
        onClose={() => setShowPublishDialog(false)}
        taxonomy={taxonomy}
        onPublish={() => {
          toast(
            "success",
            taxonomiesCopy.publish.successToast(taxonomy.title, taxonomy.version + 1),
          );
          setShowPublishDialog(false);
        }}
      />

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        title={taxonomiesCopy.delete.confirmTitle}
        message="This taxonomy and all its concept schemes will be permanently deleted."
        confirmLabel={taxonomiesCopy.delete.confirmButton}
        onConfirm={() => {
          void handleDelete();
        }}
        variant="danger"
      />
    </>
  );
}
