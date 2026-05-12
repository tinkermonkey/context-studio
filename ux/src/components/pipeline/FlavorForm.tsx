import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
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
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim() || !description.trim()) {
      setError("Name and description are required");
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
      setError(err instanceof Error ? err.message : "Failed to save flavor");
    }
  };

  return (
    <form onSubmit={handleSubmit} data-testid="flavor-form" className="stack">
      {error && <div className="error-banner">{error}</div>}

      <Input
        type="text"
        placeholder="Flavor name"
        value={name}
        onChange={(e) => {
          setName(e.target.value);
          if (error) setError(null);
        }}
        disabled={isLoading}
        data-testid="flavor-name-input"
      />

      <Input
        type="text"
        placeholder="Description"
        value={description}
        onChange={(e) => {
          setDescription(e.target.value);
          if (error) setError(null);
        }}
        disabled={isLoading}
        data-testid="flavor-description-input"
      />

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
