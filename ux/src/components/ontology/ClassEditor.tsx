import {
  TextInput as Input,
  TextArea as Textarea,
  Select,
  Button,
} from "@tinkermonkey/heimdall-ui";
import { useState, useRef } from "react";

import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];

interface ClassEditorSubmitData {
  title: string;
  description?: string | null;
  parent_class_id?: string | null;
}

interface ClassEditorProps {
  schemeId?: string;
  initialData?: ClassResponse;
  onSubmit: (data: ClassEditorSubmitData, schemeId?: string) => Promise<void>;
  isLoading?: boolean;
}

const snakeCasePattern = /^[a-z][a-z0-9_]*$/;

export function ClassEditor({ schemeId, initialData, onSubmit, isLoading }: ClassEditorProps) {
  const [name, setName] = useState(initialData?.title || "");
  const [description, setDescription] = useState(initialData?.description || "");
  const [domain, setDomain] = useState(initialData?.concept_scheme_id || schemeId || "");
  const [parentClassId, setParentClassId] = useState(initialData?.parent_class_id || "");
  const [nameError, setNameError] = useState<string>();
  const [searchParent, setSearchParent] = useState("");
  const [showParentOptions, setShowParentOptions] = useState(false);
  const parentInputRef = useRef<HTMLInputElement>(null);

  const { data: schemesResponse } = useSchemes();
  const schemes = schemesResponse?.items || [];

  const { data: classesResponse } = useClasses();
  const allClasses = classesResponse?.items || [];

  const filteredClasses = allClasses
    .filter((cls) => cls.id !== initialData?.id)
    .filter(
      (cls) =>
        cls.title.toLowerCase().includes(searchParent.toLowerCase()) ||
        cls.id.toLowerCase().includes(searchParent.toLowerCase()),
    );

  const selectedParent = parentClassId ? allClasses.find((c) => c.id === parentClassId) : null;

  const validateName = (value: string): boolean => {
    if (!value.trim()) {
      setNameError("Name is required");
      return false;
    }
    if (!snakeCasePattern.test(value)) {
      setNameError(
        "Name must start with lowercase letter and contain only lowercase letters, numbers, and underscores",
      );
      return false;
    }
    setNameError(undefined);
    return true;
  };

  const handleNameBlur = () => {
    validateName(name);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateName(name)) {
      return;
    }

    await onSubmit(
      {
        title: name,
        description: description || null,
        parent_class_id: parentClassId || null,
      },
      domain,
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  return (
    <form onSubmit={handleSubmit} data-testid="class-editor-form">
      <div className="stack-lg">
        <div>
          <label className="form-group-label">Name</label>
          <Input
            type="text"
            placeholder="class_name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={handleNameBlur}
            onKeyDown={handleKeyDown}
            mono
            autoFocus
            data-testid="class-editor-name-input"
          />
          {nameError && <div className="field-error">{nameError}</div>}
        </div>

        {!initialData && (
          <div>
            <label className="form-group-label">Domain</label>
            <Select
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              data-testid="class-editor-domain-select"
              required
            >
              <option value="">Select a domain</option>
              {schemes.map((scheme) => (
                <option key={scheme.id} value={scheme.id}>
                  {scheme.title}
                </option>
              ))}
            </Select>
          </div>
        )}

        <div>
          <label className="form-group-label">Parent Class (optional)</label>
          <div className="entity-picker">
            {selectedParent ? (
              <div className="entity-picked">
                <span className="mono" style={{ flex: 1, fontSize: "var(--text-xs)" }}>
                  {selectedParent.id.slice(0, 8)}
                </span>
                <span>{selectedParent.title}</span>
                <button
                  type="button"
                  className="entity-clear"
                  onClick={() => {
                    setParentClassId("");
                    setSearchParent("");
                  }}
                  data-testid="class-editor-parent-clear"
                >
                  ✕
                </button>
              </div>
            ) : (
              <>
                <Input
                  ref={parentInputRef}
                  type="text"
                  placeholder="Search for parent class"
                  value={searchParent}
                  onChange={(e) => {
                    setSearchParent(e.target.value);
                    setShowParentOptions(true);
                  }}
                  onFocus={() => setShowParentOptions(true)}
                  data-testid="class-editor-parent-input"
                />
                {showParentOptions && filteredClasses.length > 0 && (
                  <div className="entity-results">
                    {filteredClasses.map((cls) => (
                      <button
                        key={cls.id}
                        type="button"
                        className="entity-result"
                        onClick={() => {
                          setParentClassId(cls.id);
                          setSearchParent("");
                          setShowParentOptions(false);
                        }}
                        data-testid={`class-editor-parent-option-${cls.id}`}
                      >
                        <span className="mono" style={{ fontSize: "var(--text-xs)" }}>
                          {cls.id.slice(0, 8)}
                        </span>
                        <span>{cls.title}</span>
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        <div>
          <label className="form-group-label">Description (optional)</label>
          <Textarea
            placeholder="Optional description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onKeyDown={handleKeyDown}
            data-testid="class-editor-description-input"
            rows={4}
          />
        </div>

        <Button
          type="submit"
          variant="primary"
          disabled={isLoading}
          data-testid="class-editor-submit-button"
          onKeyDown={handleKeyDown}
        >
          {initialData ? "Update Class" : "Create Class"}
        </Button>
      </div>
    </form>
  );
}
