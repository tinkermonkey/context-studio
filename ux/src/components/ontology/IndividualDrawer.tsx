import { useState, useEffect, useRef, Fragment } from "react";
import { Drawer } from "@/components/ui/Drawer";
import { Input, Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Panel } from "@/components/ui/Panel";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAutosave } from "@/hooks/useAutosave";
import { useToasts } from "@/components/ui/Toast";
import {
  useUpdateIndividual,
  useAddClassToIndividual,
  useRemoveClassFromIndividual,
  useIndividualInheritedProperties,
} from "@/api/hooks/ontology/useIndividuals";
import { useIndividuals, useClasses } from "@/api/hooks/ontology";
import { ApiError } from "@/api/client/interceptors";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];
type DataPropertyValueResponse = components["schemas"]["DataPropertyValueResponse"];

interface IndividualDrawerProps {
  individualId: string | null;
  onClose: () => void;
  onSelectIndividual?: (id: string) => void;
}

interface ClassChipProps {
  classId: string;
  className: string;
  onRemove: (id: string) => void;
  isDisabled: boolean;
}

function ClassChip({ classId, className, onRemove, isDisabled }: ClassChipProps) {
  return (
    <div
      style={{
        padding: "4px 8px",
        background: "var(--canvas-bg-2)",
        borderRadius: "var(--radius-sm)",
        display: "flex",
        alignItems: "center",
        gap: "var(--space-1)",
        fontSize: "var(--text-sm)",
      }}
    >
      <span>{className}</span>
      <button
        type="button"
        onClick={() => onRemove(classId)}
        disabled={isDisabled}
        style={{
          background: "none",
          border: "none",
          cursor: isDisabled ? "not-allowed" : "pointer",
          padding: 0,
          color: isDisabled ? "var(--canvas-fg-4)" : "var(--canvas-fg-3)",
          fontSize: "var(--text-sm)",
          opacity: isDisabled ? 0.5 : 1,
        }}
        data-testid={`individual-class-remove-${classId}`}
      >
        ✕
      </button>
    </div>
  );
}

export function IndividualDrawer({
  individualId,
  onClose,
  onSelectIndividual,
}: IndividualDrawerProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [showClassOptions, setShowClassOptions] = useState(false);
  const [isAddingClass, setIsAddingClass] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const lastSavedAtRef = useRef<Date | null>(null);
  const { toast } = useToasts();

  const updateMutation = useUpdateIndividual();
  const addClassMutation = useAddClassToIndividual();
  const removeClassMutation = useRemoveClassFromIndividual();

  const { data: individualsResponse } = useIndividuals();
  const individual = individualsResponse?.items.find((i) => i.id === individualId) || null;

  const { data: classesResponse } = useClasses();
  const classes = classesResponse?.items || [];
  const classMap = new Map(classes.map((c: ClassResponse) => [c.id, c.title]));

  const { data: inheritedPropertiesResponse, isLoading: isLoadingProperties } =
    useIndividualInheritedProperties(individualId || "");
  const inheritedProperties = inheritedPropertiesResponse?.items || [];

  const relatedIndividuals =
    individualsResponse?.items
      ?.filter(
        (ind) =>
          ind.id !== individualId &&
          ind.class_ids.some((classId) => individual?.class_ids.includes(classId)),
      )
      .slice(0, 10) || [];

  const isDirty = title !== individual?.title || description !== (individual?.description || "");

  const updateData = { title, description };

  const { status } = useAutosave({
    data: updateData,
    mutationFn: async () => {
      if (!individual || !isDirty) return;
      await updateMutation.mutateAsync({
        id: individual.id,
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

  useEffect(() => {
    if (individual) {
      setTitle(individual.title);
      setDescription(individual.description || "");
      lastSavedAtRef.current = null;
    }
  }, [individual]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowClassOptions(false);
      }
    };

    if (showClassOptions) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [showClassOptions]);

  if (!individualId || !individual) return null;

  const handleAddClass = async (classId: string) => {
    if (!classId) return;
    try {
      setIsAddingClass(true);
      await addClassMutation.mutateAsync({
        individualId: individual.id,
        data: { class_id: classId },
      });
      setSearchQuery("");
      setShowClassOptions(false);
      toast("success", "Class added");
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Failed to add class";
      toast("error", message);
    } finally {
      setIsAddingClass(false);
    }
  };

  const handleRemoveClass = async (classId: string) => {
    const canRemove = individual.class_ids.length > 1;
    if (!canRemove) {
      toast("error", "At least one class must remain");
      return;
    }

    try {
      await removeClassMutation.mutateAsync({
        individualId: individual.id,
        classId,
      });
      toast("success", "Class removed");
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Failed to remove class";
      toast("error", message);
    }
  };

  const revert = () => {
    if (individual) {
      setTitle(individual.title);
      setDescription(individual.description || "");
      setSearchQuery("");
    }
  };

  const availableClasses = classes.filter(
    (cls) =>
      !individual.class_ids.includes(cls.id) &&
      (cls.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        cls.id.toLowerCase().includes(searchQuery.toLowerCase())),
  );

  const autosaveState = status === "idle" ? undefined : (status as "saving" | "saved" | "error");

  return (
    <Drawer
      open={!!individual}
      onClose={onClose}
      title={individual.title}
      autosaveState={autosaveState}
      isDirty={isDirty}
      lastSavedAt={lastSavedAtRef.current || undefined}
      onRevert={revert}
      data-testid="individual-detail-page"
    >
      <div className="stack-lg">
        {/* Header Section */}
        <div>
          <label className="form-group-label">ID</label>
          <Input
            type="text"
            value={individual.id}
            disabled
            mono
            data-testid="individual-drawer-id"
          />
        </div>

        <div>
          <label className="form-group-label">Name</label>
          <Input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            data-testid="individual-drawer-name-input"
          />
        </div>

        <div>
          <label className="form-group-label">Description</label>
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            data-testid="individual-drawer-description-input"
            rows={4}
          />
        </div>

        {/* Class Membership Panel */}
        <Panel title="Class Membership" data-testid="individual-class-list" className="stack-lg">
          {individual.class_ids.length > 0 && (
            <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
              {individual.class_ids.map((classId) => (
                <ClassChip
                  key={classId}
                  classId={classId}
                  className={classMap.get(classId) || "Unknown"}
                  onRemove={handleRemoveClass}
                  isDisabled={individual.class_ids.length === 1}
                />
              ))}
            </div>
          )}

          <div style={{ position: "relative" }} ref={dropdownRef}>
            <Input
              type="text"
              placeholder="Search and add classes..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setShowClassOptions(true);
              }}
              onFocus={() => setShowClassOptions(true)}
              disabled={isAddingClass}
              data-testid="individual-class-typeahead"
            />
            {showClassOptions && availableClasses.length > 0 && (
              <div
                style={{
                  position: "absolute",
                  top: "100%",
                  left: 0,
                  right: 0,
                  background: "var(--canvas-bg)",
                  border: "1px solid var(--canvas-fg-4)",
                  borderRadius: "var(--radius-sm)",
                  marginTop: "4px",
                  zIndex: 10,
                  maxHeight: "200px",
                  overflowY: "auto",
                }}
              >
                {availableClasses.map((cls) => (
                  <button
                    key={cls.id}
                    type="button"
                    onClick={() => handleAddClass(cls.id)}
                    disabled={isAddingClass}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-2)",
                      padding: "var(--space-2) var(--space-3)",
                      width: "100%",
                      background: "none",
                      border: "none",
                      cursor: isAddingClass ? "not-allowed" : "pointer",
                      textAlign: "left",
                      fontSize: "var(--text-sm)",
                      color: "var(--canvas-fg)",
                      borderBottom: "1px solid var(--canvas-fg-4)",
                      opacity: isAddingClass ? 0.5 : 1,
                    }}
                    data-testid={`individual-class-option-${cls.id}`}
                  >
                    <span
                      className="mono"
                      style={{ fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)" }}
                    >
                      {cls.id.slice(0, 8)}
                    </span>
                    <span>{cls.title}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </Panel>

        {/* Inherited Properties Panel */}
        <Panel
          title="Inherited Properties"
          data-testid="individual-properties-panel"
          className="stack-lg"
        >
          {isLoadingProperties ? (
            <div className="stack">
              <Skeleton height={40} />
              <Skeleton height={40} />
              <Skeleton height={40} />
            </div>
          ) : inheritedProperties.length === 0 ? (
            <EmptyState
              title="No properties"
              description="No properties are defined for this individual's classes"
            />
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 100px 1fr 120px",
                gap: "var(--space-2)",
                fontSize: "var(--text-sm)",
              }}
            >
              <div style={{ fontWeight: 500, paddingBottom: "var(--space-2)" }}>Property</div>
              <div style={{ fontWeight: 500, paddingBottom: "var(--space-2)" }}>Type</div>
              <div style={{ fontWeight: 500, paddingBottom: "var(--space-2)" }}>Value</div>
              <div style={{ fontWeight: 500, paddingBottom: "var(--space-2)" }}>Source</div>

              {inheritedProperties.map((prop: DataPropertyValueResponse, idx) => (
                <Fragment key={`${prop.property_identifier}-${idx}`}>
                  <div>
                    <span className="mono" style={{ fontSize: "var(--text-xs)" }}>
                      {prop.property_identifier}
                    </span>
                  </div>
                  <div>
                    <span
                      style={{
                        backgroundColor: "var(--canvas-bg-2)",
                        padding: "2px 6px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: "var(--text-xs)",
                        display: "inline-block",
                      }}
                    >
                      {prop.datatype || "any"}
                    </span>
                  </div>
                  <div>
                    <span style={{ color: "var(--canvas-fg-3)" }}>—</span>
                  </div>
                  <div>
                    <span style={{ color: "var(--canvas-fg-3)", fontSize: "var(--text-xs)" }}>
                      TBD
                    </span>
                  </div>
                </Fragment>
              ))}
            </div>
          )}
        </Panel>

        {/* Related Individuals Panel */}
        <Panel
          title="Related Individuals"
          data-testid="related-individuals-panel"
          className="stack-lg"
        >
          {relatedIndividuals.length === 0 ? (
            <EmptyState
              title="No related individuals"
              description="No other individuals share classes with this one"
            />
          ) : (
            <div className="stack">
              {relatedIndividuals.map((ind) => {
                const sharedClasses = ind.class_ids.filter((id) =>
                  individual.class_ids.includes(id),
                );
                return (
                  <div
                    key={ind.id}
                    style={{
                      padding: "var(--space-2)",
                      background: "var(--canvas-bg-2)",
                      borderRadius: "var(--radius-sm)",
                    }}
                  >
                    <div style={{ fontWeight: 500, marginBottom: "var(--space-1)" }}>
                      <span
                        style={{
                          color: "var(--cyan-600, #0891b2)",
                          cursor: "pointer",
                          textDecoration: "underline",
                        }}
                        onClick={() => onSelectIndividual?.(ind.id)}
                        data-testid={`related-individual-name-${ind.id}`}
                      >
                        {ind.title}
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: "var(--space-1)", flexWrap: "wrap" }}>
                      {sharedClasses.map((classId) => (
                        <span
                          key={classId}
                          style={{
                            backgroundColor: "var(--canvas-bg-3)",
                            color: "var(--canvas-fg)",
                            padding: "2px 6px",
                            borderRadius: "2px",
                            fontSize: "var(--text-xs)",
                          }}
                          data-testid={`related-individual-class-${classId}`}
                        >
                          {classMap.get(classId) || "Unknown"}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
              {relatedIndividuals.length === 10 && (
                <div
                  style={{
                    textAlign: "center",
                    fontSize: "var(--text-sm)",
                    color: "var(--canvas-fg-3)",
                    marginTop: "var(--space-2)",
                  }}
                >
                  Showing 10 of many results
                </div>
              )}
            </div>
          )}
        </Panel>

        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button
            variant="ghost"
            onClick={onClose}
            style={{ flex: 1 }}
            data-testid="individual-drawer-close-button"
          >
            Close
          </Button>
        </div>
      </div>
    </Drawer>
  );
}
