import React from "react";
import {
  createFileRoute,
  useNavigate,
  useSearch,
} from "@tanstack/react-router";
import { ConceptSchemesTable } from "@/components/node_tables/concept_schemes_table";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { CollapsibleTaxonomiesList } from "@/components/misc/collapsible_taxonomies_list";
import { useTaxonomy } from "@/api/hooks/taxonomies";
import { Database } from "lucide-react";

// Define the search parameters schema
interface ConceptSchemesSearch {
  taxonomy_id?: string;
  query?: string;
  [key: string]: unknown;
}

export const Route = createFileRoute("/app/concept-schemes")({
  component: ConceptSchemesPage,
  validateSearch: (search: Record<string, unknown>): ConceptSchemesSearch => {
    return {
      taxonomy_id: search.taxonomy_id as string,
      query: search.query as string,
      ...search,
    };
  },
});

function ConceptSchemesPage() {

  const tableRef = React.useRef<any>(null);
  const navigate = useNavigate({ from: "/app/concept-schemes" });
  const search = useSearch({ from: "/app/concept-schemes" });

  // Use search params directly as query params - no need for separate state
  const queryParams = React.useMemo(() => {
    const params: Record<string, unknown> = {};

    Object.entries(search).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        params[key] = value;
      }
    });

    return params;
  }, [search]);

  // Load the taxonomy record if taxonomy_id is provided
  const {
    data: taxonomy,
    isLoading: taxonomyLoading,
    error: taxonomyError,
  } = useTaxonomy(queryParams.taxonomy_id as string);

  const handleQueryParamsChange = React.useCallback(
    (newParams: Record<string, unknown>) => {
      // Update URL search parameters to reflect current filters
      const searchParams: ConceptSchemesSearch = {};

      Object.entries(newParams).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          searchParams[key] = value;
        }
      });

      navigate({
        search: searchParams,
        replace: true, // Use replace to avoid cluttering history
      });
    },
    [navigate],
  );

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Taxonomies</CsSidebarTitle>
        <CollapsibleTaxonomiesList
          selectedTaxonomyId={queryParams.taxonomy_id as string}
          useLinks={true}
        />
      </CsSidebar>
      <CsMain>
        <CsMainTitle icon={Database}>
          Concept Schemes
          {!!queryParams.taxonomy_id && (
            <span className="ml-2 text-sm font-normal text-gray-600 dark:text-gray-400">
              (filtered by taxonomy)
            </span>
          )}
        </CsMainTitle>
        {!!queryParams.taxonomy_id && (
          <>
            <div className="text-md">
              Concept Schemes in the taxonomy{" "}
              <i className="font-bold">
                {taxonomy?.title || String(queryParams.taxonomy_id)}
              </i>
              {taxonomyLoading && <span> (loading...)</span>}
              {taxonomyError && (
                <span className="text-red-500"> (error loading taxonomy)</span>
              )}
            </div>
            <div className="py-3 pb-6">
              {taxonomy?.definition && `Taxonomy definition: ${taxonomy.definition}`}
            </div>
          </>
        )}

        <ConceptSchemesTable
          ref={tableRef}
          queryParams={queryParams}
          onQueryParamsChange={handleQueryParamsChange}
        />
      </CsMain>
    </>
  );
}
