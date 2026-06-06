import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, FormCallout } from "@tinkermonkey/heimdall-ui";
import "./batch-detail.css";

export const Route = createFileRoute("/app/pipelines/batches/$batchId")({
  component: BatchDetailPage,
});

function BatchDetailPage() {
  return (
    <div data-testid="batch-detail-page" className="batch-detail-container">
      <PageHeader eyebrow="Pipelines" title="Batch Details" />

      <FormCallout
        variant="info"
        data-testid="batch-unavailable-notice"
      >
        Batch execution requires a background task runner that is not yet available. Child runs enqueued to this batch will remain in PENDING state and cannot be executed until this feature is implemented.
      </FormCallout>

      <section className="batch-section">
        <h2 className="batch-section-title">
          Child Runs
        </h2>
        <div data-testid="batch-child-runs-placeholder" className="batch-placeholder">
          <p className="batch-placeholder-text">
            This batch has no child runs yet. When batch execution is available, runs submitted to this batch will appear here.
          </p>
          <p className="batch-placeholder-text batch-placeholder-subtext">
            Future releases will display:
          </p>
          <ul className="batch-placeholder-list">
            <li>Progress indicator (X / Y runs completed)</li>
            <li>Per-run status chips (PENDING, RUNNING, COMPLETED, FAILED)</li>
            <li>Run details and results</li>
            <li>Cancel all and resume-failed controls</li>
          </ul>
        </div>
      </section>
    </div>
  );
}
