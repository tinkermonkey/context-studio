import { useState, useEffect, useRef } from "react";
import { Loader, CheckCircle, AlertCircle } from "lucide-react";
import { InspectorPanel, TextInput as Input, TextArea as Textarea, Select, KVGrid, Button } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useUpdateClass, useDeleteClass, useMoveClass } from "@/api/hooks/ontology/useClasses";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useAutosave } from "@/hooks/useAutosave";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { TypeToConfirmDialog } from "@/components/ui/TypeToConfirmDialog";
import { useIndividuals } from "@/api/hooks/ontology/useIndividuals";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
import { ApiError } from "@/api/client/interceptors";
import { classesCopy } from "@/routes/app/schema/classes/-copy";
import { formatTimeAgo } from "@/utils/dateFormatting";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];

interface ClassDrawerProps {
  classData: ClassResponse | null;
  onClose?: () => void;
}

export function ClassDrawer({ classData }: ClassDrawerProps) {
  const [title, setTitle] = useState(classData?.title ?? "");
  const [description, setDescription] = useState(classData?.description ?? "");
  const [domainId, setDomainId] = useState(classData?.concept_scheme_id ?? "");
  const [parentClassId, setParentClassId] = useState(classData?.parent_class_id ?? "");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const lastSavedAtRef = useRef<Date | null>(null);

  const { toast } = useToasts();
  const updateMutation = useUpdateClass();
  const deleteMutation = useDeleteClass();
  const moveMutation = useMoveClass();
  const { data: schemesResponse } = useSchemes();
  const schemes = schemesResponse?.items || [];
  const { data: classesResponse } = useClasses();
  const allClasses = classesResponse?.items || [];
  const {
    data: individualsResponse,
    error: individualsError,
    refetch: refetchIndividuals,
  } = useIndividuals({
    class_id: classData?.id,
  });

  const {
    data: relationshipsResponse,
    error: relationshipsError,
    refetch: refetchRelationships,
  } = useRelationships();

  const { performDelete, undo } = useUndoDelete({
    onDelete: (id: string) => deleteMutation.mutateAsync(id),
    onDeleteError: (id: string, error: Error) => {
      toast("error", `Failed to delete class: ${error.message}`);
    },
    undoWindowMs: 8000,
  });

  const handleSchemeChange = async (newSchemeId: string) => {
    if (!classData || !newSchemeId) return;
    try {
      await moveMutation.mutateAsync({
        id: classData.id,
        data: { target_scheme_id: newSchemeId },
      });
      setDomainId(newSchemeId);
      toast("success", "Class moved to new domain");
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Failed to move class";
      toast("error", message);
    }
  };

  useEffect(() => {
    setTitle(classData?.title ?? "");
    setDescription(classData?.description ?? "");
    setDomainId(classData?.concept_scheme_id ?? "");
    setParentClassId(classData?.parent_class_id ?? "");
    lastSavedAtRef.current = null;
  }, [classData]);

  const isDirty = title !== classData?.title || description !== classData?.description;

  const updateData = {
    title,
    description,
  };

  const { status } = useAutosave({
    data: updateData,
    mutationFn: async () => {
      if (!classData || !isDirty) return;
      await updateMutation.mutateAsync({
        id: classData.id,
        data: {
          title: title || undefined,
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
    if (classData) {
      setTitle(classData.title);
      setDescription(classData.description ?? "");
      setDomainId(classData.concept_scheme_id);
      setParentClassId(classData.parent_class_id ?? "");
    }
  };

  const handleDelete = async () => {
    if (!classData) return;
    await performDelete(classData.id);
    toast("success", classesCopy.delete.successToast, "Undo", {
      action: {
        label: "Undo",
        onAction: undo,
      },
      autoDismissMs: 8000,
    });
  };

  const handleDeleteClick = () => {
    if (individualCount > 0) {
      setShowDeleteConfirm(true);
    } else {
      void handleDelete();
    }
  };

  if (!classData) return null;

  const selectedParent = allClasses.find((c) => c.id === parentClassId);

  const autosaveState = status === "idle" ? undefined : (status as "saving" | "saved" | "error");

  const propertyCount = classData.data_properties?.length ?? 0;
  const individualCount = individualsResponse?.total ?? 0;

  const allRelationships = relationshipsResponse?.items || [];
  const relationshipsForClass = allRelationships.filter(
    (rel: any) => rel.source_id === classData.id || rel.target_id === classData.id,
  );
  const relationshipCount = relationshipsForClass.length;

  const inspectorActions = (
    <>
      <span data-testid="inspector-autosave-status" style={{ display: "contents" }}>
        {autosaveState === "saving" && <Loader size={14} className="spin" />}
        {autosaveState === "saved" && lastSavedAtRef.current && (
          <span style={{ fontSize: "var(--text-xs)", color: "rgb(var(--canvas-fg-3))" }}>
            Saved {formatTimeAgo(lastSavedAtRef.current)}
          </span>
        )}
        {autosaveState === "error" && <AlertCircle size={14} style={{ color: "rgb(var(--status-rose))" }} />}
      </span>
      {isDirty && (
        <Button variant="ghost" size="sm" onClick={revert} data-testid="inspector-revert-button">
          Revert
        </Button>
      )}
      <Button variant="danger" size="sm" onClick={handleDeleteClick} data-testid="inspector-delete-button">
        Delete
      </Button>
    </>
  );

  return (
    <>
      <InspectorPanel
        eyebrow="class"
        title={classData.title}
        id={classData.id}
        actions={inspectorActions}
        data-testid="class-inspector"
      >
        <InspectorPanel.Section title="Details">
          {individualsError && (
            <ErrorBanner
              error={individualsError as Error}
              onRetry={() => refetchIndividuals()}
              message="Failed to load individuals"
              compact
            />
          )}
          {relationshipsError && (
            <ErrorBanner
              error={relationshipsError as Error}
              onRetry={() => refetchRelationships()}
              message="Failed to load relationships"
              compact
            />
          )}
          <div>
            <label className="form-group-label">ID</label>
            <Input type="text" value={classData.id} disabled mono data-testid="class-drawer-id" />
          </div>

          <div>
            <label className="form-group-label">Name</label>
            <Input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              data-testid="class-drawer-name-input"
            />
          </div>

          <div>
            <label className="form-group-label">Description</label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              data-testid="class-drawer-description-input"
              rows={4}
            />
          </div>

          <div>
            <label className="form-group-label">Domain</label>
            <Select
              value={domainId}
              onChange={(e) => handleSchemeChange(e.target.value)}
              disabled={moveMutation.isPending}
              data-testid="class-drawer-domain-select"
            >
              <option value="">Select a domain</option>
              {schemes.map((scheme) => (
                <option key={scheme.id} value={scheme.id}>
                  {scheme.title}
                </option>
              ))}
            </Select>
          </div>

          <div>
            <label className="form-group-label">Parent Class</label>
            {selectedParent ? (
              <div
                className="flex-row-center"
                style={{
                  padding: "var(--space-2) var(--space-3)",
                  background: "var(--canvas-bg-2)",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "var(--text-sm)",
                }}
              >
                <span className="mono" style={{ flex: 1, fontSize: "var(--text-xs)" }}>
                  {selectedParent.id.slice(0, 8)}
                </span>
                <span>{selectedParent.title}</span>
              </div>
            ) : (
              <div
                className="flex-row-center"
                style={{
                  padding: "var(--space-2) var(--space-3)",
                  background: "var(--canvas-bg-2)",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "var(--text-sm)",
                  color: "var(--canvas-fg-3)",
                }}
              >
                —
              </div>
            )}
          </div>
        </InspectorPanel.Section>

        <InspectorPanel.Section title="Metrics">
          <KVGrid
            rows={[
              { key: "Properties", value: String(propertyCount) },
              { key: "Relationships", value: String(relationshipCount) },
              { key: "Individuals", value: String(individualCount) },
              { key: "Created", value: new Date(classData.created_at ?? "").toLocaleDateString() },
            ]}
          />
        </InspectorPanel.Section>
      </InspectorPanel>

      <TypeToConfirmDialog
        open={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        title={classesCopy.delete.confirmTitle}
        message={
          individualCount > 0
            ? `This will remove the class and all ${individualCount} individual${
                individualCount === 1 ? "" : "s"
              } that reference it. This cannot be undone.`
            : "This will remove the class. This cannot be undone."
        }
        confirmText={classData.title}
        confirmLabel={classesCopy.delete.confirmButton}
        onConfirm={handleDelete}
        onError={(error) => {
          toast("error", `Delete failed: ${error.message}`);
        }}
        isLoading={deleteMutation.isPending}
        data-testid="class-delete-confirm"
      />
    </>
  );
}
