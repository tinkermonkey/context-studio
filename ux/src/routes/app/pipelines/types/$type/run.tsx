import { createFileRoute, useParams } from "@tanstack/react-router";
import { PageHeader } from "@tinkermonkey/heimdall-ui";
import { SchemaExtractionWizard } from "@/components/pipeline/wizards/SchemaExtractionWizard";
import { IndividualExtractionWizard } from "@/components/pipeline/wizards/IndividualExtractionWizard";
import { SchemaGroundingWizard } from "@/components/pipeline/wizards/SchemaGroundingWizard";
import { DefinitionRefinementWizard } from "@/components/pipeline/wizards/DefinitionRefinementWizard";
import { ConnectionRefinementWizard } from "@/components/pipeline/wizards/ConnectionRefinementWizard";

const WIZARD_MAP: Record<string, React.ComponentType> = {
  schema_extraction: SchemaExtractionWizard,
  individual_extraction: IndividualExtractionWizard,
  schema_node_grounding: SchemaGroundingWizard,
  schema_node_definition_refinement: DefinitionRefinementWizard,
  schema_node_connection_refinement: ConnectionRefinementWizard,
};

export const Route = createFileRoute("/app/pipelines/types/$type/run")({
  component: RunWizardPage,
});

function RunWizardPage() {
  const { type } = useParams({ from: "/app/pipelines/types/$type/run" as any });

  const WizardComponent = WIZARD_MAP[type as string];

  if (!WizardComponent) {
    return (
      <div data-testid={`${type}-run-wizard-page-invalid`}>
        <PageHeader eyebrow="Pipelines" title="Invalid Pipeline Type" />
        <div style={{ padding: "24px" }}>
          <p>Invalid pipeline type: {type}</p>
        </div>
      </div>
    );
  }

  const typeLabel = (type as string)
    .split("_")
    .map((word: string) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

  return (
    <div data-testid={`${type}-run-wizard-page`}>
      <PageHeader
        eyebrow="Pipelines"
        title={typeLabel}
        subtitle="Configure and run pipeline"
      />
      <div className="wizard-container" style={{ padding: "24px" }}>
        <WizardComponent />
      </div>
    </div>
  );
}
