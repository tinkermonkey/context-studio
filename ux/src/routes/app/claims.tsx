import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ClaimsPage } from "@/components/claims/ClaimsPage";
import { isValidity, type ClaimsSearch } from "@/components/claims/claimModel";

function text(value: unknown): string | undefined {
  return typeof value === "string" && value ? value : undefined;
}

function ClaimsRoute() {
  const navigate = useNavigate();
  const search = Route.useSearch();
  return (
    <ClaimsPage
      search={search}
      onSearchChange={(next) => navigate({ to: "/app/claims", search: next, replace: true })}
    />
  );
}

export const Route = createFileRoute("/app/claims")({
  component: ClaimsRoute,
  validateSearch: (search: Record<string, unknown>): ClaimsSearch => ({
    taxonomy: text(search.taxonomy),
    subject: text(search.subject),
    validity: isValidity(search.validity) ? search.validity : undefined,
    triage:
      search.triage === "triaged" || search.triage === "untriaged" ? search.triage : undefined,
    verdict: search.verdict === "with" || search.verdict === "without" ? search.verdict : undefined,
    selected: text(search.selected),
  }),
});
