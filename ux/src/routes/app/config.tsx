import { createFileRoute, Outlet } from "@tanstack/react-router";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";

export const Route = createFileRoute("/app/config")({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Config</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <Outlet />
      </CsMain>
    </>
  );
}
