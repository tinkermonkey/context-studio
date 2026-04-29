import React from "react";
import { usePropertyDefinitions } from "@/api/hooks/propertyDefinitions";
import { createFileRoute } from "@tanstack/react-router";
import { PropertiesTable } from "@/components/node_tables/properties_table";
import { Spinner } from "flowbite-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { Hash } from "lucide-react";

export const Route = createFileRoute("/app/properties")({
  component: PropertiesPage,
});

function PropertiesPage() {
  const { data: properties, isLoading, error } = usePropertyDefinitions();

  const tableRef = React.useRef<any>(null);

  if (isLoading) {
    return <Spinner />;
  }
  if (error) {
    console.error(error);
    return <div>Error loading property definitions</div>;
  }

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Property Definitions</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle icon={Hash}>Property Definitions</CsMainTitle>

        <PropertiesTable ref={tableRef} data={properties?.data} />
      </CsMain>
    </>
  );
}
