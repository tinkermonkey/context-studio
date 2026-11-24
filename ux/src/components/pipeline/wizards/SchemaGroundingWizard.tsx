import { useState } from "react";
import { Button, Field, FormCallout } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useRunWizard } from "@/api/hooks/pipeline/useRunWizard";
import { useReferenceStatus } from "@/api/hooks/reference";
import type { BatchRunSpec } from "@/api/hooks/pipeline/usePipelineMutations";
import { selectionRequestFields, usePipelineSelection } from "@/hooks/usePipelineSelection";
import { ImplementationConfigPicker } from "../ImplementationConfigPicker";
import { EntitySearchPicker, type Entity } from "../EntitySearchPicker";
import "./Wizards.css";

/** The test id of a source's checkbox: its name without punctuation ("schema.org" → "schema_org"). */
const sourceTestId = (name: string) =>
  `schema-grounding-source-${name.toLowerCase().replace(/[^a-z0-9]+/g, "_")}`;

export function SchemaGroundingWizard() {
  const { toast } = useToasts();
  const { isSubmitting, errors, setErrors, handleSubmitBatch } = useRunWizard({
    type: "schema_node_grounding",
  });
  const selection = usePipelineSelection("schema_node_grounding");
  // The names the grounding adapter registers its sources under (case-sensitive; it refuses
  // any other): the reference status lists the same sources.
  const {
    data: referenceStatus,
    isLoading: sourcesLoading,
    isError: sourcesFailed,
  } = useReferenceStatus();
  const knowledgeSources = referenceStatus?.sources ?? [];

  // One run per class: each grounds one label.
  const [selectedNodes, setSelectedNodes] = useState<Entity[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (selectedNodes.length === 0) {
      newErrors.nodes = "At least one target class is required";
    }

    if (selectedSources.length === 0) {
      newErrors.sources = "At least one knowledge source is required";
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
      // The server grounds the title of the class each node_id names.
      const specs: BatchRunSpec[] = selectedNodes.map((node) => ({
        pipeline_type: "schema_node_grounding",
        ...selectionRequestFields(selection),
        input_data: { node_id: node.id, node_type: "Class", sources: selectedSources },
      }));

      await handleSubmitBatch(specs);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to run pipeline";
      toast("error", errorMessage);
    }
  };

  const toggleSource = (sourceId: string) => {
    setSelectedSources((prev) =>
      prev.includes(sourceId) ? prev.filter((s) => s !== sourceId) : [...prev, sourceId],
    );
    setErrors((prev) => ({ ...prev, sources: undefined }));
  };

  return (
    <form onSubmit={onSubmit} data-testid="schema-grounding-wizard" className="wizard-form">
      <Field label="Target Classes" required error={errors.nodes} errorId="nodes-error">
        <EntitySearchPicker
          entityType="Class"
          multiSelect
          selectedIds={selectedNodes.map((node) => node.id)}
          onSelectMultiple={(entities) => {
            setSelectedNodes(entities);
            setErrors((prev) => ({ ...prev, nodes: undefined }));
          }}
          placeholder="Search classes to ground…"
          disabled={isSubmitting}
          aria-invalid={!!errors.nodes}
          aria-describedby={errors.nodes ? "nodes-error" : undefined}
          data-testid="schema-grounding-nodes"
        />
      </Field>
      <FormCallout variant="info" data-testid="schema-grounding-classes-only">
        Grounding applies to classes only, so property definitions can&apos;t be grounded here. Each
        selected class is its own run, started together.
      </FormCallout>

      <Field label="Knowledge Sources" required error={errors.sources} errorId="sources-error">
        <div
          className="sources-checkboxes"
          role="group"
          aria-label="Knowledge sources"
          aria-invalid={!!errors.sources}
          aria-describedby={errors.sources ? "sources-error" : undefined}
          data-testid="schema-grounding-sources"
        >
          {knowledgeSources.map((source) => (
            <label key={source.name} className="sources-label">
              <input
                type="checkbox"
                checked={selectedSources.includes(source.name)}
                onChange={() => toggleSource(source.name)}
                disabled={isSubmitting}
                data-testid={sourceTestId(source.name)}
              />
              {source.name}
            </label>
          ))}
          {sourcesLoading && (
            <span data-testid="schema-grounding-sources-loading">Loading knowledge sources…</span>
          )}
          {sourcesFailed && (
            <span role="alert" data-testid="schema-grounding-sources-error">
              Could not load the knowledge sources
            </span>
          )}
        </div>
      </Field>

      <ImplementationConfigPicker
        selection={selection}
        idPrefix="schema-grounding"
        disabled={isSubmitting}
      />

      {isSubmitting && (
        <FormCallout variant="info" data-testid="schema-grounding-loading">
          Starting the run — it opens in Runs, where its progress shows
        </FormCallout>
      )}

      <Button
        type="submit"
        variant="primary"
        disabled={isSubmitting || selectedNodes.length === 0 || selectedSources.length === 0}
        aria-busy={isSubmitting}
        data-testid="schema-grounding-submit"
      >
        {isSubmitting
          ? "Starting…"
          : selectedNodes.length > 1
            ? `Run ${selectedNodes.length} Pipelines`
            : "Run Pipeline"}
      </Button>
    </form>
  );
}
