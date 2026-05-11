import { useState } from "react";
import { Input, Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import type { components } from "@/api/types";

type IndividualCreateRequest = components["schemas"]["IndividualCreateRequest"];

interface IndividualEditorSubmitData {
  title: string;
  description?: string | null;
  class_ids: string[];
}

interface IndividualEditorProps {
  initialData?: IndividualCreateRequest;
  onSubmit: (data: IndividualEditorSubmitData) => Promise<void>;
  isLoading?: boolean;
}

export function IndividualEditor({ initialData, onSubmit, isLoading }: IndividualEditorProps) {
  const [title, setTitle] = useState(initialData?.title || "");
  const [description, setDescription] = useState(initialData?.description || "");
  const [selectedClassIds, setSelectedClassIds] = useState<string[]>(
    Array.isArray(initialData?.class_ids) ? initialData.class_ids : []
  );
  const [titleError, setTitleError] = useState<string>();
  const [classError, setClassError] = useState<string>();

  const { data: classesResponse } = useClasses();
  const classes = classesResponse?.items || [];

  const validateTitle = (value: string): boolean => {
    if (!value.trim()) {
      setTitleError("Title is required");
      return false;
    }
    setTitleError(undefined);
    return true;
  };

  const handleTitleBlur = () => {
    validateTitle(title);
  };

  const handleClassToggle = (classId: string) => {
    setSelectedClassIds((prev) =>
      prev.includes(classId) ? prev.filter((id) => id !== classId) : [...prev, classId]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateTitle(title)) {
      return;
    }

    if (selectedClassIds.length === 0) {
      setClassError("At least one class must be selected");
      return;
    }

    setClassError(undefined);
    await onSubmit({
      title,
      description: description || null,
      class_ids: selectedClassIds,
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  return (
    <form onSubmit={handleSubmit} data-testid="individual-editor-form">
      <div className="stack-lg">
        <div>
          <label className="form-group-label">Title</label>
          <Input
            type="text"
            placeholder="Individual title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={handleTitleBlur}
            onKeyDown={handleKeyDown}
            autoFocus
            data-testid="individual-editor-title-input"
          />
          {titleError && (
            <div style={{ color: "var(--rose-600)", fontSize: "var(--text-xs)", marginTop: "4px" }}>
              {titleError}
            </div>
          )}
        </div>

        <div>
          <label className="form-group-label">Classes</label>
          <div
            style={{
              border: "1px solid var(--canvas-fg-4)",
              borderRadius: "var(--radius-sm)",
              maxHeight: "200px",
              overflowY: "auto",
            }}
            data-testid="individual-editor-class-list"
          >
            {classes.length === 0 ? (
              <div
                style={{
                  padding: "var(--space-3)",
                  color: "var(--canvas-fg-3)",
                  fontSize: "var(--text-sm)",
                }}
              >
                No classes available
              </div>
            ) : (
              classes.map((cls) => (
                <label
                  key={cls.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    padding: "var(--space-2) var(--space-3)",
                    borderBottom: "1px solid var(--canvas-fg-4)",
                    cursor: "pointer",
                    fontSize: "var(--text-sm)",
                  }}
                  data-testid={`individual-editor-class-${cls.id}`}
                >
                  <input
                    type="checkbox"
                    checked={selectedClassIds.includes(cls.id)}
                    onChange={() => handleClassToggle(cls.id)}
                    style={{ marginRight: "var(--space-2)" }}
                    data-testid={`individual-editor-class-checkbox-${cls.id}`}
                  />
                  <span className="mono" style={{ fontSize: "var(--text-xs)", marginRight: "var(--space-2)" }}>
                    {cls.id.slice(0, 8)}
                  </span>
                  <span>{cls.title}</span>
                </label>
              ))
            )}
          </div>
          {classError && (
            <div style={{ color: "var(--rose-600)", fontSize: "var(--text-xs)", marginTop: "4px" }}>
              {classError}
            </div>
          )}
        </div>

        <div>
          <label className="form-group-label">Description (optional)</label>
          <Textarea
            placeholder="Optional description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onKeyDown={handleKeyDown}
            data-testid="individual-editor-description-input"
            rows={4}
          />
        </div>

        <Button
          type="submit"
          variant="primary"
          disabled={isLoading}
          data-testid="individual-editor-submit-button"
          onKeyDown={handleKeyDown}
        >
          Create Individual
        </Button>
      </div>
    </form>
  );
}
