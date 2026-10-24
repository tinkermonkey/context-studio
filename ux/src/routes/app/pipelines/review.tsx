import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ExtractionReviewPage } from "@/components/pipeline/extraction-review";

interface ReviewSearchParams {
  /** Opens an existing schema/individual extraction run for review. */
  runId?: string;
}

export const Route = createFileRoute("/app/pipelines/review")({
  component: ExtractionReviewRoute,
  validateSearch: (search: Record<string, unknown>): ReviewSearchParams => ({
    runId: typeof search.runId === "string" ? search.runId : undefined,
  }),
});

function ExtractionReviewRoute() {
  const navigate = useNavigate();
  const { runId } = Route.useSearch();
  return (
    <ExtractionReviewPage
      initialRunId={runId}
      onOpenRunHistory={() => navigate({ to: "/app/pipelines/runs" })}
    />
  );
}
