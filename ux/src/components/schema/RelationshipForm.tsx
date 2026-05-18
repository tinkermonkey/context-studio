import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Input";
import type { components } from "@/api/types";

type RelationshipCreateRequest = components["schemas"]["RelationshipCreateRequest"];
type ClassResponse = components["schemas"]["ClassResponse"];
type PropertyDefinitionResponse = components["schemas"]["PropertyDefinitionResponse"];

interface RelationshipFormProps {
  onSubmit: (data: RelationshipCreateRequest) => Promise<void>;
  isLoading?: boolean;
  classes: ClassResponse[];
  properties: PropertyDefinitionResponse[];
}

export function RelationshipForm({
  onSubmit,
  isLoading,
  classes,
  properties,
}: RelationshipFormProps) {
  const [sourceId, setSourceId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [relationshipType, setRelationshipType] = useState("");
  const [sourceError, setSourceError] = useState<string>();
  const [targetError, setTargetError] = useState<string>();
  const [typeError, setTypeError] = useState<string>();

  const validateFields = (): boolean => {
    let isValid = true;

    if (!sourceId.trim()) {
      setSourceError("Source class is required");
      isValid = false;
    } else {
      setSourceError(undefined);
    }

    if (!targetId.trim()) {
      setTargetError("Target class is required");
      isValid = false;
    } else {
      setTargetError(undefined);
    }

    if (!relationshipType.trim()) {
      setTypeError("Relationship type is required");
      isValid = false;
    } else {
      setTypeError(undefined);
    }

    return isValid;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateFields()) {
      return;
    }

    await onSubmit({
      source_id: sourceId,
      target_id: targetId,
      relationship_type: relationshipType,
    });
  };

  return (
    <form onSubmit={handleSubmit} data-testid="relationship-form">
      <div className="stack-lg">
        <Field
          label="Source Class"
          required
          error={sourceError}
        >
          <select
            value={sourceId}
            onChange={(e) => {
              setSourceId(e.target.value);
              setSourceError(undefined);
            }}
            data-testid="relationship-source-select"
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "4px",
              border: "1px solid var(--canvas-fg-4, #e5e7eb)",
              backgroundColor: "var(--canvas-bg, #ffffff)",
              fontSize: "var(--text-sm)",
              fontFamily: "inherit",
            }}
          >
            <option value="">Select a source class</option>
            {classes.map((cls) => (
              <option key={cls.id} value={cls.id}>
                {cls.title}
              </option>
            ))}
          </select>
        </Field>

        <Field
          label="Target Class"
          required
          error={targetError}
        >
          <select
            value={targetId}
            onChange={(e) => {
              setTargetId(e.target.value);
              setTargetError(undefined);
            }}
            data-testid="relationship-target-select"
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "4px",
              border: "1px solid var(--canvas-fg-4, #e5e7eb)",
              backgroundColor: "var(--canvas-bg, #ffffff)",
              fontSize: "var(--text-sm)",
              fontFamily: "inherit",
            }}
          >
            <option value="">Select a target class</option>
            {classes.map((cls) => (
              <option key={cls.id} value={cls.id}>
                {cls.title}
              </option>
            ))}
          </select>
        </Field>

        <Field
          label="Relationship Type (Property)"
          required
          error={typeError}
        >
          <select
            value={relationshipType}
            onChange={(e) => {
              setRelationshipType(e.target.value);
              setTypeError(undefined);
            }}
            data-testid="relationship-type-select"
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "4px",
              border: "1px solid var(--canvas-fg-4, #e5e7eb)",
              backgroundColor: "var(--canvas-bg, #ffffff)",
              fontSize: "var(--text-sm)",
              fontFamily: "inherit",
            }}
          >
            <option value="">Select a relationship type</option>
            {properties.map((prop) => (
              <option key={prop.id} value={prop.identifier}>
                {prop.title}
              </option>
            ))}
          </select>
        </Field>

        <Button
          type="submit"
          variant="primary"
          disabled={isLoading}
          data-testid="relationship-submit-button"
        >
          Create Relationship
        </Button>
      </div>
    </form>
  );
}
