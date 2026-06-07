import { useState, useMemo } from "react";
import { Button, Field, FormCallout } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useRunWizard } from "@/api/hooks/pipeline/useRunWizard";
import { useClass } from "@/api/hooks/ontology/useClasses";
import { ImplementationConfigPicker, decodeConfigSelection } from "../ImplementationConfigPicker";
import { EntitySearchPicker, type Entity } from "../EntitySearchPicker";
import { BatchToggle } from "./BatchToggle";
import { type RelationshipPreview } from "./types";
import type { components } from "@/api/types";
import "./Wizards.css";

type PipelineRunRequest = components["schemas"]["PipelineRunRequest"];

export function ConnectionRefinementWizard() {
  const { toast } = useToasts();
  const { isSubmitting, errors, setErrors, handleSubmit } = useRunWizard({
    type: "schema_node_connection_refinement",
  });

  const [selectedScope, setSelectedScope] = useState<Entity | null>(null);
  const [implementationId, setImplementationId] = useState("");
  const [configRef, setConfigRef] = useState("");
  const [runAsBatch, setRunAsBatch] = useState(false);

  const { data: scopeClassDetails } = useClass(selectedScope?.id || "");

  const neighborhoodPreview = useMemo(() => {
    if (!scopeClassDetails) return null;

    return {
      label: scopeClassDetails.title || scopeClassDetails.id,
      // TODO: wire to relationship API when available
      outgoingRelationships: [] as RelationshipPreview[],
    };
  }, [scopeClassDetails]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!selectedScope?.id) {
      newErrors.scopeId = "Scope class is required";
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
        scope_id: selectedScope!.id,
        run_as_batch: runAsBatch,
      };

      await handleSubmit(request);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to run pipeline";
      toast("error", errorMessage);
    }
  };

  return (
    <form onSubmit={onSubmit} data-testid="connection-refinement-wizard" className="wizard-form">
      <Field label="Scope Class" required error={errors.scopeId} errorId="scope-id-error">
        <EntitySearchPicker
          entityType="Class"
          selectedId={selectedScope?.id}
          onSelect={(entity) => {
            setSelectedScope(entity);
            setErrors((prev) => ({ ...prev, scopeId: undefined }));
          }}
          placeholder="Search classes…"
          aria-invalid={!!errors.scopeId}
          aria-describedby={errors.scopeId ? "scope-id-error" : undefined}
          data-testid="connection-refinement-scope"
        />
      </Field>

      {neighborhoodPreview && (
        <div className="neighborhood-preview" data-testid="connection-refinement-neighborhood">
          <h4>{neighborhoodPreview.label} — Current Connections</h4>

          {neighborhoodPreview.outgoingRelationships.length > 0 ? (
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Subject</th>
                    <th>Predicate</th>
                    <th>Object</th>
                  </tr>
                </thead>
                <tbody>
                  {neighborhoodPreview.outgoingRelationships.slice(0, 10).map((rel: RelationshipPreview) => (
                    <tr key={rel.id || rel.target_id}>
                      <td>{neighborhoodPreview.label}</td>
                      <td>{rel.relationship_type}</td>
                      <td>{rel.target_label || rel.target_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {neighborhoodPreview.outgoingRelationships.length > 10 && (
                <p style={{ marginTop: "8px", fontSize: "var(--text-sm)" }}>
                  +{neighborhoodPreview.outgoingRelationships.length - 10} more connections
                </p>
              )}
            </div>
          ) : (
            <p
              style={{
                fontSize: "var(--text-sm)",
                color: "rgb(var(--canvas-fg-2))",
              }}
            >
              No current connections
            </p>
          )}
        </div>
      )}

      <ImplementationConfigPicker
        pipelineType="schema_node_connection_refinement"
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
        testIdPrefix="connection-refinement"
      />

      {isSubmitting && (
        <FormCallout variant="info" data-testid="connection-refinement-loading">
          Running pipeline — this may take up to a minute
        </FormCallout>
      )}

      <Button
        type="submit"
        variant="primary"
        disabled={isSubmitting || !selectedScope}
        aria-busy={isSubmitting}
        data-testid="connection-refinement-submit"
      >
        {isSubmitting ? "Running…" : "Run Pipeline"}
      </Button>
    </form>
  );
}
