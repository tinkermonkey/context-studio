import { useState } from "react";
import { Input, Textarea, Field } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import type { components } from "@/api/types";

type PropertyDefinitionCreateRequest = components["schemas"]["PropertyDefinitionCreateRequest"];
type PropertyDefinitionUpdateRequest = components["schemas"]["PropertyDefinitionUpdateRequest"];
type PropertyDefinitionResponse = components["schemas"]["PropertyDefinitionResponse"];

interface PropertyDefinitionFormProps {
  initialData?: PropertyDefinitionResponse;
  onSubmit: (
    data: PropertyDefinitionCreateRequest | PropertyDefinitionUpdateRequest,
  ) => Promise<void>;
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
  const [formError, setFormError] = useState<string>();

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

    try {
      setFormError(undefined);
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
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "Failed to save property"
      );
    }
  };

  return (
    <form onSubmit={handleSubmit} data-testid="property-definition-form">
      <div className="stack-lg">
        {formError && (
          <div
            className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm"
            role="alert"
            data-testid="property-definition-form-error"
          >
            {formError}
          </div>
        )}
        <Field label="Identifier (snake_case)" required error={identifierError}>
          <Input
            type="text"
            placeholder="property_identifier"
            value={identifier}
            onChange={(e) => {
              setIdentifier(e.target.value);
              setIdentifierError(undefined);
            }}
            onBlur={handleIdentifierBlur}
            disabled={!!initialData}
            mono
            data-testid="property-definition-identifier-input"
          />
        </Field>

        <Field label="Title" required error={titleError}>
          <Input
            type="text"
            placeholder="Display name"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setTitleError(undefined);
            }}
            onBlur={handleTitleBlur}
            data-testid="property-definition-title-input"
          />
        </Field>

        <Field label="Description (optional)">
          <Textarea
            placeholder="Optional description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            data-testid="property-definition-description-input"
            rows={4}
          />
        </Field>

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
