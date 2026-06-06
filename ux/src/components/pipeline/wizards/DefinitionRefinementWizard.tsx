import { useState, useMemo } from "react";
import { Button, Field, FormCallout } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useRunWizard } from "@/api/hooks/pipeline/useRunWizard";
import { useClass } from "@/api/hooks/ontology/useClasses";
import { ImplementationConfigPicker } from "../ImplementationConfigPicker";
import { EntitySearchPicker, type Entity } from "../EntitySearchPicker";
import type { components } from "@/api/types";

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
      const request: PipelineRunRequest = {
        implementation_id: implementationId,
        configuration_ref: configRef,
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
          style={{
            padding: "12px",
            borderRadius: "4px",
            backgroundColor: "rgb(var(--canvas-bg-2))",
            border: "1px solid rgb(var(--canvas-border))",
            marginBottom: "12px",
          }}
        >
          <h4 style={{ marginBottom: "8px", fontSize: "var(--text-base)" }}>
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
              <h5 style={{ fontSize: "var(--text-sm)", marginBottom: "4px" }}>
                Relationships
              </h5>
              <ul
                style={{
                  listStyle: "none",
                  padding: 0,
                  fontSize: "var(--text-sm)",
                }}
              >
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
          style={{
            width: "100%",
            padding: "8px 12px",
            borderRadius: "4px",
            border: "1px solid rgb(var(--canvas-fg-4))",
            backgroundColor: "rgb(var(--canvas-bg))",
            fontSize: "var(--text-sm)",
            fontFamily: "monospace",
            color: "rgb(var(--canvas-fg-1))",
            resize: "vertical",
          }}
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
        onSelectConfig={(ref) => {
          setConfigRef(ref);
          setErrors((prev) => ({ ...prev, configRef: undefined }));
        }}
        disabled={isSubmitting}
        implementationError={errors.implementationId}
        configError={errors.configRef}
      />

      {errors.submit && (
        <FormCallout variant="error" data-testid="definition-refinement-error">
          {errors.submit}
        </FormCallout>
      )}

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
