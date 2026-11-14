import { useState } from "react";
import { Button, Field, FormCallout, SegmentedControl } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useRunWizard } from "@/api/hooks/pipeline/useRunWizard";
import { selectionRequestFields, usePipelineSelection } from "@/hooks/usePipelineSelection";
import { ImplementationConfigPicker } from "../ImplementationConfigPicker";
import { EntitySearchPicker, type Entity } from "../EntitySearchPicker";
import type { components } from "@/api/types";
import "./Wizards.css";

type PipelineRunRequest = components["schemas"]["PipelineRunRequest"];

// The names the server's grounding adapter registers its sources under
// (case-sensitive; an unknown name is refused).
const KNOWLEDGE_SOURCES = [
  { id: "dbpedia", name: "DBpedia" },
  { id: "conceptnet", name: "ConceptNet" },
  { id: "wikidata", name: "Wikidata" },
  { id: "schema_org", name: "schema.org" },
];

export function SchemaGroundingWizard() {
  const { toast } = useToasts();
  const { isSubmitting, errors, setErrors, handleSubmit } = useRunWizard({
    type: "schema_node_grounding",
  });
  const selection = usePipelineSelection("schema_node_grounding");

  // One node per run: the pipeline grounds one label.
  const [selectedNode, setSelectedNode] = useState<Entity | null>(null);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [nodeType, setNodeType] = useState<"Class" | "PropertyDefinition">("Class");

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!selectedNode) {
      newErrors.nodes = "A target node is required";
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
      const request: PipelineRunRequest = {
        ...selectionRequestFields(selection),
        // The label is what is grounded; the id says which node the result is for.
        node_id: selectedNode!.id,
        node_label: selectedNode!.label,
        node_type: nodeType,
        sources: selectedSources,
      };

      await handleSubmit(request);
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
      <Field label="Node Type" data-testid="schema-grounding-node-type">
        <SegmentedControl
          value={nodeType}
          onChange={(value) => {
            setNodeType(value as "Class" | "PropertyDefinition");
            setSelectedNode(null);
            setErrors((prev) => ({ ...prev, nodes: undefined }));
          }}
          options={[
            { value: "Class", label: "Class" },
            { value: "PropertyDefinition", label: "Property Definition" },
          ]}
          disabled={isSubmitting}
        />
      </Field>

      <Field label="Target Node" required error={errors.nodes} errorId="nodes-error">
        <EntitySearchPicker
          entityType={nodeType}
          selectedId={selectedNode?.id}
          onSelect={(entity) => {
            setSelectedNode(entity);
            setErrors((prev) => ({ ...prev, nodes: undefined }));
          }}
          placeholder={`Search ${nodeType === "Class" ? "classes" : "property definitions"} to ground…`}
          aria-invalid={!!errors.nodes}
          aria-describedby={errors.nodes ? "nodes-error" : undefined}
          data-testid="schema-grounding-nodes"
        />
      </Field>

      <Field label="Knowledge Sources" required error={errors.sources} errorId="sources-error">
        <div
          className="sources-checkboxes"
          role="group"
          aria-label="Knowledge sources"
          aria-invalid={!!errors.sources}
          aria-describedby={errors.sources ? "sources-error" : undefined}
          data-testid="schema-grounding-sources"
        >
          {KNOWLEDGE_SOURCES.map((source) => (
            <label key={source.id} className="sources-label">
              <input
                type="checkbox"
                checked={selectedSources.includes(source.name)}
                onChange={() => toggleSource(source.name)}
                disabled={isSubmitting}
                data-testid={`schema-grounding-source-${source.id}`}
              />
              {source.name}
            </label>
          ))}
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
        disabled={isSubmitting || !selectedNode || selectedSources.length === 0}
        aria-busy={isSubmitting}
        data-testid="schema-grounding-submit"
      >
        {isSubmitting ? "Starting…" : "Run Pipeline"}
      </Button>
    </form>
  );
}
