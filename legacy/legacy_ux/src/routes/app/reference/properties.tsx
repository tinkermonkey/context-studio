import React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { PredicateMappingManager } from "@/components/predicates/PredicateMappingManager";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { GitBranch } from "lucide-react";

export const Route = createFileRoute("/app/reference/properties")({
  component: ReferencePropertiesComponent,
});

function ReferencePropertiesComponent() {
  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Property Mapping</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle icon={GitBranch}>Property Mapping</CsMainTitle>
        <PredicateMappingManager />
      </CsMain>
    </>
  );
}
