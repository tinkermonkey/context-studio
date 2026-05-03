/**
 * Interchange Recent Runs Page
 *
 * Landing page showing recent import runs
 */

import { createFileRoute } from "@tanstack/react-router";
import { CsMainTitle } from "@/components/layout/cs_main";
import { RecentRunsTable } from "@/components/interchange/RecentRunsTable";

export const Route = createFileRoute("/app/interchange/")({
  component: InterchangeIndexComponent,
});

function InterchangeIndexComponent() {
  return (
    <>
      <CsMainTitle>Import History</CsMainTitle>
      <div className="mt-6">
        <RecentRunsTable />
      </div>
    </>
  );
}
