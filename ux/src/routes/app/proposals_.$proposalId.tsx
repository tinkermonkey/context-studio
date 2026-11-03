import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ProposalDetailPage } from "@/components/proposals/ProposalDetailPage";

interface ProposalSearch {
  /** The operation shown in the inspector. */
  op?: string;
}

/**
 * One proposal's page. Keyed by proposal: checked operations, the threshold,
 * results and a revert conflict reset when moving to another one.
 */
export function ProposalPage({ proposalId, op }: { proposalId: string; op?: string }) {
  const navigate = useNavigate();
  return (
    <ProposalDetailPage
      key={proposalId}
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

function ProposalRoute() {
  const { proposalId } = Route.useParams();
  const { op } = Route.useSearch();
  return <ProposalPage proposalId={proposalId} op={op} />;
}

export const Route = createFileRoute("/app/proposals_/$proposalId")({
  component: ProposalRoute,
  validateSearch: (search: Record<string, unknown>): ProposalSearch => ({
    op: typeof search.op === "string" ? search.op : undefined,
  }),
});
