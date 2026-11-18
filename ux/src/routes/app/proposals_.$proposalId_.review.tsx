import { createFileRoute, useNavigate, useRouter } from "@tanstack/react-router";
import { ReviewPage } from "@/components/proposals/review/ReviewPage";

interface ReviewSearch {
  /** The operation open in the inspector: an element or a relationship. */
  selected?: string;
}

/**
 * An extraction proposal reviewed against its whole source; Finish goes back to
 * the proposal. The selection lives in the URL (?selected=<operation id>): each
 * selection pushes a history entry, so Back and Forward move between them, and
 * a link to one opens it (in a new tab, or after a reload).
 */
function ProposalReviewRoute() {
  const { proposalId } = Route.useParams();
  const { selected } = Route.useSearch();
  const navigate = useNavigate();
  const router = useRouter();
  const to = "/app/proposals/$proposalId/review" as const;
  return (
    <ReviewPage
      key={proposalId}
      id={proposalId}
      selectedId={selected}
      onSelect={(operationId) =>
        navigate({
          to,
          params: { proposalId },
          search: (prev: Record<string, unknown>) => ({ ...prev, selected: operationId }),
        })
      }
      hrefOf={(operationId) =>
        router.buildLocation({ to, params: { proposalId }, search: { selected: operationId } }).href
      }
      onFinish={() => navigate({ to: "/app/proposals/$proposalId", params: { proposalId } })}
    />
  );
}

export const Route = createFileRoute("/app/proposals_/$proposalId_/review")({
  component: ProposalReviewRoute,
  validateSearch: (search: Record<string, unknown>): ReviewSearch => ({
    selected: typeof search.selected === "string" ? search.selected : undefined,
  }),
});
