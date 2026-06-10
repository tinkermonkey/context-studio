import { useState, useEffect } from "react";
import {
  InspectorPanel,
  TextInput as Input,
  KVGrid,
  Button,
  VersionPill,
  ConfirmDialog,
} from "@tinkermonkey/heimdall-ui";
import { InlineInspector } from "@/components/ui/InlineInspector";
import { EditableField } from "@/components/ui/EditableField";
import { useUpdateTaxonomy, useDeleteTaxonomy, useCreateTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { taxonomiesCopy } from "@/routes/app/schema/taxonomies/-copy";
import { TaxonomyPublishDialog } from "./TaxonomyPublishDialog";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];

interface TaxonomyDrawerProps {
  taxonomy: TaxonomyResponse | null;
}

export function TaxonomyDrawer({ taxonomy }: TaxonomyDrawerProps) {
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [showPublishDialog, setShowPublishDialog] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { toast } = useToasts();
  const updateMutation = useUpdateTaxonomy();
  const deleteMutation = useDeleteTaxonomy();
  const createMutation = useCreateTaxonomy();
  const { performDelete, undo } = useUndoDelete({
    onDelete: (id: string) => deleteMutation.mutateAsync(id),
    onDeleteError: (id: string, error: Error) => {
      toast("error", `Failed to delete taxonomy: ${error.message}`);
    },
    undoWindowMs: 8000,
  });

  useEffect(() => {
    setMode("view");
  }, [taxonomy]);

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

  const handleDuplicate = async () => {
    try {
      await createMutation.mutateAsync({ title: `Copy of ${taxonomy.title}`, description: taxonomy.description ?? undefined });
      toast("success", "Taxonomy duplicated");
    } catch {
      toast("error", "Failed to duplicate taxonomy");
    }
  };

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
        onDuplicate={() => { void handleDuplicate(); }}
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

                <EditableField
                  label="Title"
                  value={taxonomy.title}
                  onSave={async (v) => {
                    await updateMutation.mutateAsync({ id: taxonomy.id, data: { title: v } });
                  }}
                  validate={(v) => !v.trim() ? "Title is required" : undefined}
                  data-testid="taxonomy-drawer-title-field"
                />

                <EditableField
                  label="Description"
                  type="textarea"
                  rows={4}
                  value={taxonomy.description ?? ""}
                  onSave={async (v) => {
                    await updateMutation.mutateAsync({ id: taxonomy.id, data: { description: v || null } });
                  }}
                  data-testid="taxonomy-drawer-description-field"
                />
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
