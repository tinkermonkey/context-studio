import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { WorkspaceSwitcher } from "@/components/workspace/WorkspaceSwitcher";
import { useWorkspaceStorage } from "@/hooks/useWorkspaceStorage";

export const Route = createFileRoute("/welcome")({
  component: WelcomePage,
});

function WelcomePage() {
  const navigate = useNavigate();
  const { setWorkspacePath } = useWorkspaceStorage();

  const handleWorkspaceSelect = (path: string) => {
    setWorkspacePath(path);
    navigate({ to: "/app" });
  };

  return <WorkspaceSwitcher onSelect={handleWorkspaceSelect} />;
}
