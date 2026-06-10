import { useState, useEffect, useRef } from "react";
import {
  InspectorPanel,
  TextInput as Input,
  Select,
  KVGrid,
  Button,
} from "@tinkermonkey/heimdall-ui";
import { SuggestField, RelationshipSuggester, GroundingSection } from "./suggesters";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { InlineInspector } from "@/components/ui/InlineInspector";
import { TypeToConfirmDialog } from "@/components/ui/TypeToConfirmDialog";
import { useUpdateClass, useDeleteClass, useMoveClass } from "@/api/hooks/ontology/useClasses";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useAutosave } from "@/hooks/useAutosave";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { useIndividuals } from "@/api/hooks/ontology/useIndividuals";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
import { ApiError } from "@/api/client/interceptors";
import { classesCopy } from "@/routes/app/schema/classes/-copy";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];

interface ClassDrawerProps {
  classData: ClassResponse | null;
  onClose?: () => void;
}

export function ClassDrawer({ classData }: ClassDrawerProps) {
  const [mode, setMode] = useState<"view" | "edit">("view");
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
    setMode("view");
  }, [classData]);

  const isDirty = title !== classData?.title || description !== classData?.description;

  const updateData = { title, description };

  const { status } = useAutosave({
    data: updateData,
    mutationFn: async () => {
      if (!classData || !isDirty || mode !== "edit") return;
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

  if (!classData) return null;

  const selectedScheme = schemes.find((s) => s.id === domainId);
  const selectedParent = allClasses.find((c) => c.id === parentClassId);
  const autosaveStatus = status === "idle" ? undefined : (status as "saving" | "saved" | "error");
  const propertyCount = classData.data_properties?.length ?? 0;
  const individualCount = individualsResponse?.total ?? 0;
  const allRelationships = relationshipsResponse?.items || [];
  const relationshipCount = allRelationships.filter(
    (rel: any) => rel.source_id === classData.id || rel.target_id === classData.id,
  ).length;

  return (
    <>
      <InlineInspector
        eyebrow="class"
        title={classData.title}
        id={classData.id}
        mode={mode}
        onEdit={() => setMode("edit")}
        onDone={() => setMode("view")}
        onDelete={() => setShowDeleteConfirm(true)}
        autosaveStatus={autosaveStatus}
        lastSavedAt={lastSavedAtRef.current}
        data-testid="class-inspector"
      >
        {mode === "view" ? (
          <>
            <InspectorPanel.Section title="Details">
              <KVGrid
                rows={[
                  { key: "Name", value: classData.title },
                  { key: "Domain", value: selectedScheme?.title ?? "—" },
                  { key: "Parent Class", value: selectedParent?.title ?? "—" },
                  { key: "Description", value: classData.description || "—" },
                ]}
              />
            </InspectorPanel.Section>
            <InspectorPanel.Section title="Metrics">
              <KVGrid
                rows={[
                  { key: "Properties", value: String(propertyCount) },
                  { key: "Relationships", value: String(relationshipCount) },
                  { key: "Individuals", value: String(individualCount) },
                  {
                    key: "Created",
                    value: new Date(classData.created_at ?? "").toLocaleDateString(),
                  },
                ]}
              />
            </InspectorPanel.Section>
          </>
        ) : (
          <>
            <InspectorPanel.Section title="Details">
              <div className="stack">
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
                  <Input
                    type="text"
                    value={classData.id}
                    disabled
                    mono
                    data-testid="class-drawer-id"
                  />
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
                  <SuggestField
                    entityId={classData.id}
                    value={description}
                    onChange={setDescription}
                    rows={4}
                    testId="class-drawer-description-input"
                  />
                </div>

                <div>
                  <label className="form-group-label">Domain</label>
                  <Select
                    value={domainId}
                    onChange={(value) => handleSchemeChange(value)}
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
                    <div className="readonly-display">
                      <span className="mono" style={{ flex: 1, fontSize: "var(--text-xs)" }}>
                        {selectedParent.id.slice(0, 8)}
                      </span>
                      <span>{selectedParent.title}</span>
                    </div>
                  ) : (
                    <div className="readonly-display muted">—</div>
                  )}
                </div>

                {isDirty && (
                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        if (classData) {
                          setTitle(classData.title);
                          setDescription(classData.description ?? "");
                          setDomainId(classData.concept_scheme_id);
                          setParentClassId(classData.parent_class_id ?? "");
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
                  { key: "Properties", value: String(propertyCount) },
                  { key: "Relationships", value: String(relationshipCount) },
                  { key: "Individuals", value: String(individualCount) },
                  {
                    key: "Created",
                    value: new Date(classData.created_at ?? "").toLocaleDateString(),
                  },
                ]}
              />
            </InspectorPanel.Section>

            <InspectorPanel.Section title="Suggest Relationships">
              <RelationshipSuggester classId={classData.id} />
            </InspectorPanel.Section>

            <InspectorPanel.Section title="Grounding">
              <GroundingSection classId={classData.id} />
            </InspectorPanel.Section>
          </>
        )}
      </InlineInspector>

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
