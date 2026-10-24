import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  InspectorPanel,
  TextInput as Input,
  Select,
  KVGrid,
  Chip,
} from "@tinkermonkey/heimdall-ui";
import { RelationshipSuggester, GroundingSection } from "./suggesters";
import { SuggestField } from "@/components/ontology/suggesters/SuggestField";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { InlineInspector } from "@/components/ui/InlineInspector";
import { EditableField } from "@/components/ui/EditableField";
import { TypeToConfirmDialog } from "@/components/ui/TypeToConfirmDialog";
import {
  useUpdateClass,
  useDeleteClass,
  useMoveClass,
  useCreateClass,
} from "@/api/hooks/ontology/useClasses";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useClass, useClasses, useClassesByIds } from "@/api/hooks/ontology/useClasses";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { useIndividuals } from "@/api/hooks/ontology/useIndividuals";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
import { usePropertiesByIds } from "@/api/hooks/ontology/useProperties";
import { SMALL_SET_LIMIT } from "@/api/config";
import { ApiError } from "@/api/client/interceptors";
import { classesCopy } from "@/routes/app/schema/classes/-copy";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];
/** Subclasses, individuals and relationships each show at most this many entries. */
const CHILDREN_LIMIT = 50;
const SAMPLE_INDIVIDUALS = 5;
const RELATIONSHIPS_SHOWN = 10;

type ExternalReferenceResponse = components["schemas"]["ExternalReferenceResponse"];

interface ClassDrawerProps {
  classData: ClassResponse | null;
}

export function ClassDrawer({ classData }: ClassDrawerProps) {
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [domainId, setDomainId] = useState(classData?.concept_scheme_id ?? "");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [descriptionDraft, setDescriptionDraft] = useState(classData?.description ?? "");

  const navigate = useNavigate();
  const { toast } = useToasts();
  const updateMutation = useUpdateClass();
  const deleteMutation = useDeleteClass();
  const moveMutation = useMoveClass();
  const createMutation = useCreateClass();
  // Schemes are a small set: the domain select needs all of them.
  const { data: schemesResponse } = useSchemes(undefined, { limit: SMALL_SET_LIMIT });
  const schemes = schemesResponse?.items || [];
  const classId = classData?.id ?? "";
  const { data: parentClass } = useClass(classData?.parent_class_id ?? "");
  const { data: childrenResponse } = useClasses(
    { parent_class_id: classId, limit: CHILDREN_LIMIT, sort_by: "title" },
    { enabled: !!classId },
  );
  const {
    data: individualsResponse,
    error: individualsError,
    refetch: refetchIndividuals,
  } = useIndividuals({ class_id: classId, limit: SAMPLE_INDIVIDUALS }, { enabled: !!classId });

  // Relationships touching this class: the newest as source and as target.
  const relationshipPage = { limit: RELATIONSHIPS_SHOWN, sort_order: "desc" as const };
  const {
    data: outgoingResponse,
    error: outgoingError,
    refetch: refetchOutgoing,
  } = useRelationships({ ...relationshipPage, source_id: classId }, { enabled: !!classId });
  const {
    data: incomingResponse,
    error: incomingError,
    refetch: refetchIncoming,
  } = useRelationships({ ...relationshipPage, target_id: classId }, { enabled: !!classId });
  const relationshipsError = outgoingError ?? incomingError;
  const refetchRelationships = () => {
    void refetchOutgoing();
    void refetchIncoming();
  };

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
    setDomainId(classData?.concept_scheme_id ?? "");
    setMode("view");
    setDescriptionDraft(classData?.description ?? "");
  }, [classData]);

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

  const classRelationships = useMemo(
    () =>
      [...(outgoingResponse?.items ?? []), ...(incomingResponse?.items ?? [])]
        .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))
        .slice(0, RELATIONSHIPS_SHOWN),
    [outgoingResponse, incomingResponse],
  );
  const { data: endpointClasses } = useClassesByIds(
    classRelationships.flatMap((rel) => [rel.source_id, rel.target_id]),
  );
  const { data: predicateProperties } = usePropertiesByIds(
    classRelationships.map((rel) => rel.property_definition_id),
  );
  const classMap = useMemo(
    () => new Map((endpointClasses?.items ?? []).map((c) => [c.id, c.title])),
    [endpointClasses],
  );
  const propertyMap = useMemo(
    () => new Map((predicateProperties?.items ?? []).map((p) => [p.id, p.identifier])),
    [predicateProperties],
  );

  if (!classData) return null;

  const handleSaveDescription = async (value: string) => {
    if (value === (classData.description ?? "")) return;
    try {
      await updateMutation.mutateAsync({ id: classData.id, data: { description: value || null } });
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Failed to save description";
      toast("error", message);
      setDescriptionDraft(classData.description ?? "");
    }
  };

  const handleDuplicate = async () => {
    try {
      await createMutation.mutateAsync({
        schemeId: classData.concept_scheme_id,
        data: {
          title: `Copy of ${classData.title}`,
          description: classData.description ?? undefined,
        },
      });
      toast("success", "Class duplicated");
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Failed to duplicate class";
      toast("error", message);
    }
  };

  const selectedScheme = schemes.find((s) => s.id === domainId);
  const selectedParent = classData.parent_class_id ? parentClass : undefined;
  const propertyCount = classData.data_properties?.length ?? 0;
  const individualCount = individualsResponse?.total ?? 0;
  const relationshipCount = (outgoingResponse?.total ?? 0) + (incomingResponse?.total ?? 0);
  const childClasses = childrenResponse?.items ?? [];
  const sampleIndividuals = individualsResponse?.items ?? [];
  const externalRefs: ExternalReferenceResponse[] = classData.external_references ?? [];

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
        onDuplicate={() => {
          void handleDuplicate();
        }}
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
            <InspectorPanel.Section title="Children">
              {childClasses.length === 0 ? (
                <p className="drawer-empty-note" data-testid="class-children-empty">
                  No subclasses
                </p>
              ) : (
                <div className="drawer-pill-row" data-testid="class-children-list">
                  {childClasses.map((c) => (
                    <Chip key={c.id} variant="neutral" data-testid={`class-child-${c.id}`}>
                      {c.title}
                    </Chip>
                  ))}
                </div>
              )}
            </InspectorPanel.Section>
            <InspectorPanel.Section title="Individuals">
              {sampleIndividuals.length === 0 ? (
                <p className="drawer-empty-note" data-testid="class-individuals-empty">
                  No individuals
                </p>
              ) : (
                <div className="stack" data-testid="class-individuals-list">
                  {sampleIndividuals.map((ind) => (
                    <div
                      key={ind.id}
                      className="drawer-list-item"
                      data-testid={`class-individual-${ind.id}`}
                    >
                      {ind.title}
                    </div>
                  ))}
                  {individualCount > SAMPLE_INDIVIDUALS && (
                    <button
                      type="button"
                      className="drawer-show-all-link"
                      onClick={() => navigate({ to: "/app/data/individuals" })}
                      data-testid="class-individuals-show-all"
                    >
                      Show all {individualCount} individuals
                    </button>
                  )}
                </div>
              )}
            </InspectorPanel.Section>
            <InspectorPanel.Section title="Relationships">
              {classRelationships.length === 0 ? (
                <p className="drawer-empty-note" data-testid="class-relationships-empty">
                  No relationships
                </p>
              ) : (
                <div className="stack" data-testid="class-relationships-list">
                  {classRelationships.map((rel) => (
                    <div
                      key={rel.id}
                      className="drawer-triple"
                      data-testid={`class-relationship-${rel.id}`}
                    >
                      <span className="drawer-triple-node">
                        {classMap.get(rel.source_id) ?? "—"}
                      </span>
                      <span className="drawer-triple-predicate">
                        {propertyMap.get(rel.property_definition_id) ?? "—"}
                      </span>
                      <span className="drawer-triple-node">
                        {classMap.get(rel.target_id) ?? "—"}
                      </span>
                    </div>
                  ))}
                  {relationshipCount > classRelationships.length && (
                    <p className="drawer-empty-note">
                      +{relationshipCount - classRelationships.length} more
                    </p>
                  )}
                </div>
              )}
            </InspectorPanel.Section>
            {externalRefs.length > 0 && (
              <InspectorPanel.Section title="Grounding">
                <GroundingSection classId={classData.id} externalRefs={externalRefs} readOnly />
              </InspectorPanel.Section>
            )}
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

                <EditableField
                  label="Name"
                  value={classData.title}
                  onSave={async (v) => {
                    await updateMutation.mutateAsync({ id: classData.id, data: { title: v } });
                  }}
                  validate={(v) => (!v.trim() ? "Name is required" : undefined)}
                  data-testid="class-drawer-name-field"
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
                    entityId={classData.id}
                    value={descriptionDraft}
                    onChange={setDescriptionDraft}
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
              <GroundingSection
                classId={classData.id}
                externalRefs={externalRefs}
                onRemoveRef={() => {
                  toast("error", "Removing grounding references is not yet supported by the API.");
                }}
              />
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
