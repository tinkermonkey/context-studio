import React from "react";
import { useLayers } from "@/api/hooks/layers";
import { createFileRoute } from "@tanstack/react-router";
import { LayersTable } from "@/components/node_tables/layers_table";
import { Button, Spinner } from "flowbite-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { RefreshCcw } from "lucide-react";
import { LayerSelector } from "@/components/node_selectors/layer_selector"

export const Route = createFileRoute("/app/layers")({
  component: LayersPage,
});

function LayersPage() {
  const { data: layers, isLoading, error, refetch } = useLayers();
  const [currentLayer, setCurrentLayer] = React.useState<string | undefined>(undefined);

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
        <LayersTable data={layers} />
        <div className="mt-4 flex items-center justify-between gap-3">
            <Button color="blue" onClick={() => refetch()}>
              <RefreshCcw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
            <LayerSelector onSelect={(layer) => setCurrentLayer(layer ? layer.id : undefined)} value={currentLayer} />
        </div>
      </CsMain>
    </>
  );
}
