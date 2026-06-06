import { useState } from "react";
import { Button, Field, FormCallout } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useRunWizard } from "@/api/hooks/pipeline/useRunWizard";
import { ImplementationConfigPicker, decodeConfigSelection } from "../ImplementationConfigPicker";
import { EntitySearchPicker, type Entity } from "../EntitySearchPicker";
import type { components } from "@/api/types";
import "./Wizards.css";

type PipelineRunRequest = components["schemas"]["PipelineRunRequest"];

export function SchemaExtractionWizard() {
  const { toast } = useToasts();
  const { isSubmitting, errors, setErrors, handleSubmit } = useRunWizard({
    type: "schema_extraction",
  });

  const [document, setDocument] = useState("");
  const [selectedScope, setSelectedScope] = useState<Entity | null>(null);
  const [implementationId, setImplementationId] = useState("");
  const [configRef, setConfigRef] = useState("");
  const [runAsBatch, setRunAsBatch] = useState(false);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!document.trim()) {
      newErrors.document = "Document text is required";
    }

    if (!implementationId.trim()) {
      newErrors.implementationId = "Implementation is required";
    }

    if (!configRef.trim()) {
      newErrors.configRef = "Configuration is required";
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return false;
    }

    return true;
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    if (!validateForm()) {
      return;
    }

    try {
      const { configRef: configRefPart } = decodeConfigSelection(configRef);
      const request: PipelineRunRequest = {
        implementation_id: implementationId,
        configuration_ref: configRefPart,
        documents: [document],
        ...(selectedScope && {
          scope: selectedScope.id,
          scope_name: selectedScope.label,
        }),
      };

      await handleSubmit(request);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to run pipeline";
      toast("error", errorMessage);
    }
  };

  return (
    <form onSubmit={onSubmit} data-testid="schema-extraction-wizard" className="wizard-form">
      <Field label="Document" required error={errors.document} errorId="document-error">
        <textarea
          id="document-input"
          value={document}
          onChange={(e) => {
            setDocument(e.target.value);
            setErrors((prev) => ({ ...prev, document: undefined }));
          }}
          placeholder="Paste or type the document text to extract from…"
          rows={6}
          aria-invalid={!!errors.document}
          aria-describedby={errors.document ? "document-error" : undefined}
          data-testid="schema-extraction-document"
          className="wizard-textarea"
        />
      </Field>

      <Field label="Scope (Optional)" hint="Taxonomy or Concept Scheme to constrain extraction">
        <EntitySearchPicker
          entityType="Taxonomy"
          selectedId={selectedScope?.id}
          onSelect={setSelectedScope}
          placeholder="Search taxonomies…"
          data-testid="schema-extraction-taxonomy-picker"
        />
      </Field>

      <ImplementationConfigPicker
        pipelineType="schema_extraction"
        selectedImplementationId={implementationId}
        selectedConfigRef={configRef}
        onSelectImplementation={(id) => {
          setImplementationId(id);
          setErrors((prev) => ({ ...prev, implementationId: undefined }));
          setConfigRef("");
        }}
        onSelectConfig={(compositeValue) => {
          setConfigRef(compositeValue);
          setErrors((prev) => ({ ...prev, configRef: undefined }));
        }}
        disabled={isSubmitting}
        implementationError={errors.implementationId}
        configError={errors.configRef}
      />

      <div
        className="batch-toggle"
        role="group"
        aria-label="Batch execution"
        data-testid="schema-extraction-batch-toggle"
      >
        <label className="batch-toggle-label">
          <input
            type="checkbox"
            checked={runAsBatch}
            onChange={(e) => setRunAsBatch(e.target.checked)}
            disabled={isSubmitting}
            data-testid="schema-extraction-batch-checkbox"
          />
          <span>Run as batch</span>
        </label>
      </div>

      {isSubmitting && (
        <FormCallout variant="info" data-testid="schema-extraction-loading">
          Running pipeline — this may take up to a minute
        </FormCallout>
      )}

      <Button
        type="submit"
        variant="primary"
        disabled={isSubmitting || !document.trim()}
        aria-busy={isSubmitting}
        data-testid="schema-extraction-submit"
      >
        {isSubmitting ? "Running…" : "Run Pipeline"}
      </Button>
    </form>
  );
}
