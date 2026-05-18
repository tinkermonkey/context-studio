import { useState } from "react";
import { Input, Textarea, Field } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import type { components } from "@/api/types";

type ConceptSchemeCreateRequest = components["schemas"]["ConceptSchemeCreateRequest"];

interface SchemeFormProps {
  onSubmit: (data: ConceptSchemeCreateRequest) => Promise<void>;
  isLoading?: boolean;
}

export function SchemeForm({ onSubmit, isLoading }: SchemeFormProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [titleError, setTitleError] = useState<string>();

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

    if (!validateTitle(title)) {
      return;
    }

    await onSubmit({
      title,
      description: description || null,
    });
  };

  return (
    <form onSubmit={handleSubmit} data-testid="scheme-form">
      <div className="stack-lg">
        <Field
          label="Title"
          required
          error={titleError}
        >
          <Input
            type="text"
            placeholder="Scheme name"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setTitleError(undefined);
            }}
            onBlur={handleTitleBlur}
            data-testid="scheme-title-input"
          />
        </Field>

        <Field label="Description (optional)">
          <Textarea
            placeholder="Optional description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            data-testid="scheme-description-input"
            rows={4}
          />
        </Field>

        <Button
          type="submit"
          variant="primary"
          disabled={isLoading}
          data-testid="scheme-submit-button"
        >
          Create Scheme
        </Button>
      </div>
    </form>
  );
}
