import React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RelationshipsTable } from "@/components/node_tables/relationships_table";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { GitBranch } from "lucide-react";

export const Route = createFileRoute("/app/relationships")({
  component: RelationshipsPage,
});

function RelationshipsPage() {
  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Relationships</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle icon={GitBranch}>Relationships</CsMainTitle>
        <RelationshipsTable />
      </CsMain>
    </>
  );
}
