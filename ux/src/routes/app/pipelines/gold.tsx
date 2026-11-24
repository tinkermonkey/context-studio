import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { BenchmarkGoldPage } from "@/components/proposals/gold/BenchmarkGoldPage";

/** The benchmark gold checks; Check gold opens a check on its proposal page. */
function BenchmarkGoldRoute() {
  const navigate = useNavigate();
  return (
    <BenchmarkGoldPage
      onOpenReview={(proposalId) =>
        navigate({ to: "/app/proposals/$proposalId", params: { proposalId } })
      }
    />
  );
}

export const Route = createFileRoute("/app/pipelines/gold")({
  component: BenchmarkGoldRoute,
});
