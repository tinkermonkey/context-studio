import { useState } from "react";
import { Input, Textarea } from "@/components/ui/Input";
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
    <form onSubmit={handleSubmit} data-testid="taxonomy-form">
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div>
          <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
            Title
          </label>
          <Input
            type="text"
            placeholder="Taxonomy name"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={handleTitleBlur}
            data-testid="taxonomy-title-input"
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
            data-testid="taxonomy-description-input"
            rows={4}
          />
        </div>

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
