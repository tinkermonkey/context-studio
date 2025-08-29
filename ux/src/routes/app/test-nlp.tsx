import React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import MinimalTestNlpConceptChart from "@/components/nlp/MinimalTestNlpConceptChart";
import TestNlpConceptChart from "@/components/nlp/TestNlpConceptChart";

export const Route = createFileRoute("/app/test-nlp")({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>NLP Test</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle>NLP Concept Chart Test</CsMainTitle>
        <div className="p-4">
          <TestNlpConceptChart />
        </div>
      </CsMain>
    </>
  );
}
