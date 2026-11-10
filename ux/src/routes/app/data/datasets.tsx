import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { DatasetsPage } from "@/components/datasets/DatasetsPage";

interface DatasetsSearchParams {
  taxonomy?: string;
}

function DatasetsRoute() {
  const { taxonomy } = Route.useSearch();
  const navigate = useNavigate();
  return (
    <DatasetsPage
      taxonomyId={taxonomy}
      onTaxonomyChange={(next) =>
        navigate({
          to: "/app/data/datasets",
          search: (prev) => ({ ...prev, taxonomy: next }),
          replace: true,
        })
      }
    />
  );
}

export const Route = createFileRoute("/app/data/datasets")({
  validateSearch: (search: Record<string, unknown>): DatasetsSearchParams => ({
    taxonomy: typeof search.taxonomy === "string" && search.taxonomy ? search.taxonomy : undefined,
  }),
  component: DatasetsRoute,
});
