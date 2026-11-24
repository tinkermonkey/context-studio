import { useRef } from "react";
import { createFileRoute, redirect, useNavigate, useRouter } from "@tanstack/react-router";
import { ProposalDetailPage } from "@/components/proposals/ProposalDetailPage";

interface ProposalSearch {
  /** The operation shown in the inspector. */
  selected?: string;
  /** The long text field open in the wide diff (#1661). */
  diff?: string;
  /** The old name for `selected` (before #1663): a link with it redirects. */
  op?: string;
}

/** Where an old link (?op=) goes: the same operation as ?selected=; undefined for a current one. */
export function redirectFromOp(search: ProposalSearch): ProposalSearch | undefined {
  if (!search.op) return undefined;
  return { selected: search.selected ?? search.op, ...(search.diff ? { diff: search.diff } : {}) };
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
  selected,
  diff,
}: {
  proposalId: string;
  selected?: string;
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
      selectedOperationId={selected}
      diffField={diff}
      onDiff={(field, operationId) => {
        if (field === undefined) {
          const openedOn = diffOpenedOn.current;
          diffOpenedOn.current = undefined;
          if (openedOn !== undefined && openedOn === selected) {
            router.history.back();
          } else {
            navigate({
              to: "/app/proposals/$proposalId",
              params: { proposalId },
              search: selected ? { selected } : {},
              replace: true,
            });
          }
          return;
        }
        const opening = !diff;
        if (opening) diffOpenedOn.current = operationId ?? selected ?? "";
        navigate({
          to: "/app/proposals/$proposalId",
          params: { proposalId },
          search: { selected: operationId ?? selected, diff: field },
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
          search: operationId ? { selected: operationId } : {},
          replace: true,
        });
      }}
    />
  );
}

function ProposalRoute() {
  const { proposalId } = Route.useParams();
  const { selected, diff } = Route.useSearch();
  return <ProposalPage proposalId={proposalId} selected={selected} diff={diff} />;
}

export const Route = createFileRoute("/app/proposals_/$proposalId")({
  component: ProposalRoute,
  validateSearch: (search: Record<string, unknown>): ProposalSearch => ({
    selected: typeof search.selected === "string" ? search.selected : undefined,
    diff: typeof search.diff === "string" ? search.diff : undefined,
    op: typeof search.op === "string" ? search.op : undefined,
  }),
  // An old link (?op=) becomes ?selected=, in place of the entry it came in on.
  beforeLoad: ({ params, search }) => {
    const target = redirectFromOp(search);
    if (target) {
      throw redirect({
        to: "/app/proposals/$proposalId",
        params,
        search: target,
        replace: true,
      });
    }
  },
});
