import { useState } from "react";
import { Input, Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

interface FlavorFormProps {
  onSubmit: (data: {
    name: string;
    description?: string;
    steps: Array<Record<string, unknown>>;
  }) => Promise<void>;
  isLoading?: boolean;
  initialData?: {
    name: string;
    description?: string;
    steps: Array<Record<string, unknown>>;
  };
}

export function FlavorForm({ onSubmit, isLoading, initialData }: FlavorFormProps) {
  const [name, setName] = useState(initialData?.name ?? "");
  const [description, setDescription] = useState(initialData?.description ?? "");
  const [stepsJson, setStepsJson] = useState(JSON.stringify(initialData?.steps ?? [], null, 2));
  const [nameError, setNameError] = useState<string>();
  const [stepsError, setStepsError] = useState<string>();

  const validateName = (value: string): boolean => {
    if (!value.trim()) {
      setNameError("Name is required");
      return false;
    }
    setNameError(undefined);
    return true;
  };

  const validateSteps = (value: string): boolean => {
    try {
      const parsed = JSON.parse(value);
      if (!Array.isArray(parsed)) {
        setStepsError("Steps must be a JSON array");
        return false;
      }
      setStepsError(undefined);
      return true;
    } catch (e) {
      setStepsError("Invalid JSON format");
      return false;
    }
  };

  const handleNameBlur = () => {
    validateName(name);
  };

  const handleStepsChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setStepsJson(value);
    if (value.trim()) {
      validateSteps(value);
    } else {
      setStepsError(undefined);
    }
  };

  const handleStepsBlur = () => {
    if (stepsJson.trim()) {
      validateSteps(stepsJson);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateName(name)) {
      return;
    }

    if (!validateSteps(stepsJson)) {
      return;
    }

    const steps = JSON.parse(stepsJson);

    await onSubmit({
      name,
      description: description || undefined,
      steps,
    });
  };

  return (
    <form onSubmit={handleSubmit} data-testid="flavor-form">
      <div className="stack-lg">
        <div>
          <label htmlFor="flavor-name-field" className="form-group-label">Name</label>
          <Input
            id="flavor-name-field"
            type="text"
            placeholder="Flavor name"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              setNameError(undefined);
            }}
            onBlur={handleNameBlur}
            data-testid="flavor-name-input"
          />
          {nameError && <div className="field-error">{nameError}</div>}
        </div>

        <div>
          <label htmlFor="flavor-description-field" className="form-group-label">Description (optional)</label>
          <Textarea
            id="flavor-description-field"
            placeholder="Optional description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            data-testid="flavor-description-input"
            rows={3}
          />
        </div>

        <div>
          <label htmlFor="flavor-steps-field" className="form-group-label">Steps (JSON)</label>
          <Textarea
            id="flavor-steps-field"
            placeholder='[{"name": "step1", "config": {}}]'
            value={stepsJson}
            onChange={handleStepsChange}
            onBlur={handleStepsBlur}
            data-testid="flavor-steps-input"
            rows={6}
            mono
          />
          {stepsError && <div className="field-error">{stepsError}</div>}
        </div>

        <Button
          type="submit"
          variant="primary"
          disabled={isLoading}
          data-testid="flavor-submit-button"
        >
          {initialData ? "Update Flavor" : "Create Flavor"}
        </Button>
      </div>
    </form>
  );
}
