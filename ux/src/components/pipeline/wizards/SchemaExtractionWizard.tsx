import { useState } from "react";
import { Button, Field, FormCallout } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useRunWizard } from "@/api/hooks/pipeline/useRunWizard";
import { selectionRequestFields, usePipelineSelection } from "@/hooks/usePipelineSelection";
import { ImplementationConfigPicker } from "../ImplementationConfigPicker";
import { EntitySearchPicker, type Entity } from "../EntitySearchPicker";
import type { components } from "@/api/types";
import "./Wizards.css";

type PipelineRunRequest = components["schemas"]["PipelineRunRequest"];

export function SchemaExtractionWizard() {
  const { toast } = useToasts();
  const { isSubmitting, errors, setErrors, handleSubmit } = useRunWizard({
    type: "schema_extraction",
  });
  const selection = usePipelineSelection("schema_extraction");

  const [document, setDocument] = useState("");
  const [selectedScope, setSelectedScope] = useState<Entity | null>(null);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!document.trim()) {
      newErrors.document = "Document text is required";
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
      const request: PipelineRunRequest = {
        ...selectionRequestFields(selection),
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

      <Field label="Scope (Optional)" hint="Taxonomy the run is reviewed and applied against">
        <EntitySearchPicker
          entityType="Taxonomy"
          selectedId={selectedScope?.id}
          onSelect={setSelectedScope}
          placeholder="Search taxonomies…"
          data-testid="schema-extraction-taxonomy-picker"
        />
      </Field>

      <ImplementationConfigPicker
        selection={selection}
        idPrefix="schema-extraction"
        disabled={isSubmitting}
      />

      {isSubmitting && (
        <FormCallout variant="info" data-testid="schema-extraction-loading">
          Starting the run — it opens in Runs, where its progress shows
        </FormCallout>
      )}

      <Button
        type="submit"
        variant="primary"
        disabled={isSubmitting || !document.trim()}
        aria-busy={isSubmitting}
        data-testid="schema-extraction-submit"
      >
        {isSubmitting ? "Starting…" : "Run Pipeline"}
      </Button>
    </form>
  );
}
