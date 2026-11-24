import { useRef } from "react";
import { createFileRoute, useNavigate, useRouter } from "@tanstack/react-router";
import { ProposalDetailPage } from "@/components/proposals/ProposalDetailPage";

interface ProposalSearch {
  /** The operation shown in the inspector. */
  op?: string;
  /** The long text field open in the wide diff (#1661). */
  diff?: string;
}

/**
 * One proposal's page. Keyed by proposal: checked operations, the threshold,
 * results and a revert conflict reset when moving to another one. The wide
 * diff lives in the URL (&diff=<field>): opening it adds a history entry, so
 * Back closes it; stepping fields or operations in it replaces that entry.
 * Closing it goes back over that entry while it still shows the operation it
 * opened on; after J / K moved to another, closing replaces the entry with that
 * operation instead, so the reviewer stays on it.
 */
export function ProposalPage({
  proposalId,
  op,
  diff,
}: {
  proposalId: string;
  op?: string;
  diff?: string;
}) {
  const navigate = useNavigate();
  const router = useRouter();
  // The operation the wide diff was opened on here (its entry pushed); undefined when
  // it wasn't opened here (a deep link) or was left another way.
  const diffOpenedOn = useRef<string | undefined>(undefined);
  return (
    <ProposalDetailPage
      key={proposalId}
      id={proposalId}
      selectedOperationId={op}
      diffField={diff}
      onDiff={(field, operationId) => {
        if (field === undefined) {
          const openedOn = diffOpenedOn.current;
          diffOpenedOn.current = undefined;
          if (openedOn !== undefined && openedOn === op) {
            router.history.back();
          } else {
            navigate({
              to: "/app/proposals/$proposalId",
              params: { proposalId },
              search: op ? { op } : {},
              replace: true,
            });
          }
          return;
        }
        const opening = !diff;
        if (opening) diffOpenedOn.current = operationId ?? op ?? "";
        navigate({
          to: "/app/proposals/$proposalId",
          params: { proposalId },
          search: { op: operationId ?? op, diff: field },
          replace: !opening,
        });
      }}
      onCompare={(otherId) =>
        navigate({
          to: "/app/proposals/$proposalId/compare/$otherId",
          params: { proposalId, otherId },
        })
      }
      onReviewAgainstSource={() =>
        navigate({ to: "/app/proposals/$proposalId/review", params: { proposalId } })
      }
      onSelectOperation={(operationId) => {
        diffOpenedOn.current = undefined;
        navigate({
          to: "/app/proposals/$proposalId",
          params: { proposalId },
          search: operationId ? { op: operationId } : {},
          replace: true,
        });
      }}
    />
  );
}

function ProposalRoute() {
  const { proposalId } = Route.useParams();
  const { op, diff } = Route.useSearch();
  return <ProposalPage proposalId={proposalId} op={op} diff={diff} />;
}

export const Route = createFileRoute("/app/proposals_/$proposalId")({
  component: ProposalRoute,
  validateSearch: (search: Record<string, unknown>): ProposalSearch => ({
    op: typeof search.op === "string" ? search.op : undefined,
    diff: typeof search.diff === "string" ? search.diff : undefined,
  }),
});
