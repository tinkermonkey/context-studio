import React from "react";
import { useTerms } from "@/api/hooks/terms";
import { createFileRoute } from "@tanstack/react-router";
import { TermsTable } from "@/components/node_tables/terms_table";
import { Spinner } from "flowbite-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";

export const Route = createFileRoute("/app/terms")({
  component: TermsPage,
});

function TermsPage() {
  const { data: terms, isLoading, error } = useTerms();
  const tableRef = React.useRef<any>(null);

  if (isLoading) {
    return <Spinner />;
  }
  if (error) {
    console.error(error);
    return <div>Error loading Terms</div>;
  }

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Terms</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle>Terms</CsMainTitle>
        <TermsTable ref={tableRef} data={terms} />
      </CsMain>
    </>
  );
}
