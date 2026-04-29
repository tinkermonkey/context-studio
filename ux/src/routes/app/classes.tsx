import React from "react";
import {
  useOntologyClasses,
} from "@/api/hooks/ontologyClasses";
import { useTaxonomies, useTaxonomy } from "@/api/hooks/taxonomies";
import { useConceptScheme } from "@/api/hooks/conceptSchemes";
import {
  createFileRoute,
  useNavigate,
  useSearch,
} from "@tanstack/react-router";
import { ClassesTable } from "@/components/node_tables/classes_table";
import { Spinner } from "flowbite-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { CollapsibleConceptSchemesList } from "@/components/misc/collapsible_concept_schemes_list";
import { Hash } from "lucide-react";

// Define the search parameters schema
interface ClassesSearch {
  taxonomy_id?: string;
  concept_scheme_id?: string;
  query?: string;
  [key: string]: unknown;
}

export const Route = createFileRoute("/app/classes")({
  component: ClassesPage,
  validateSearch: (search: Record<string, unknown>): ClassesSearch => {
    return {
      taxonomy_id: search.taxonomy_id as string,
      concept_scheme_id: search.concept_scheme_id as string,
      query: search.query as string,
      ...search,
    };
  },
});

function ClassesPage() {
  const {
    isLoading: classesLoading,
    error: classesError,
  } = useOntologyClasses();
  const {
    data: taxonomies,
    isLoading: taxonomiesLoading,
    error: taxonomiesError,
  } = useTaxonomies();

  const navigate = useNavigate({ from: "/app/classes" });
  const search = useSearch({ from: "/app/classes" });

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

  const handleQueryParamsChange = React.useCallback(
    (newParams: Record<string, unknown>) => {
      // Update URL search parameters to reflect current filters
      const searchParams: ClassesSearch = {};

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

  // Load the taxonomy record if taxonomy_id is provided
  const {
    data: taxonomy,
    isLoading: taxonomyLoading,
    error: taxonomyError,
  } = useTaxonomy((queryParams.taxonomy_id as string) ?? "");

  // Load the concept scheme record if concept_scheme_id is provided
  const {
    data: conceptScheme,
    isLoading: conceptSchemeLoading,
    error: conceptSchemeError,
  } = useConceptScheme((queryParams.concept_scheme_id as string) ?? "");

  if (classesLoading || taxonomiesLoading || taxonomyLoading || conceptSchemeLoading) {
    return <Spinner />;
  }
  if (classesError) {
    console.error(classesError);
    return <div>Error loading Classes</div>;
  }
  if (taxonomiesError) {
    console.error(taxonomiesError);
    return <div>Error loading Taxonomies</div>;
  }
  if (taxonomyError) {
    console.error(taxonomyError);
    return <div>Error loading Taxonomy</div>;
  }
  if (conceptSchemeError) {
    console.error(conceptSchemeError);
    return <div>Error loading Concept Scheme</div>;
  }

  // Sort taxonomies alphabetically by title
  const sortedTaxonomies = taxonomies
    ? [...taxonomies].sort((a, b) => a.title.localeCompare(b.title))
    : [];

  return (
    <>
      <CsSidebar>
        <div className="space-y-4">
          {sortedTaxonomies.map((taxonomy) => (
            <div key={taxonomy.id} className="space-y-2">
              <CsSidebarTitle>{taxonomy.title}</CsSidebarTitle>
              <CollapsibleConceptSchemesList taxonomyId={taxonomy.id} useLinks={true} />
            </div>
          ))}
        </div>
      </CsSidebar>
      <CsMain>
        <CsMainTitle icon={Hash}>Classes</CsMainTitle>
        {!!queryParams.taxonomy_id && (
          <>
            <div className="text-md">
              Classes in the taxonomy{" "}
              <i className="font-bold">
                {taxonomy?.title || String(queryParams.taxonomy_id)}
              </i>
              {taxonomyLoading && <span> (loading...)</span>}
              {taxonomyError && (
                <span className="text-red-500"> (error loading taxonomy)</span>
              )}
            </div>
            <div className="py-3 pb-6">
              {taxonomy?.description && `Taxonomy description: ${taxonomy.description}`}
            </div>
          </>
        )}
        {!!queryParams.concept_scheme_id && (
          <>
            <div className="text-md">
              Classes in the concept scheme{" "}
              <i className="font-bold">
                {conceptScheme?.title || String(queryParams.concept_scheme_id)}
              </i>
              {conceptSchemeLoading && <span> (loading...)</span>}
              {conceptSchemeError && (
                <span className="text-red-500"> (error loading concept scheme)</span>
              )}
            </div>
            <div className="py-3 pb-6">
              {conceptScheme?.description && `Concept Scheme description: ${conceptScheme.description}`}
            </div>
          </>
        )}

        <ClassesTable
          queryParams={queryParams}
          onQueryParamsChange={handleQueryParamsChange}
        />
      </CsMain>
    </>
  );
}
