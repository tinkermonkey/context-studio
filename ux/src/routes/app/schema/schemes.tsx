import { createFileRoute, Outlet } from "@tanstack/react-router";

function SchemesLayout() {
  return <Outlet />;
}

export const Route = createFileRoute("/app/schema/schemes")({
  component: SchemesLayout,
});
