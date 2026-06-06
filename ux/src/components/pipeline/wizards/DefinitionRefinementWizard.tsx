import { useState, useMemo } from "react";
import { Button, Field, FormCallout } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useRunWizard } from "@/api/hooks/pipeline/useRunWizard";
import { useClass } from "@/api/hooks/ontology/useClasses";
import { ImplementationConfigPicker, decodeConfigSelection } from "../ImplementationConfigPicker";
import { EntitySearchPicker, type Entity } from "../EntitySearchPicker";
import type { components } from "@/api/types";
import "./Wizards.css";

type PipelineRunRequest = components["schemas"]["PipelineRunRequest"];

export function DefinitionRefinementWizard() {
  const { toast } = useToasts();
  const { isSubmitting, errors, setErrors, handleSubmit } = useRunWizard({
    type: "schema_node_definition_refinement",
  });

  const [selectedNode, setSelectedNode] = useState<Entity | null>(null);
  const [currentDefinition, setCurrentDefinition] = useState("");
  const [implementationId, setImplementationId] = useState("");
  const [configRef, setConfigRef] = useState("");

  const { data: selectedNodeDetails } = useClass(selectedNode?.id || "");

  const neighborhoodPreview = useMemo(() => {
    if (!selectedNodeDetails) return null;

    return {
      label: selectedNodeDetails.title || selectedNodeDetails.id,
      definition: selectedNodeDetails.description,
      outgoingRelationships: (selectedNodeDetails as any)
        .outgoing_relationships || [],
    };
  }, [selectedNodeDetails]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!selectedNode?.id) {
      newErrors.nodeId = "Class to refine is required";
    }

    if (!currentDefinition.trim()) {
      newErrors.currentDefinition = "Current definition is required";
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
        node_id: selectedNode!.id,
        current_definition: currentDefinition,
      };

      await handleSubmit(request);
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Failed to run pipeline";
      toast("error", errorMessage);
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      data-testid="definition-refinement-wizard"
      className="wizard-form"
    >
      <Field
        label="Class to Refine"
        required
        error={errors.nodeId}
        errorId="node-id-error"
      >
        <EntitySearchPicker
          entityType="Class"
          selectedId={selectedNode?.id}
          onSelect={(entity) => {
            setSelectedNode(entity);
            setErrors((prev) => ({ ...prev, nodeId: undefined }));
          }}
          placeholder="Search classes…"
          aria-invalid={!!errors.nodeId}
          aria-describedby={errors.nodeId ? "node-id-error" : undefined}
          data-testid="definition-refinement-class"
        />
      </Field>

      {neighborhoodPreview && (
        <div
          className="neighborhood-preview"
          data-testid="definition-refinement-neighborhood"
        >
          <h4>
            Neighborhood Preview
          </h4>
          <p style={{ marginBottom: "4px", fontWeight: 600 }}>
            {neighborhoodPreview.label}
          </p>
          {neighborhoodPreview.definition && (
            <p
              style={{
                marginBottom: "8px",
                fontSize: "var(--text-sm)",
                color: "rgb(var(--canvas-fg-2))",
              }}
            >
              {neighborhoodPreview.definition}
            </p>
          )}
          {neighborhoodPreview.outgoingRelationships.length > 0 && (
            <div>
              <h5>
                Relationships
              </h5>
              <ul>
                {neighborhoodPreview.outgoingRelationships
                  .slice(0, 5)
                  .map((rel: any) => (
                    <li key={rel.id || rel.target_id}>
                      {rel.relationship_type} → {rel.target_label || rel.target_id}
                    </li>
                  ))}
                {neighborhoodPreview.outgoingRelationships.length > 5 && (
                  <li>
                    +{neighborhoodPreview.outgoingRelationships.length - 5} more
                  </li>
                )}
              </ul>
            </div>
          )}
        </div>
      )}

      <Field
        label="Current Definition"
        required
        error={errors.currentDefinition}
        errorId="definition-error"
      >
        <textarea
          id="current-definition-input"
          value={currentDefinition}
          onChange={(e) => {
            setCurrentDefinition(e.target.value);
            setErrors((prev) => ({ ...prev, currentDefinition: undefined }));
          }}
          placeholder="Current definition to be refined…"
          rows={4}
          aria-invalid={!!errors.currentDefinition}
          aria-describedby={
            errors.currentDefinition ? "definition-error" : undefined
          }
          data-testid="definition-refinement-definition"
          className="wizard-textarea"
        />
      </Field>

      <ImplementationConfigPicker
        pipelineType="schema_node_definition_refinement"
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

      {isSubmitting && (
        <FormCallout
          variant="info"
          data-testid="definition-refinement-loading"
        >
          Running pipeline — this may take up to a minute
        </FormCallout>
      )}

      <Button
        type="submit"
        variant="primary"
        disabled={
          isSubmitting || !selectedNode || !currentDefinition.trim()
        }
        aria-busy={isSubmitting}
        data-testid="definition-refinement-submit"
      >
        {isSubmitting ? "Running…" : "Run Pipeline"}
      </Button>
    </form>
  );
}
