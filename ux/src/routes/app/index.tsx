import React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Spinner } from "flowbite-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { TreeChart } from "@/components/graphs/hierarchy/tree_chart";
import { useLayers } from "@/api/hooks/layers/useLayers";
import { useDomains } from "@/api/hooks/domains/useDomains";
import { useTerms } from "@/api/hooks/terms/useTerms";
import { buildHierarchicalTree } from "@/utils/treeBuilder";
import { ChartData } from "@/components/graphs/hierarchy/tree_data";

export const Route = createFileRoute("/app/")({
  component: RouteComponent,
});

function RouteComponent() {
  const { data: layers } = useLayers();
  const { data: domains } = useDomains();
  const { data: terms } = useTerms();

  const chartData = React.useMemo(() => {
    if (!layers || !domains || !terms) return null;
    return {
      root: buildHierarchicalTree({ layers, domains, terms }),
    } as ChartData;
  }, [layers, domains, terms]);

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Context</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle>Context Studio Dashboard</CsMainTitle>
        {chartData ? <TreeChart chartData={chartData} /> : <Spinner />}
      </CsMain>
    </>
  );
}
