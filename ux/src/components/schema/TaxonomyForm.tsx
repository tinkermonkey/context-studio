import { useState } from "react";
import { Input, Textarea, Field } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import type { components } from "@/api/types";

type TaxonomyCreateRequest = components["schemas"]["TaxonomyCreateRequest"];

interface TaxonomyFormProps {
  onSubmit: (data: TaxonomyCreateRequest) => Promise<void>;
  isLoading?: boolean;
}

export function TaxonomyForm({ onSubmit, isLoading }: TaxonomyFormProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [titleError, setTitleError] = useState<string>();
  const [formError, setFormError] = useState<string>();

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(undefined);

    if (!validateTitle(title)) {
      return;
    }

    try {
      await onSubmit({
        title,
        description: description || null,
      });
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "Failed to create taxonomy"
      );
    }
  };

  return (
    <form onSubmit={handleSubmit} data-testid="taxonomy-form">
      <div className="stack-lg">
        {formError && (
          <div className="error-banner" role="alert" data-testid="taxonomy-form-error">
            {formError}
          </div>
        )}
        <Field label="Title" required error={titleError}>
          <Input
            type="text"
            placeholder="Taxonomy name"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setTitleError(undefined);
            }}
            onBlur={handleTitleBlur}
            data-testid="taxonomy-title-input"
          />
        </Field>

        <Field label="Description (optional)">
          <Textarea
            placeholder="Optional description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            data-testid="taxonomy-description-input"
            rows={4}
          />
        </Field>

        <Button
          type="submit"
          variant="primary"
          disabled={isLoading}
          data-testid="taxonomy-submit-button"
        >
          Create Taxonomy
        </Button>
      </div>
    </form>
  );
}
