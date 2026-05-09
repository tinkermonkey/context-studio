import { createRootRoute, Outlet } from "@tanstack/react-router";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/api/utils/queryClient";
import { CommandPalette } from "@/components/shell/CommandPalette";

export const Route = createRootRoute({
  component: Root,
});

function Root() {
  return (
    <QueryClientProvider client={queryClient}>
      <Outlet />
      <CommandPalette />
    </QueryClientProvider>
  );
}
