import { createFileRoute, redirect } from "@tanstack/react-router";

interface ReviewSearch {
  /** The operation open in the inspector: an element or a relationship. */
  selected?: string;
}

/**
 * The review against the source is the proposal's own page now (#1664): an old
 * /review link lands there with the same selection, in place of the entry it
 * came in on.
 */
export const Route = createFileRoute("/app/proposals_/$proposalId_/review")({
  validateSearch: (search: Record<string, unknown>): ReviewSearch => ({
    selected: typeof search.selected === "string" ? search.selected : undefined,
  }),
  beforeLoad: ({ params, search }) => {
    throw redirect({
      to: "/app/proposals/$proposalId",
      params: { proposalId: params.proposalId },
      search: search.selected ? { selected: search.selected } : {},
      replace: true,
    });
  },
});
