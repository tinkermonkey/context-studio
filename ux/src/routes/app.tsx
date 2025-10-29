import { createFileRoute, Outlet } from "@tanstack/react-router";
import { CsNavbar } from "../components/layout/cs_navbar";

export const Route = createFileRoute("/app")({
  component: AppComponent,
});

function AppComponent() {
  return (
    <>
      <CsNavbar />
      <div className="mx-auto w-full max-w-7xl lg:flex lg:px-4">
        <Outlet />
      </div>
    </>
  );
}
