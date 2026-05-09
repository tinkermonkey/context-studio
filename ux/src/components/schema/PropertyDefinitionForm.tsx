import { useState } from "react";
import { Input, Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import type { components } from "@/api/types";

type PropertyDefinitionCreateRequest = components["schemas"]["PropertyDefinitionCreateRequest"];
type PropertyDefinitionUpdateRequest = components["schemas"]["PropertyDefinitionUpdateRequest"];
type PropertyDefinitionResponse = components["schemas"]["PropertyDefinitionResponse"];

interface PropertyDefinitionFormProps {
  initialData?: PropertyDefinitionResponse;
  onSubmit: (data: PropertyDefinitionCreateRequest | PropertyDefinitionUpdateRequest) => Promise<void>;
  isLoading?: boolean;
}

const snakeCasePattern = /^[a-z0-9_]+$/;

export function PropertyDefinitionForm({
  initialData,
  onSubmit,
  isLoading,
}: PropertyDefinitionFormProps) {
  const [identifier, setIdentifier] = useState(initialData?.identifier || "");
  const [title, setTitle] = useState(initialData?.title || "");
  const [description, setDescription] = useState(initialData?.description || "");
  const [identifierError, setIdentifierError] = useState<string>();
  const [titleError, setTitleError] = useState<string>();

  const validateIdentifier = (value: string): boolean => {
    if (!value) {
      setIdentifierError("Identifier is required");
      return false;
    }
    if (!snakeCasePattern.test(value)) {
      setIdentifierError("Identifier must be lowercase with underscores only");
      return false;
    }
    setIdentifierError(undefined);
    return true;
  };

  const validateTitle = (value: string): boolean => {
    if (!value.trim()) {
      setTitleError("Title is required");
      return false;
    }
    setTitleError(undefined);
    return true;
  };

  const handleIdentifierBlur = () => {
    validateIdentifier(identifier);
  };

  const handleTitleBlur = () => {
    validateTitle(title);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateIdentifier(identifier) || !validateTitle(title)) {
      return;
    }

    if (initialData) {
      await onSubmit({
        title,
        description: description || null,
      } as PropertyDefinitionUpdateRequest);
    } else {
      await onSubmit({
        identifier,
        title,
        description: description || null,
      } as PropertyDefinitionCreateRequest);
    }
  };

  return (
    <form onSubmit={handleSubmit} data-testid="property-definition-form">
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div>
          <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
            Identifier (snake_case)
          </label>
          <Input
            type="text"
            placeholder="property_identifier"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            onBlur={handleIdentifierBlur}
            disabled={!!initialData}
            mono
            data-testid="property-definition-identifier-input"
          />
          {identifierError && (
            <div style={{ color: "var(--rose-600)", fontSize: "var(--text-xs)", marginTop: "4px" }}>
              {identifierError}
            </div>
          )}
        </div>

        <div>
          <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
            Title
          </label>
          <Input
            type="text"
            placeholder="Display name"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={handleTitleBlur}
            data-testid="property-definition-title-input"
          />
          {titleError && (
            <div style={{ color: "var(--rose-600)", fontSize: "var(--text-xs)", marginTop: "4px" }}>
              {titleError}
            </div>
          )}
        </div>

        <div>
          <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
            Description (optional)
          </label>
          <Textarea
            placeholder="Optional description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            data-testid="property-definition-description-input"
            rows={4}
          />
        </div>

        <Button
          type="submit"
          variant="primary"
          disabled={isLoading}
          data-testid="property-definition-submit-button"
        >
          {initialData ? "Update Property" : "Create Property"}
        </Button>
      </div>
    </form>
  );
}
