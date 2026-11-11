import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { SourcesPage } from "@/components/sources/SourcesPage";

interface SourcesSearchParams {
  taxonomy?: string;
}

function SourcesRoute() {
  const { taxonomy } = Route.useSearch();
  const navigate = useNavigate();
  return (
    <SourcesPage
      taxonomyId={taxonomy}
      onTaxonomyChange={(next) =>
        navigate({
          to: "/app/data/sources",
          // Another taxonomy's dataset would scope nothing: drop it.
          search: (prev) => ({ ...prev, taxonomy: next, dataset: undefined }),
          replace: true,
        })
      }
    />
  );
}

export const Route = createFileRoute("/app/data/sources")({
  validateSearch: (search: Record<string, unknown>): SourcesSearchParams => ({
    taxonomy: typeof search.taxonomy === "string" && search.taxonomy ? search.taxonomy : undefined,
  }),
  component: SourcesRoute,
});
