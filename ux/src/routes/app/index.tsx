import React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { TreeChartPanel } from "@/components/panels/TreeChartPanel";

export const Route = createFileRoute("/app/")({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Context</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle>Context Studio Dashboard</CsMainTitle>
        <TreeChartPanel />
      </CsMain>
    </>
  );
}
