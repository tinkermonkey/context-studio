import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input, Field } from "@/components/ui/Input";
import type { components } from "@/api/types";

type PipelineFlavorCreateRequest = components["schemas"]["PipelineFlavorCreateRequest"];

interface FlavorFormProps {
  onSubmit: (data: PipelineFlavorCreateRequest) => Promise<void>;
  onCancel?: () => void;
  isLoading?: boolean;
}

export function FlavorForm({ onSubmit, onCancel, isLoading = false }: FlavorFormProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [nameError, setNameError] = useState<string>();
  const [descriptionError, setDescriptionError] = useState<string>();
  const [formError, setFormError] = useState<string>();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setNameError(undefined);
    setDescriptionError(undefined);
    setFormError(undefined);

    if (!name.trim()) {
      setNameError("Name is required");
      return;
    }

    if (!description.trim()) {
      setDescriptionError("Description is required");
      return;
    }

    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim(),
        steps: [],
      });
      setName("");
      setDescription("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save flavor";
      setFormError(message);
    }
  };

  return (
    <form onSubmit={handleSubmit} data-testid="flavor-form" className="stack">
      {formError && (
        <div className="error-banner" data-testid="flavor-form-error" role="alert">
          {formError}
        </div>
      )}
      <Field label="Name" required error={nameError}>
        <Input
          type="text"
          placeholder="Flavor name"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setNameError(undefined);
          }}
          disabled={isLoading}
          data-testid="flavor-name-input"
        />
      </Field>

      <Field label="Description" required error={descriptionError}>
        <Input
          type="text"
          placeholder="Description"
          value={description}
          onChange={(e) => {
            setDescription(e.target.value);
            setDescriptionError(undefined);
          }}
          disabled={isLoading}
          data-testid="flavor-description-input"
        />
      </Field>

      <div style={{ display: "flex", gap: "8px" }}>
        <Button
          variant="primary"
          type="submit"
          disabled={isLoading}
          data-testid="flavor-submit-button"
        >
          {isLoading ? "Saving..." : "Create Flavor"}
        </Button>
        {onCancel && (
          <Button variant="ghost" type="button" onClick={onCancel} disabled={isLoading}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}
