import { useState, useRef, useEffect } from "react";
import { Input, Textarea, Select } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useIndividual } from "@/api/hooks/ontology/useIndividuals";
import type { components } from "@/api/types";

type IndividualCreateRequest = components["schemas"]["IndividualCreateRequest"];
type IndividualResponse = components["schemas"]["IndividualResponse"];
type ClassResponse = components["schemas"]["ClassResponse"];
type DataPropertyValueResponse = components["schemas"]["DataPropertyValueResponse"];

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
  const [title, setTitle] = useState(initialData && "title" in initialData ? initialData.title : "");
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
  const { data: existingIndividual } = useIndividual(individualId || "");
  const classes = classesResponse?.items || [];

  useEffect(() => {
    if (existingIndividual) {
      setTitle(existingIndividual.title);
      setDescription(existingIndividual.description || "");
      setSelectedClassIds(existingIndividual.class_ids);
    }
  }, [existingIndividual]);

  const selectedClasses = classes.filter((cls) => selectedClassIds.includes(cls.id));
  const filteredClasses = classes.filter(
    (cls) =>
      !selectedClassIds.includes(cls.id) &&
      (cls.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        cls.id.toLowerCase().includes(searchQuery.toLowerCase())),
  );

  const allPropertiesToDisplay = selectedClasses.flatMap(
    (cls) => cls.data_properties || [],
  );
  const uniqueProperties = Array.from(
    new Map(
      allPropertiesToDisplay.map((prop) => [prop.property_identifier, prop]),
    ).values(),
  );

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

  const handleAddClass = (classId: string) => {
    setSelectedClassIds((prev) => [...prev, classId]);
    setSearchQuery("");
    setShowClassOptions(false);
  };

  const handleRemoveClass = (classId: string) => {
    setSelectedClassIds((prev) => prev.filter((id) => id !== classId));
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
    <form onSubmit={handleSubmit} data-testid="individual-form">
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
            data-testid="individual-title-input"
          />
          {titleError && (
            <div style={{ color: "var(--rose-600)", fontSize: "var(--text-xs)", marginTop: "4px" }}>
              {titleError}
            </div>
          )}
        </div>

        <div>
          <label className="form-group-label">Classes</label>
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
              placeholder="Search and add classes..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setShowClassOptions(true);
              }}
              onFocus={() => setShowClassOptions(true)}
              onKeyDown={handleKeyDown}
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
          <label className="form-group-label">Description (optional)</label>
          <Textarea
            placeholder="Optional description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onKeyDown={handleKeyDown}
            data-testid="individual-description-input"
            rows={4}
          />
        </div>

        {individualId && uniqueProperties.length > 0 && (
          <div>
            <label className="form-group-label">Properties</label>
            <div className="stack">
              {uniqueProperties.map((prop) => (
                <div key={prop.property_identifier}>
                  <label className="form-group-label" style={{ fontSize: "var(--text-sm)" }}>
                    {prop.property_identifier}
                  </label>
                  <Input
                    type="text"
                    placeholder={`Enter ${prop.property_identifier}`}
                    defaultValue={prop.value ? String(prop.value) : ""}
                    data-testid={`individual-property-${prop.property_identifier}`}
                    disabled
                  />
                  <div
                    style={{
                      fontSize: "var(--text-xs)",
                      color: "var(--canvas-fg-3)",
                      marginTop: "2px",
                    }}
                  >
                    Type: {prop.datatype || "unknown"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {individualId && uniqueProperties.length === 0 && selectedClasses.length > 0 && (
          <div
            style={{
              padding: "var(--space-3)",
              background: "var(--canvas-bg-2)",
              borderRadius: "var(--radius-sm)",
              fontSize: "var(--text-sm)",
              color: "var(--canvas-fg-3)",
            }}
          >
            No properties defined for selected classes
          </div>
        )}

        <Button
          type="submit"
          variant="primary"
          disabled={isLoading}
          data-testid="individual-submit-button"
          onKeyDown={handleKeyDown}
        >
          {individualId ? "Update Individual" : "Create Individual"}
        </Button>
      </div>
    </form>
  );
}
