import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ComparePage } from "@/components/proposals/compare/ComparePage";

/** Two pipelines' proposals for one source compared; Finish goes back to proposal A. */
function ProposalCompareRoute() {
  const { proposalId, otherId } = Route.useParams();
  const navigate = useNavigate();
  return (
    <ComparePage
      key={`${proposalId}-${otherId}`}
      aId={proposalId}
      bId={otherId}
      onFinish={() => navigate({ to: "/app/proposals/$proposalId", params: { proposalId } })}
    />
  );
}

export const Route = createFileRoute("/app/proposals_/$proposalId_/compare/$otherId")({
  component: ProposalCompareRoute,
});
