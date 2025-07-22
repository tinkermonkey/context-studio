import { useDomains } from "@/api/hooks/domains";
import { createFileRoute } from "@tanstack/react-router";
import { DomainsTable } from "@/components/node_tables/domains_table";
import { Spinner } from "flowbite-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";

export const Route = createFileRoute("/app/domains")({
  component: DomainsPage,
});

function DomainsPage() {
  const { data: domains, isLoading, error, refetch } = useDomains();

  if (isLoading) {
    return <Spinner />;
  }

  if (error) {
    console.error(error);
    return <div>Error loading Domains</div>;
  }

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Domains</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle>Domains</CsMainTitle>
        <DomainsTable data={domains} />
      </CsMain>
    </>
  );
}
