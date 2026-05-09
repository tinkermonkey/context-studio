import { useState, useEffect, useRef } from "react";
import { Drawer } from "@/components/ui/Drawer";
import { Input, Textarea, Select } from "@/components/ui/Input";
import { useUpdateClass, useDeleteClass } from "@/api/hooks/ontology/useClasses";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useAutosave } from "@/hooks/useAutosave";
import { useToasts } from "@/components/ui/Toast";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { TypeToConfirmDialog } from "@/components/ui/TypeToConfirmDialog";
import { useIndividuals } from "@/api/hooks/ontology/useIndividuals";
import { classesCopy } from "@/routes/app/schema/classes/-copy";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];
type ClassUpdateRequest = components["schemas"]["ClassUpdateRequest"];

interface ClassDrawerProps {
  classData: ClassResponse | null;
  onClose: () => void;
}

export function ClassDrawer({ classData, onClose }: ClassDrawerProps) {
  const [title, setTitle] = useState(classData?.title ?? "");
  const [description, setDescription] = useState(classData?.description ?? "");
  const [domainId, setDomainId] = useState(classData?.concept_scheme_id ?? "");
  const [parentClassId, setParentClassId] = useState(
    classData?.parent_class_id ?? ""
  );
  const [searchParent, setSearchParent] = useState("");
  const [showParentOptions, setShowParentOptions] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const lastSavedAtRef = useRef<Date | null>(null);

  const { toast } = useToasts();
  const updateMutation = useUpdateClass();
  const deleteMutation = useDeleteClass();
  const { data: schemesResponse } = useSchemes();
  const schemes = schemesResponse?.items || [];
  const { data: classesResponse } = useClasses();
  const allClasses = classesResponse?.items || [];
  const { data: individualsResponse } = useIndividuals({
    class_id: classData?.id,
  });

  const { performDelete, undo } = useUndoDelete({
    onDelete: (id: string) => deleteMutation.mutateAsync(id),
    undoWindowMs: 8000,
  });

  useEffect(() => {
    setTitle(classData?.title ?? "");
    setDescription(classData?.description ?? "");
    setDomainId(classData?.concept_scheme_id ?? "");
    setParentClassId(classData?.parent_class_id ?? "");
    lastSavedAtRef.current = null;
  }, [classData]);

  const isDirty =
    title !== classData?.title ||
    description !== classData?.description ||
    domainId !== classData?.concept_scheme_id ||
    parentClassId !== classData?.parent_class_id;

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
    try {
      await performDelete(classData.id);
      toast("success", classesCopy.delete.successToast, "Undo", {
        action: {
          label: "Undo",
          onAction: undo,
        },
        autoDismissMs: 8000,
      });
      onClose();
    } catch {
      toast("error", "Failed to delete class");
    }
  };

  const handleDeleteClick = () => {
    setShowDeleteConfirm(true);
  };

  if (!classData) return null;

  const selectedDomain = schemes.find((s) => s.id === domainId);
  const selectedParent = allClasses.find((c) => c.id === parentClassId);

  const filteredClasses = allClasses
    .filter((cls) => cls.id !== classData.id)
    .filter(
      (cls) =>
        cls.title.toLowerCase().includes(searchParent.toLowerCase()) ||
        cls.id.toLowerCase().includes(searchParent.toLowerCase())
    );

  const autosaveState =
    status === "idle" ? undefined : (status as "saving" | "saved" | "error");

  const propertyCount = classData.data_properties?.length ?? 0;
  const individualCount = individualsResponse?.total ?? 0;

  return (
    <>
      <Drawer
        open={!!classData}
        onClose={onClose}
        title={classData.title}
        autosaveState={autosaveState}
        isDirty={isDirty}
        lastSavedAt={lastSavedAtRef.current || undefined}
        onRevert={revert}
        onDelete={handleDeleteClick}
        data-testid="class-drawer"
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
              ID
            </label>
            <Input
              type="text"
              value={classData.id}
              disabled
              mono
              data-testid="class-drawer-id"
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
              Name
            </label>
            <Input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              data-testid="class-drawer-name-input"
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
              Description
            </label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              data-testid="class-drawer-description-input"
              rows={4}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
              Domain
            </label>
            <Select
              value={domainId}
              onChange={(e) => setDomainId(e.target.value)}
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
            <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
              Parent Class
            </label>
            {selectedParent ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-2)",
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
                <button
                  type="button"
                  onClick={() => {
                    setParentClassId("");
                    setSearchParent("");
                  }}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: 0,
                    color: "var(--canvas-fg-3)",
                  }}
                  data-testid="class-drawer-parent-clear"
                >
                  ✕
                </button>
              </div>
            ) : (
              <div style={{ position: "relative" }}>
                <Input
                  type="text"
                  placeholder="Search for parent class"
                  value={searchParent}
                  onChange={(e) => {
                    setSearchParent(e.target.value);
                    setShowParentOptions(true);
                  }}
                  onFocus={() => setShowParentOptions(true)}
                  data-testid="class-drawer-parent-input"
                />
                {showParentOptions && filteredClasses.length > 0 && (
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
                    {filteredClasses.map((cls) => (
                      <button
                        key={cls.id}
                        type="button"
                        onClick={() => {
                          setParentClassId(cls.id);
                          setSearchParent("");
                          setShowParentOptions(false);
                        }}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "var(--space-2)",
                          padding: "var(--space-2) var(--space-3)",
                          width: "100%",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          textAlign: "left",
                          fontSize: "var(--text-sm)",
                          color: "var(--canvas-fg)",
                          borderBottom: "1px solid var(--canvas-fg-4)",
                        }}
                        data-testid={`class-drawer-parent-option-${cls.id}`}
                      >
                        <span className="mono" style={{ fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)" }}>
                          {cls.id.slice(0, 8)}
                        </span>
                        <span>{cls.title}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--text-xs)" }}>
            <span style={{ color: "var(--canvas-fg-3)" }}>
              Properties: <span style={{ fontWeight: 500 }}>{propertyCount}</span>
            </span>
          </div>

          <div style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--text-xs)" }}>
            <span style={{ color: "var(--canvas-fg-3)" }}>
              Individuals: <span style={{ fontWeight: 500 }}>{individualCount}</span>
            </span>
          </div>

          <div style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--text-xs)" }}>
            <span style={{ color: "var(--canvas-fg-3)" }}>
              Created: {new Date(classData.created_at ?? "").toLocaleDateString()}
            </span>
          </div>
        </div>
      </Drawer>

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
        isLoading={deleteMutation.isPending}
        data-testid="class-delete-confirm"
      />
    </>
  );
}
