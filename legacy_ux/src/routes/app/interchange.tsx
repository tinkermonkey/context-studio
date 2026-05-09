/**
 * Interchange Module Layout
 *
 * Layout route for the interchange (import/export) module
 */

import { createFileRoute, Outlet } from "@tanstack/react-router";
import { InterchangeSidebar } from "@/components/interchange/InterchangeSidebar";
import { CsMain } from "@/components/layout/cs_main";

export const Route = createFileRoute("/app/interchange")({
  component: InterchangeLayout,
});

function InterchangeLayout() {
  return (
    <>
      <InterchangeSidebar />
      <CsMain>
        <Outlet />
      </CsMain>
    </>
  );
}
