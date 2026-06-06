import { useState } from "react";
import { Button, Field, FormCallout } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useRunWizard } from "@/api/hooks/pipeline/useRunWizard";
import { ImplementationConfigPicker } from "../ImplementationConfigPicker";
import { EntitySearchPicker, type Entity } from "../EntitySearchPicker";
import type { components } from "@/api/types";
import "./Wizards.css";

type PipelineRunRequest = components["schemas"]["PipelineRunRequest"];

const KNOWLEDGE_SOURCES = [
  { id: "dbpedia", label: "DBpedia" },
  { id: "conceptnet", label: "ConceptNet" },
  { id: "wikidata", label: "Wikidata" },
  { id: "schema_org", label: "Schema.org" },
];

export function SchemaGroundingWizard() {
  const { toast } = useToasts();
  const { isSubmitting, errors, setErrors, handleSubmit } = useRunWizard({
    type: "schema_node_grounding",
  });

  const [selectedNodes, setSelectedNodes] = useState<Entity[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [implementationId, setImplementationId] = useState("");
  const [configRef, setConfigRef] = useState("");
  const [nodeType, setNodeType] = useState<"Class" | "PropertyDefinition">("Class");
  const [runAsBatch, setRunAsBatch] = useState(false);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (selectedNodes.length === 0) {
      newErrors.nodes = "At least one target node is required";
    }

    if (selectedSources.length === 0) {
      newErrors.sources = "At least one knowledge source is required";
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
      const configRefPart = configRef.split("_v")[0];
      const request: PipelineRunRequest = {
        implementation_id: implementationId,
        configuration_ref: configRefPart,
        nodes: selectedNodes.map((n) => ({ id: n.id })),
        sources: selectedSources,
      };

      await handleSubmit(request);
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Failed to run pipeline";
      toast("error", errorMessage);
    }
  };

  const handleNodeSelect = (entity: Entity | null) => {
    if (entity) {
      setSelectedNodes([entity]);
    } else {
      setSelectedNodes([]);
    }
    setErrors((prev) => ({ ...prev, nodes: undefined }));
  };

  const toggleSource = (sourceId: string) => {
    setSelectedSources((prev) =>
      prev.includes(sourceId)
        ? prev.filter((s) => s !== sourceId)
        : [...prev, sourceId]
    );
    setErrors((prev) => ({ ...prev, sources: undefined }));
  };

  return (
    <form
      onSubmit={onSubmit}
      data-testid="schema-grounding-wizard"
      className="wizard-form"
    >
      <div className="node-type-selector" data-testid="schema-grounding-node-type">
        <div className="node-type-label">Node Type</div>
        <div className="node-type-buttons">
          <button
            type="button"
            className={`node-type-button ${nodeType === "Class" ? "active" : ""}`}
            onClick={() => {
              setNodeType("Class");
              setSelectedNodes([]);
              setErrors((prev) => ({ ...prev, nodes: undefined }));
            }}
            disabled={isSubmitting}
            data-testid="schema-grounding-node-type-class"
          >
            Class
          </button>
          <button
            type="button"
            className={`node-type-button ${nodeType === "PropertyDefinition" ? "active" : ""}`}
            onClick={() => {
              setNodeType("PropertyDefinition");
              setSelectedNodes([]);
              setErrors((prev) => ({ ...prev, nodes: undefined }));
            }}
            disabled={isSubmitting}
            data-testid="schema-grounding-node-type-property"
          >
            Property Definition
          </button>
        </div>
      </div>

      <Field
        label="Target Nodes"
        required
        error={errors.nodes}
        errorId="nodes-error"
      >
        <EntitySearchPicker
          entityType={nodeType}
          selectedId={selectedNodes[0]?.id}
          onSelect={handleNodeSelect}
          placeholder={`Search ${nodeType === "Class" ? "classes" : "property definitions"} to ground…`}
          aria-invalid={!!errors.nodes}
          aria-describedby={errors.nodes ? "nodes-error" : undefined}
          data-testid="schema-grounding-nodes"
        />
      </Field>

      <Field
        label="Knowledge Sources"
        required
        error={errors.sources}
        errorId="sources-error"
      >
        <div
          className="sources-checkboxes"
          role="group"
          aria-label="Knowledge sources"
          aria-invalid={!!errors.sources}
          aria-describedby={errors.sources ? "sources-error" : undefined}
          data-testid="schema-grounding-sources"
        >
          {KNOWLEDGE_SOURCES.map((source) => (
            <label
              key={source.id}
              className="sources-label"
            >
              <input
                type="checkbox"
                checked={selectedSources.includes(source.id)}
                onChange={() => toggleSource(source.id)}
                disabled={isSubmitting}
                data-testid={`schema-grounding-source-${source.id}`}
              />
              {source.label}
            </label>
          ))}
        </div>
      </Field>

      <ImplementationConfigPicker
        pipelineType="schema_node_grounding"
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
        data-testid="schema-grounding-batch-toggle"
      >
        <label className="batch-toggle-label">
          <input
            type="checkbox"
            checked={runAsBatch}
            onChange={(e) => setRunAsBatch(e.target.checked)}
            disabled={isSubmitting}
            data-testid="schema-grounding-batch-checkbox"
          />
          <span>Run as batch</span>
        </label>
      </div>

      {isSubmitting && (
        <FormCallout variant="info" data-testid="schema-grounding-loading">
          Running pipeline — this may take up to a minute
        </FormCallout>
      )}

      <Button
        type="submit"
        variant="primary"
        disabled={
          isSubmitting ||
          selectedNodes.length === 0 ||
          selectedSources.length === 0
        }
        aria-busy={isSubmitting}
        data-testid="schema-grounding-submit"
      >
        {isSubmitting ? "Running…" : "Run Pipeline"}
      </Button>
    </form>
  );
}
