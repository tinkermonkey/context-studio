import { createFileRoute, Outlet } from "@tanstack/react-router";
import { CsMain } from "@/components/layout/cs_main";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { ConfigSidebar } from "@/components/configuration/ConfigSidebar";

export const Route = createFileRoute("/app/config")({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Configuration</CsSidebarTitle>
        <div className="mt-4">
          <ConfigSidebar />
        </div>
      </CsSidebar>
      <CsMain>
        <Outlet />
      </CsMain>
    </>
  );
}
