import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ExtractionReviewPage } from "@/components/pipeline/extraction-review";

export const Route = createFileRoute("/app/pipelines/review")({
  component: ExtractionReviewRoute,
});

function ExtractionReviewRoute() {
  const navigate = useNavigate();
  return <ExtractionReviewPage onOpenRunHistory={() => navigate({ to: "/app/pipelines/runs" })} />;
}
