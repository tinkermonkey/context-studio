import { TextInput as Input, TextArea as Textarea, Button } from "@tinkermonkey/heimdall-ui";
import { useState, useRef } from "react";


import { useClasses } from "@/api/hooks/ontology/useClasses";
import { individualsCopy } from "@/routes/app/data/individuals/-copy";
import type { components } from "@/api/types";

type IndividualCreateRequest = components["schemas"]["IndividualCreateRequest"];
type IndividualResponse = components["schemas"]["IndividualResponse"];

interface IndividualEditorSubmitData {
  title: string;
  description?: string | null;
  class_ids: string[];
}

interface IndividualEditorProps {
  individualId?: string;
  initialData?: IndividualCreateRequest | IndividualResponse;
  onSubmit: (data: IndividualEditorSubmitData) => Promise<void>;
  isLoading?: boolean;
}

export function IndividualEditor({
  individualId,
  initialData,
  onSubmit,
  isLoading,
}: IndividualEditorProps) {
  const [title, setTitle] = useState(
    initialData && "title" in initialData ? initialData.title : "",
  );
  const [description, setDescription] = useState(
    initialData && "description" in initialData ? initialData.description || "" : "",
  );
  const [selectedClassIds, setSelectedClassIds] = useState<string[]>(
    initialData && "class_ids" in initialData
      ? Array.isArray(initialData.class_ids)
        ? initialData.class_ids
        : [initialData.class_ids]
      : [],
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [showClassOptions, setShowClassOptions] = useState(false);
  const [titleError, setTitleError] = useState<string>();
  const [classError, setClassError] = useState<string>();
  const searchInputRef = useRef<HTMLInputElement>(null);

  const { data: classesResponse } = useClasses();
  const classes = classesResponse?.items || [];

  const selectedClasses = classes.filter((cls) => selectedClassIds.includes(cls.id));
  const filteredClasses = classes.filter(
    (cls) =>
      !selectedClassIds.includes(cls.id) &&
      (cls.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        cls.id.toLowerCase().includes(searchQuery.toLowerCase())),
  );

  const validateTitle = (value: string): boolean => {
    if (!value.trim()) {
      setTitleError(individualsCopy.form.titleRequired);
      return false;
    }
    setTitleError(undefined);
    return true;
  };

  const handleTitleBlur = () => {
    validateTitle(title);
  };

  const handleAddClass = (classId: string) => {
    if (!individualId) {
      setSelectedClassIds((prev) => [...prev, classId]);
      setSearchQuery("");
      setShowClassOptions(false);
    }
  };

  const handleRemoveClass = (classId: string) => {
    if (!individualId) {
      setSelectedClassIds((prev) => prev.filter((id) => id !== classId));
    }
  };

  const performSubmit = async () => {
    if (!validateTitle(title)) {
      return;
    }

    if (selectedClassIds.length === 0) {
      setClassError(individualsCopy.form.classesRequired);
      return;
    }

    setClassError(undefined);
    await onSubmit({
      title,
      description: description || null,
      class_ids: selectedClassIds,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await performSubmit();
  };

  const handleKeyDown = async (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      await performSubmit();
    }
  };

  return (
    <form onSubmit={handleSubmit} data-testid="individual-form">
      <div className="stack-lg">
        <div>
          <label className="form-group-label">{individualsCopy.form.titleLabel}</label>
          <Input
            type="text"
            placeholder={individualsCopy.form.titlePlaceholder}
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setTitleError(undefined);
            }}
            onBlur={handleTitleBlur}
            onKeyDown={handleKeyDown}
            autoFocus
            data-testid="individual-title-input"
          />
          {titleError && (
            <div style={{ color: "var(--rose-600)", fontSize: "var(--text-xs)", marginTop: "4px" }}>
              {titleError}
            </div>
          )}
        </div>

        <div>
          <label className="form-group-label">{individualsCopy.form.classesLabel}</label>
          {selectedClasses.length > 0 && (
            <div
              style={{
                display: "flex",
                gap: "var(--space-2)",
                flexWrap: "wrap",
                marginBottom: "var(--space-2)",
              }}
            >
              {selectedClasses.map((cls) => (
                <div
                  key={cls.id}
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
                  <span>{cls.title}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveClass(cls.id)}
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: 0,
                      color: "var(--canvas-fg-3)",
                      fontSize: "var(--text-sm)",
                    }}
                    data-testid={`individual-class-remove-${cls.id}`}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
          <div style={{ position: "relative" }}>
            <Input
              ref={searchInputRef}
              type="text"
              placeholder={
                individualId
                  ? individualsCopy.form.classesEditPlaceholder
                  : individualsCopy.form.classesPlaceholder
              }
              value={searchQuery}
              onChange={(e) => {
                if (!individualId) {
                  setSearchQuery(e.target.value);
                  setShowClassOptions(true);
                }
              }}
              onFocus={() => !individualId && setShowClassOptions(true)}
              onKeyDown={handleKeyDown}
              disabled={!!individualId}
              data-testid="individual-class-select"
            />
            {showClassOptions && filteredClasses.length > 0 && (
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
                    onClick={() => handleAddClass(cls.id)}
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
          {classError && (
            <div style={{ color: "var(--rose-600)", fontSize: "var(--text-xs)", marginTop: "4px" }}>
              {classError}
            </div>
          )}
        </div>

        <div>
          <label className="form-group-label">{individualsCopy.form.descriptionLabel}</label>
          <Textarea
            placeholder={individualsCopy.form.descriptionPlaceholder}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onKeyDown={handleKeyDown}
            data-testid="individual-description-input"
            rows={4}
          />
        </div>

        <Button
          type="submit"
          variant="primary"
          disabled={isLoading}
          data-testid="individual-submit-button"
          onKeyDown={handleKeyDown}
        >
          {individualId ? individualsCopy.edit.submitButton : individualsCopy.create.submitButton}
        </Button>
      </div>
    </form>
  );
}
