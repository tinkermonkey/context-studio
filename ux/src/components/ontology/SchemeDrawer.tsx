import { useState, useEffect, useRef } from "react";
import { Drawer } from "@/components/ui/Drawer";
import { TextInput as Input, TextArea as Textarea, KVGrid } from "@tinkermonkey/heimdall-ui";
import { ConfirmDialog } from "@tinkermonkey/heimdall-ui";
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
  onClose: () => void;
}

export function SchemeDrawer({ scheme, taxonomyName, onClose }: SchemeDrawerProps) {
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
  }, [scheme]);

  const isDirty = title !== scheme?.title || description !== scheme?.description;

  const updateData = {
    title,
    description,
  };

  const { status } = useAutosave({
    data: updateData,
    mutationFn: async () => {
      if (!scheme || !isDirty) return;
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

  const revert = () => {
    if (scheme) {
      setTitle(scheme.title);
      setDescription(scheme.description ?? "");
    }
  };

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
    onClose();
  };

  const handleDeleteClick = () => {
    setShowDeleteConfirm(true);
  };

  if (!scheme) return null;

  const autosaveState = status === "idle" ? undefined : (status as "saving" | "saved" | "error");

  const classCountText =
    classes.length === 1
      ? "This will delete 1 class"
      : `This will delete ${classes.length} classes`;
  const deleteMessage =
    classes.length > 0 ? classCountText + " and cannot be undone." : "This cannot be undone.";

  return (
    <>
      <Drawer
        open={!!scheme}
        onClose={onClose}
        title={scheme.title}
        autosaveState={autosaveState}
        isDirty={isDirty}
        lastSavedAt={lastSavedAtRef.current || undefined}
        onRevert={revert}
        onDelete={handleDeleteClick}
        data-testid="scheme-drawer"
      >
        <div className="stack-lg">
          <div>
            <label className="form-group-label">ID</label>
            <Input type="text" value={scheme.id} disabled mono data-testid="scheme-drawer-id" />
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
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              data-testid="scheme-drawer-description-input"
              rows={4}
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

          <KVGrid
            rows={[
              { key: "Created", value: new Date(scheme.created_at ?? "").toLocaleDateString() },
            ]}
          />
        </div>
      </Drawer>

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        title={schemesCopy.delete.confirmTitle}
        message={deleteMessage}
        confirmLabel={schemesCopy.delete.confirmButton}
        onConfirm={() => { void handleDelete(); }}
        variant="danger"
      />
    </>
  );
}
