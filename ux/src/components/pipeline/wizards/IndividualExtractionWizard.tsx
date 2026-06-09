import { useState } from "react";
import { Button, Field, FormCallout } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useRunWizard } from "@/api/hooks/pipeline/useRunWizard";
import { ImplementationConfigPicker, decodeConfigSelection } from "../ImplementationConfigPicker";
import { EntitySearchPicker, type Entity } from "../EntitySearchPicker";
import { BatchToggle } from "./BatchToggle";
import type { components } from "@/api/types";
import "./Wizards.css";

type PipelineRunRequest = components["schemas"]["PipelineRunRequest"];

export function IndividualExtractionWizard() {
  const { toast } = useToasts();
  const { isSubmitting, errors, setErrors, handleSubmit } = useRunWizard({
    type: "individual_extraction",
  });

  const [sourceText, setSourceText] = useState("");
  const [selectedOntology, setSelectedOntology] = useState<Entity | null>(null);
  const [implementationId, setImplementationId] = useState("");
  const [configRef, setConfigRef] = useState("");
  const [runAsBatch, setRunAsBatch] = useState(false);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!sourceText.trim()) {
      newErrors.sourceText = "Source text is required";
    }

    if (!selectedOntology?.id) {
      newErrors.ontologyId = "Target ontology is required";
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
        text: sourceText,
        ontology_id: selectedOntology!.id,
        ontology_name: selectedOntology!.label,
        run_as_batch: runAsBatch,
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

      <ImplementationConfigPicker
        pipelineType="individual_extraction"
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

      <BatchToggle
        checked={runAsBatch}
        onChange={setRunAsBatch}
        disabled={isSubmitting}
        testIdPrefix="individual-extraction"
      />

      {isSubmitting && (
        <FormCallout variant="info" data-testid="individual-extraction-loading">
          Running pipeline — this may take up to a minute
        </FormCallout>
      )}

      <Button
        type="submit"
        variant="primary"
        disabled={isSubmitting || !sourceText.trim() || !selectedOntology}
        aria-busy={isSubmitting}
        data-testid="individual-extraction-submit"
      >
        {isSubmitting ? "Running…" : "Run Pipeline"}
      </Button>
    </form>
  );
}
