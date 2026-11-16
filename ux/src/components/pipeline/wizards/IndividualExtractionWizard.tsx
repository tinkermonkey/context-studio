import { useState } from "react";
import { Button, Field, FormCallout } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useRunWizard } from "@/api/hooks/pipeline/useRunWizard";
import { selectionRequestFields, usePipelineSelection } from "@/hooks/usePipelineSelection";
import { useRunDataset } from "@/hooks/useRunDataset";
import { ImplementationConfigPicker } from "../ImplementationConfigPicker";
import { DATASET_REQUIRED, RunDatasetField } from "../RunDatasetField";
import { EntitySearchPicker, type Entity } from "../EntitySearchPicker";
import type { components } from "@/api/types";
import "./Wizards.css";

type PipelineRunRequest = components["schemas"]["PipelineRunRequest"];

export function IndividualExtractionWizard() {
  const { toast } = useToasts();
  const { isSubmitting, errors, setErrors, handleSubmit } = useRunWizard({
    type: "individual_extraction",
  });
  const selection = usePipelineSelection("individual_extraction");

  const [sourceText, setSourceText] = useState("");
  const [selectedOntology, setSelectedOntology] = useState<Entity | null>(null);
  const dataset = useRunDataset(selectedOntology?.id);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!sourceText.trim()) {
      newErrors.sourceText = "Source text is required";
    }

    if (!selectedOntology?.id) {
      newErrors.ontologyId = "Target ontology is required";
    }

    if (dataset.missing) {
      newErrors.dataset = DATASET_REQUIRED;
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
        ...dataset.fields,
        text: sourceText,
        ontology_id: selectedOntology!.id,
        ontology_name: selectedOntology!.label,
      };

      await handleSubmit(request);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to run pipeline";
      toast("error", errorMessage);
    }
  };

  return (
    <form onSubmit={onSubmit} data-testid="individual-extraction-wizard" className="wizard-form">
      <Field label="Source Text" required error={errors.sourceText} errorId="source-text-error">
        <textarea
          id="source-text-input"
          value={sourceText}
          onChange={(e) => {
            setSourceText(e.target.value);
            setErrors((prev) => ({ ...prev, sourceText: undefined }));
          }}
          placeholder="Paste or type text to extract individuals from…"
          rows={6}
          aria-invalid={!!errors.sourceText}
          aria-describedby={errors.sourceText ? "source-text-error" : undefined}
          data-testid="individual-extraction-source"
          className="wizard-textarea"
        />
      </Field>

      <Field label="Target Ontology" required error={errors.ontologyId} errorId="ontology-error">
        <EntitySearchPicker
          entityType="Taxonomy"
          selectedId={selectedOntology?.id}
          onSelect={(entity) => {
            setSelectedOntology(entity);
            setErrors((prev) => ({ ...prev, ontologyId: undefined }));
          }}
          placeholder="Search ontologies…"
          aria-invalid={!!errors.ontologyId}
          aria-describedby={errors.ontologyId ? "ontology-error" : undefined}
          data-testid="individual-extraction-ontology"
        />
      </Field>

      <RunDatasetField
        run={dataset}
        id="individual-extraction-dataset"
        error={errors.dataset}
        disabled={isSubmitting}
        onChange={() => setErrors((prev) => ({ ...prev, dataset: undefined }))}
      />

      <ImplementationConfigPicker
        selection={selection}
        idPrefix="individual-extraction"
        disabled={isSubmitting}
      />

      {isSubmitting && (
        <FormCallout variant="info" data-testid="individual-extraction-loading">
          Starting the run — it opens in Runs, where its progress shows
        </FormCallout>
      )}

      <Button
        type="submit"
        variant="primary"
        // Not before the taxonomy's datasets are read: whether one must be named is unknown.
        disabled={
          isSubmitting ||
          !sourceText.trim() ||
          !selectedOntology ||
          dataset.loading ||
          !!dataset.loadError
        }
        aria-busy={isSubmitting}
        data-testid="individual-extraction-submit"
      >
        {isSubmitting ? "Starting…" : "Run Pipeline"}
      </Button>
    </form>
  );
}
