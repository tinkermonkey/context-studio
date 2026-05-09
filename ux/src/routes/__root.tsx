import { createRootRoute, Outlet } from "@tanstack/react-router";
import { ApiProvider } from "@/api/ApiProvider";
import { CommandPalette } from "@/components/shell/CommandPalette";

export const Route = createRootRoute({
  component: Root,
});

function Root() {
  return (
    <ApiProvider>
      <Outlet />
      <CommandPalette />
    </ApiProvider>
  );
}
