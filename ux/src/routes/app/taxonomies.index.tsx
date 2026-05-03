import React from "react";
import { useTaxonomies } from "@/api/hooks/taxonomies";
import { createFileRoute } from "@tanstack/react-router";
import { TaxonomiesTable } from "@/components/node_tables/taxonomies_table";
import { Spinner } from "flowbite-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { Layers } from "lucide-react";
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { TreeMenuPanel } from "@/components/panels/TreeMenuPanel";

export const Route = createFileRoute("/app/taxonomies/")({
  component: TaxonomiesPage,
});

function TaxonomiesPage() {
  const { data: taxonomies, isLoading, error } = useTaxonomies();

  const tableRef = React.useRef<any>(null);

  if (isLoading) {
    return <Spinner />;
  }
  if (error) {
    console.error(error);
    return <div>Error loading taxonomies</div>;
  }

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Taxonomies</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle icon={Layers}>Taxonomies</CsMainTitle>

        <TaxonomiesTable ref={tableRef} data={taxonomies} />
      </CsMain>
    </>
  );
}
