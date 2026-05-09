import { createFileRoute, Navigate } from "@tanstack/react-router";
import { useWorkspaceStorage } from "@/hooks/useWorkspaceStorage";

export const Route = createFileRoute("/")({
  component: IndexPage,
});

function IndexPage() {
  const { getWorkspacePath } = useWorkspaceStorage();
  const workspacePath = getWorkspacePath();

  if (!workspacePath) {
    return <Navigate to="/welcome" />;
  }

  return <Navigate to="/app" />;
}
