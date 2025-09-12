import React from "react";
import { useLayerNodes } from "@/api/hooks/structure_nodes/useStructureNodes";
import { createFileRoute } from "@tanstack/react-router";
import { LayersTable } from "@/components/node_tables/layers_table";
import { Spinner } from "flowbite-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { Layers } from "lucide-react";

export const Route = createFileRoute("/app/layers")({
  component: LayersPage,
});

function LayersPage() {
  const { data: layers, isLoading, error } = useLayerNodes();
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
        <CsMainTitle icon={Layers}>Layers</CsMainTitle>

        <LayersTable ref={tableRef} data={layers} />
      </CsMain>
    </>
  );
}
