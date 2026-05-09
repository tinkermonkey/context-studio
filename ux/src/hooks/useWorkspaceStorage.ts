export function useWorkspaceStorage() {
  const WORKSPACE_KEY = "context-studio:workspace-path";

  const getWorkspacePath = (): string | null => {
    try {
      return localStorage.getItem(WORKSPACE_KEY);
    } catch {
      return null;
    }
  };

  const setWorkspacePath = (path: string): void => {
    try {
      localStorage.setItem(WORKSPACE_KEY, path);
    } catch (error) {
      console.error("Failed to save workspace path", error);
    }
  };

  const clearWorkspacePath = (): void => {
    try {
      localStorage.removeItem(WORKSPACE_KEY);
    } catch {
      // silence
    }
  };

  return {
    getWorkspacePath,
    setWorkspacePath,
    clearWorkspacePath,
  };
}
