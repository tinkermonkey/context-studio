import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ProposalDetailPage } from "@/components/proposals/ProposalDetailPage";

interface ProposalSearch {
  /** The operation shown in the inspector. */
  op?: string;
}

function ProposalRoute() {
  const navigate = useNavigate();
  const { proposalId } = Route.useParams();
  const { op } = Route.useSearch();
  return (
    <ProposalDetailPage
      id={proposalId}
      selectedOperationId={op}
      onSelectOperation={(operationId) =>
        navigate({
          to: "/app/proposals/$proposalId",
          params: { proposalId },
          search: operationId ? { op: operationId } : {},
          replace: true,
        })
      }
    />
  );
}

export const Route = createFileRoute("/app/proposals_/$proposalId")({
  component: ProposalRoute,
  validateSearch: (search: Record<string, unknown>): ProposalSearch => ({
    op: typeof search.op === "string" ? search.op : undefined,
  }),
});
