import React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { PredicateMappingManager } from "@/components/predicates/PredicateMappingManager";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { GitBranch } from "lucide-react";

export const Route = createFileRoute("/app/reference/predicates")({
  component: ReferencePredicatesComponent,
});

function ReferencePredicatesComponent() {
  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Predicate Mapping</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle icon={GitBranch}>Predicate Mapping</CsMainTitle>
        <PredicateMappingManager />
      </CsMain>
    </>
  );
}
