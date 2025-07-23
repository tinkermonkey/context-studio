import React from "react";
import { useLayers } from "@/api/hooks/layers";
import { createFileRoute } from "@tanstack/react-router";
import { LayersTable } from "@/components/node_tables/layers_table";
import { Spinner } from "flowbite-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";

export const Route = createFileRoute("/app/layers")({
  component: LayersPage,
});

function LayersPage() {
  const { data: layers, isLoading, error } = useLayers();
  const tableRef = React.useRef<any>(null);

  if (isLoading) {
    return <Spinner />;
  }
  if (error) {
    console.error(error);
    return <div>Error loading layers</div>;
  }

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Layers</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle>Layers</CsMainTitle>

        <LayersTable ref={tableRef} data={layers} />
      </CsMain>
    </>
  );
}
