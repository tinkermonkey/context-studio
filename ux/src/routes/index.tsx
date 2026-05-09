import { createFileRoute, Navigate } from "@tanstack/react-router";
import { getWorkspacePath } from "@/hooks/useWorkspaceStorage";

export const Route = createFileRoute("/")({
  component: IndexPage,
});

function IndexPage() {
  const workspacePath = getWorkspacePath();

  if (!workspacePath) {
    return <Navigate to="/welcome" />;
  }

  return <Navigate to="/app" />;
}
