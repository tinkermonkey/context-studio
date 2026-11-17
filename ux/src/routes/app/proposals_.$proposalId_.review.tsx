import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ReviewPage } from "@/components/proposals/review/ReviewPage";

/** An extraction proposal reviewed against its whole source; Finish goes back to the proposal. */
function ProposalReviewRoute() {
  const { proposalId } = Route.useParams();
  const navigate = useNavigate();
  return (
    <ReviewPage
      key={proposalId}
      id={proposalId}
      onFinish={() => navigate({ to: "/app/proposals/$proposalId", params: { proposalId } })}
    />
  );
}

export const Route = createFileRoute("/app/proposals_/$proposalId_/review")({
  component: ProposalReviewRoute,
});
