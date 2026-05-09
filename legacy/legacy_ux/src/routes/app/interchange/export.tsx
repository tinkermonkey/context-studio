/**
 * Interchange Export Page
 *
 * Page for exporting ontology data
 */

import { createFileRoute } from "@tanstack/react-router";
import { CsMainTitle } from "@/components/layout/cs_main";
import { ExportPanel } from "@/components/interchange/ExportPanel";

export const Route = createFileRoute("/app/interchange/export")({
  component: ExportComponent,
});

function ExportComponent() {
  return (
    <>
      <CsMainTitle>Export Ontology</CsMainTitle>
      <div className="mt-6">
        <ExportPanel />
      </div>
    </>
  );
}
