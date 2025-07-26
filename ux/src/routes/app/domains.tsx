import React from "react";
import {
  createFileRoute,
  useNavigate,
  useSearch,
} from "@tanstack/react-router";
import { DomainsTable } from "@/components/node_tables/domains_table";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { CollapsibleLayersList } from "@/components/misc/collapsible_layers_list";
import { useLayer } from "@/api/hooks/layers";

// Define the search parameters schema
interface DomainsSearch {
  layer_id?: string;
  query?: string;
  [key: string]: unknown;
}

export const Route = createFileRoute("/app/domains")({
  component: DomainsPage,
  validateSearch: (search: Record<string, unknown>): DomainsSearch => {
    return {
      layer_id: search.layer_id as string,
      query: search.query as string,
      ...search,
    };
  },
});

function DomainsPage() {
  const tableRef = React.useRef<any>(null);
  const navigate = useNavigate({ from: "/app/domains" });
  const search = useSearch({ from: "/app/domains" });

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

  // Load the layer record if layer_id is provided
  const {
    data: layer,
    isLoading: layerLoading,
    error: layerError,
  } = useLayer(queryParams.layer_id as string);

  const handleQueryParamsChange = React.useCallback(
    (newParams: Record<string, unknown>) => {
      // Update URL search parameters to reflect current filters
      const searchParams: DomainsSearch = {};

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
        <CsSidebarTitle>Layers</CsSidebarTitle>
        <CollapsibleLayersList
          selectedLayerId={queryParams.layer_id as string}
          useLinks={true}
        />
      </CsSidebar>
      <CsMain>
        <CsMainTitle>
          Domains
          {!!queryParams.layer_id && (
            <span className="ml-2 text-sm font-normal text-gray-600 dark:text-gray-400">
              (filtered by layer)
            </span>
          )}
        </CsMainTitle>
        {!!queryParams.layer_id && (
          <>
            <div className="text-md">
              Domains in the layer{" "}
              <i className="font-bold">{layer?.title || String(queryParams.layer_id)}</i>
              {layerLoading && <span> (loading...)</span>}
              {layerError && (
                <span className="text-red-500"> (error loading layer)</span>
              )}
            </div>
            <div className="py-3 pb-6">{layer?.definition && `Layer definition: ${layer.definition}`}</div>
          </>
        )}

        <DomainsTable
          ref={tableRef}
          queryParams={queryParams}
          onQueryParamsChange={handleQueryParamsChange}
        />
      </CsMain>
    </>
  );
}
