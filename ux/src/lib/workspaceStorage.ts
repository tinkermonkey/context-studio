const WORKSPACE_KEY = "context-studio:workspace-path";

export const getWorkspacePath = (): string | null => {
  try {
    return localStorage.getItem(WORKSPACE_KEY);
  } catch {
    return null;
  }
};

export const setWorkspacePath = (path: string): void => {
  try {
    localStorage.setItem(WORKSPACE_KEY, path);
  } catch (error) {
    console.error("Failed to save workspace path", error);
  }
};

export const clearWorkspacePath = (): void => {
  try {
    localStorage.removeItem(WORKSPACE_KEY);
  } catch {
    // silence
  }
};
