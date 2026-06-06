import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, Icon } from "@tinkermonkey/heimdall-ui";
import { EmptyState } from "@/components/ui/EmptyState";

export const Route = createFileRoute("/app/pipelines/batches/$batchId")({
  component: BatchDetailPage,
});

function BatchDetailPage() {
  return (
    <div data-testid="batch-detail-page">
      <PageHeader eyebrow="Pipelines" title="Batch Details" />
      <EmptyState
        title="Batch Execution Unavailable"
        description="Batch execution requires a background task runner that is not yet available. Batches will be supported in a follow-up release."
        icon={<Icon name="info" size={48} />}
      />
    </div>
  );
}
