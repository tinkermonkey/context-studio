import React from "react";
import { useTerms } from "@/api/hooks/terms";
import { useDomain } from "@/api/hooks/domains";
import { useLayers, useLayer } from "@/api/hooks/layers";
import {
  createFileRoute,
  useNavigate,
  useSearch,
} from "@tanstack/react-router";
import { TermsTable } from "@/components/node_tables/terms_table";
import { Spinner } from "flowbite-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { CollapsibleDomainsList } from "@/components/misc/collapsible_domains_list";
import type { components } from "@/api/client/types";

type LayerOut = components["schemas"]["LayerOut"];

// Define the search parameters schema
interface TermsSearch {
  layer_id?: string;
  domain_id?: string;
  query?: string;
  [key: string]: unknown;
}

export const Route = createFileRoute("/app/terms")({
  component: TermsPage,
  validateSearch: (search: Record<string, unknown>): TermsSearch => {
    return {
      layer_id: search.layer_id as string,
      domain_id: search.domain_id as string,
      query: search.query as string,
      ...search,
    };
  },
});

function TermsPage() {
  const {
    data: terms,
    isLoading: termsLoading,
    error: termsError,
  } = useTerms();
  const {
    data: layers,
    isLoading: layersLoading,
    error: layersError,
  } = useLayers();
  const tableRef = React.useRef<any>(null);
  const navigate = useNavigate({ from: "/app/terms" });
  const search = useSearch({ from: "/app/terms" });

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
      const searchParams: TermsSearch = {};

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

  // Load the layer record if layer_id is provided
  const {
    data: layer,
    isLoading: layerLoading,
    error: layerError,
  } = useLayer(queryParams.layer_id as string);

  // Load the domain record if domain_id is provided
  const {
    data: domain,
    isLoading: domainLoading,
    error: domainError,
  } = useDomain(queryParams.domain_id as string);

  if (termsLoading || layersLoading || layerLoading || domainLoading) {
    return <Spinner />;
  }
  if (termsError) {
    console.error(termsError);
    return <div>Error loading Terms</div>;
  }
  if (layersError) {
    console.error(layersError);
    return <div>Error loading Layers</div>;
  }
  if (layerError) {
    console.error(layerError);
    return <div>Error loading Layer</div>;
  }
  if (domainError) {
    console.error(domainError);
    return <div>Error loading Domain</div>;
  }

  // Sort layers alphabetically by title
  const sortedLayers = layers
    ? [...layers].sort((a, b) => a.title.localeCompare(b.title))
    : [];

  return (
    <>
      <CsSidebar>
        <div className="space-y-4">
          {sortedLayers.map((layer: LayerOut) => (
            <div key={layer.id} className="space-y-2">
              <CsSidebarTitle>{layer.title}</CsSidebarTitle>
              <CollapsibleDomainsList
                layerId={layer.id}
                useLinks={true}
              />
            </div>
          ))}
        </div>
      </CsSidebar>
      <CsMain>
        <CsMainTitle>Terms</CsMainTitle>
        {!!queryParams.layer_id && (
          <>
            <div className="text-md">
              Terms in the layer{" "}
              <i className="font-bold">
                {layer?.title || String(queryParams.layer_id)}
              </i>
              {layerLoading && <span> (loading...)</span>}
              {layerError && (
                <span className="text-red-500"> (error loading layer)</span>
              )}
            </div>
            <div className="py-3 pb-6">
              {layer?.definition && `Layer definition: ${layer.definition}`}
            </div>
          </>
        )}
        {!!queryParams.domain_id && (
          <>
            <div className="text-md">
              Terms in the domain{" "}
              <i className="font-bold">
                {domain?.title || String(queryParams.domain_id)}
              </i>
              {domainLoading && <span> (loading...)</span>}
              {domainError && (
                <span className="text-red-500"> (error loading domain)</span>
              )}
            </div>
            <div className="py-3 pb-6">
              {domain?.definition && `Domain definition: ${domain.definition}`}
            </div>
          </>
        )}

        <TermsTable
          ref={tableRef}
          queryParams={queryParams}
          onQueryParamsChange={handleQueryParamsChange}
        />
      </CsMain>
    </>
  );
}
