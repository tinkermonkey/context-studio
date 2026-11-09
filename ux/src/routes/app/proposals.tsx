import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  ProposalsListPage,
  type ProposalStatusFilter,
} from "@/components/proposals/ProposalsListPage";

interface ProposalsSearch {
  status?: ProposalStatusFilter;
  taxonomy?: string;
}

const STATUSES: ProposalStatusFilter[] = ["open", "done", "unlanded", "reverted", "all"];

function ProposalsRoute() {
  const navigate = useNavigate();
  const { status, taxonomy } = Route.useSearch();
  return (
    <ProposalsListPage
      status={status ?? "open"}
      taxonomyId={taxonomy}
      onFiltersChange={(filters) =>
        navigate({
          to: "/app/proposals",
          search: {
            status: filters.status === "open" ? undefined : filters.status,
            taxonomy: filters.taxonomyId,
          },
          replace: true,
        })
      }
    />
  );
}

export const Route = createFileRoute("/app/proposals")({
  component: ProposalsRoute,
  validateSearch: (search: Record<string, unknown>): ProposalsSearch => ({
    status: STATUSES.includes(search.status as ProposalStatusFilter)
      ? (search.status as ProposalStatusFilter)
      : undefined,
    taxonomy: typeof search.taxonomy === "string" ? search.taxonomy : undefined,
  }),
});
