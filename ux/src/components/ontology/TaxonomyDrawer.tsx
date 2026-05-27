import { useState, useEffect, useRef } from "react";
import { Loader, CheckCircle, AlertCircle } from "lucide-react";
import {
  InspectorPanel,
  TextInput as Input,
  TextArea as Textarea,
  Button,
  KVGrid,
  VersionPill,
} from "@tinkermonkey/heimdall-ui";
import { ConfirmDialog } from "@tinkermonkey/heimdall-ui";
import { useUpdateTaxonomy, useDeleteTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { useAutosave } from "@/hooks/useAutosave";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { taxonomiesCopy } from "@/routes/app/schema/taxonomies/-copy";
import { TaxonomyPublishDialog } from "./TaxonomyPublishDialog";
import { formatTimeAgo } from "@/utils/dateFormatting";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];

interface TaxonomyDrawerProps {
  taxonomy: TaxonomyResponse | null;
  onClose?: () => void;
}

export function TaxonomyDrawer({ taxonomy }: TaxonomyDrawerProps) {
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
  }, [taxonomy]);

  const isDirty = title !== taxonomy?.title || description !== taxonomy?.description;

  const updateData = {
    title,
    description,
  };

  const { status } = useAutosave({
    data: updateData,
    mutationFn: async () => {
      if (!taxonomy || !isDirty) return;
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

  const revert = () => {
    if (taxonomy) {
      setTitle(taxonomy.title);
      setDescription(taxonomy.description ?? "");
    }
  };

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

  const handleDeleteClick = () => {
    setShowDeleteConfirm(true);
  };

  if (!taxonomy) return null;

  const autosaveState = status === "idle" ? undefined : (status as "saving" | "saved" | "error");

  const inspectorActions = (
    <>
      {taxonomy.status === "draft" && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowPublishDialog(true)}
          data-testid="taxonomy-drawer-publish-button"
        >
          Publish…
        </Button>
      )}
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
        eyebrow="taxonomy"
        title={taxonomy.title}
        id={taxonomy.id}
        actions={inspectorActions}
        data-testid="taxonomy-inspector"
      >
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
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                data-testid="taxonomy-drawer-description-input"
                rows={4}
              />
            </div>
          </div>
        </InspectorPanel.Section>

        <InspectorPanel.Section title="Metrics">
          <KVGrid
            rows={[
              { key: "Status", value: taxonomy.status },
              { key: "Version", value: <VersionPill>v{taxonomy.version}</VersionPill> },
              { key: "Created", value: new Date(taxonomy.created_at ?? "").toLocaleDateString() },
            ]}
          />
        </InspectorPanel.Section>
      </InspectorPanel>

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
