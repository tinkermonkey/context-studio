import React from "react";
import { usePredicates } from "@/api/hooks/predicates";
import { createFileRoute } from "@tanstack/react-router";
import { PredicatesTable } from "@/components/node_tables/predicates_table";
import { Spinner } from "flowbite-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { Hash } from "lucide-react"

export const Route = createFileRoute("/app/predicates")({
  component: PredicatesPage,
});

function PredicatesPage() {
  const { data: predicates, isLoading, error } = usePredicates();
  const tableRef = React.useRef<any>(null);

  if (isLoading) {
    return <Spinner />;
  }
  if (error) {
    console.error(error);
    return <div>Error loading predicates</div>;
  }

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Predicates</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle icon={Hash}>Predicates</CsMainTitle>

        <PredicatesTable ref={tableRef} data={predicates?.data} />
      </CsMain>
    </>
  );
}
