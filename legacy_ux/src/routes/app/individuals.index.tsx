import React from "react";
import {
  createFileRoute,
  useNavigate,
  useSearch,
} from "@tanstack/react-router";
import { IndividualsTable } from "@/components/node_tables/individuals_table";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { Users } from "lucide-react";

// Define the search parameters schema
interface IndividualsSearch {
  query?: string;
  [key: string]: unknown;
}

export const Route = createFileRoute("/app/individuals/")({
  component: IndividualsPage,
  validateSearch: (search: Record<string, unknown>): IndividualsSearch => {
    return {
      query: search.query as string,
      ...search,
    };
  },
});

function IndividualsPage() {
  const navigate = useNavigate({ from: "/app/individuals/" });
  const search = useSearch({ from: "/app/individuals/" });

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
      const searchParams: IndividualsSearch = {};

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
        <div className="space-y-4">
          <CsSidebarTitle>Individuals</CsSidebarTitle>
          <div className="text-sm text-gray-600">
            <p>Browse and manage individual instances of ontology classes.</p>
          </div>
        </div>
      </CsSidebar>
      <CsMain>
        <CsMainTitle icon={Users}>Individuals</CsMainTitle>
        <IndividualsTable
          queryParams={queryParams}
          onQueryParamsChange={handleQueryParamsChange}
        />
      </CsMain>
    </>
  );
}
