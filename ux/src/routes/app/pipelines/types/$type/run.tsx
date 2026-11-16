import { createFileRoute, useParams } from "@tanstack/react-router";
import { PageHeader } from "@tinkermonkey/heimdall-ui";
import { RUN_WIZARDS } from "@/components/pipeline/wizards";
import "./run.css";

export const Route = createFileRoute("/app/pipelines/types/$type/run")({
  component: RunWizardPage,
});

function RunWizardPage() {
  const { type } = useParams({ from: "/app/pipelines/types/$type/run" as any });

  const WizardComponent = RUN_WIZARDS[type as string];

  if (!WizardComponent) {
    return (
      <div data-testid={`${type}-run-wizard-page-invalid`}>
        <PageHeader eyebrow="Pipelines" title="Invalid Pipeline Type" />
        <div className="wizard-padding">
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
      <PageHeader eyebrow="Pipelines" title={typeLabel} subtitle="Configure and run pipeline" />
      <div className="wizard-container wizard-padding">
        <WizardComponent />
      </div>
    </div>
  );
}
