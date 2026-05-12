import { useState, useRef, useEffect } from "react";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { useReferenceStatus, useClasses } from "@/api/hooks";
import type { GroundingWorkflowCreate } from "@/api/services/reference";

interface GroundingWorkflowFormProps {
  onSubmit: (data: GroundingWorkflowCreate) => Promise<void>;
  isLoading?: boolean;
}

export function GroundingWorkflowForm({
  onSubmit,
  isLoading,
}: GroundingWorkflowFormProps) {
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("");
  const [selectedClassIds, setSelectedClassIds] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [showClassOptions, setShowClassOptions] = useState(false);
  const [titleError, setTitleError] = useState<string>();
  const [sourceError, setSourceError] = useState<string>();
  const [scopeError, setScopeError] = useState<string>();
  const searchInputRef = useRef<HTMLInputElement>(null);
  const dropdownContainerRef = useRef<HTMLDivElement>(null);

  const { data: statusResponse } = useReferenceStatus();
  const sources = statusResponse?.sources || [];

  const { data: classesResponse } = useClasses();
  const allClasses = classesResponse?.items || [];

  const selectedClasses = allClasses.filter((cls) => selectedClassIds.includes(cls.id));
  const filteredClasses = allClasses.filter(
    (cls) =>
      !selectedClassIds.includes(cls.id) &&
      cls.title.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  useEffect(() => {
    if (showClassOptions) {
      searchInputRef.current?.focus();
    }
  }, [showClassOptions]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownContainerRef.current &&
        !dropdownContainerRef.current.contains(event.target as Node)
      ) {
        setShowClassOptions(false);
      }
    };

    if (showClassOptions) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
      };
    }
  }, [showClassOptions]);

  const validateTitle = (value: string): boolean => {
    if (!value.trim()) {
      setTitleError("Title is required");
      return false;
    }
    setTitleError(undefined);
    return true;
  };

  const validateSource = (value: string): boolean => {
    if (!value) {
      setSourceError("Source is required");
      return false;
    }
    setSourceError(undefined);
    return true;
  };

  const validateScope = (ids: string[]): boolean => {
    if (ids.length === 0) {
      setScopeError("At least one class scope is required");
      return false;
    }
    setScopeError(undefined);
    return true;
  };

  const handleAddClass = (classId: string) => {
    setSelectedClassIds((prev) => [...prev, classId]);
    setSearchQuery("");
    setShowClassOptions(false);
    setScopeError(undefined);
  };

  const handleRemoveClass = (classId: string) => {
    setSelectedClassIds((prev) => prev.filter((id) => id !== classId));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateTitle(title)) {
      return;
    }

    if (!validateSource(source)) {
      return;
    }

    if (!validateScope(selectedClassIds)) {
      return;
    }

    await onSubmit({
      title,
      source,
      class_scope: selectedClassIds,
    });
  };

  return (
    <form onSubmit={handleSubmit} data-testid="grounding-workflow-form">
      <div className="stack-lg">
        <div>
          <label className="form-group-label">Workflow Name</label>
          <Input
            type="text"
            placeholder="Enter workflow name"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setTitleError(undefined);
            }}
            onBlur={() => validateTitle(title)}
            autoFocus
            data-testid="workflow-title-input"
          />
          {titleError && (
            <div style={{ color: "var(--rose-600)", fontSize: "var(--text-xs)", marginTop: "4px" }}>
              {titleError}
            </div>
          )}
        </div>

        <div>
          <label className="form-group-label">Reference Source</label>
          <select
            value={source}
            onChange={(e) => {
              setSource(e.target.value);
              setSourceError(undefined);
            }}
            onBlur={() => validateSource(source)}
            style={{
              width: "100%",
              padding: "var(--space-2) var(--space-3)",
              border: "1px solid var(--canvas-fg-4)",
              borderRadius: "var(--radius-sm)",
              backgroundColor: "var(--canvas-bg)",
              color: "var(--canvas-fg)",
              fontSize: "inherit",
            }}
            data-testid="workflow-source-select"
          >
            <option value="">Select a source...</option>
            {sources.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name}
              </option>
            ))}
          </select>
          {sourceError && (
            <div style={{ color: "var(--rose-600)", fontSize: "var(--text-xs)", marginTop: "4px" }}>
              {sourceError}
            </div>
          )}
        </div>

        <div>
          <label className="form-group-label">Class Scope</label>
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
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-1)",
                  }}
                  data-testid={`workflow-class-chip-${cls.id}`}
                >
                  <Chip color="violet">{cls.title}</Chip>
                  <button
                    type="button"
                    onClick={() => {
                      handleRemoveClass(cls.id);
                      setScopeError(undefined);
                    }}
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: 0,
                      color: "var(--canvas-fg-3)",
                      fontSize: "var(--text-sm)",
                    }}
                    data-testid={`workflow-class-remove-${cls.id}`}
                    aria-label={`Remove ${cls.title}`}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}

          <div style={{ position: "relative" }} ref={dropdownContainerRef}>
            <Input
              ref={searchInputRef}
              type="text"
              placeholder="Search classes..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setShowClassOptions(true);
              }}
              onFocus={() => setShowClassOptions(true)}
              data-testid="workflow-scope-input"
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
                      borderBottom: "1px solid var(--canvas-fg-4)",
                    }}
                    data-testid={`workflow-scope-option-${cls.id}`}
                  >
                    <span className="mono" style={{ fontSize: "var(--text-xs)" }}>
                      {cls.id.slice(0, 8)}
                    </span>
                    <span>{cls.title}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {scopeError && (
            <div style={{ color: "var(--rose-600)", fontSize: "var(--text-xs)", marginTop: "4px" }}>
              {scopeError}
            </div>
          )}
        </div>

        <Button
          type="submit"
          variant="primary"
          disabled={isLoading}
          data-testid="workflow-submit-button"
        >
          Create Workflow
        </Button>
      </div>
    </form>
  );
}
