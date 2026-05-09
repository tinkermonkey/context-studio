import { AlertCircle, RefreshCw, FolderOpen, RotateCcw } from "lucide-react";
import { useWorkspaceStorage } from "@/hooks/useWorkspaceStorage";

interface WorkspaceErrorCardProps {
  onRetry: () => void;
  onChooseAnother: () => void;
}

export function WorkspaceErrorCard({
  onRetry,
  onChooseAnother,
}: WorkspaceErrorCardProps) {
  const { clearWorkspacePath } = useWorkspaceStorage();

  const handleReset = () => {
    clearWorkspacePath();
    window.location.href = "/";
  };

  return (
    <div
      data-testid="workspace-error-card"
      className="flex flex-col items-center gap-4 rounded-lg border border-red-500/30 bg-gray-800 px-6 py-12 text-center"
    >
      <AlertCircle size={48} className="text-red-400" />
      <div>
        <h2 className="mb-2 text-lg font-semibold text-gray-100">
          Workspace not found
        </h2>
        <p className="text-sm text-gray-400">
          The workspace folder could not be accessed. Try again or select a
          different folder.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-3">
        <button
          data-testid="workspace-error-retry-btn"
          type="button"
          onClick={onRetry}
          className="flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700"
        >
          <RefreshCw size={13} />
          Retry
        </button>
        <button
          data-testid="workspace-error-choose-btn"
          type="button"
          onClick={onChooseAnother}
          className="flex items-center gap-2 rounded-md border border-gray-600 bg-gray-700 px-4 py-2 text-sm font-medium text-gray-100 transition-colors hover:border-gray-500 hover:bg-gray-600"
        >
          <FolderOpen size={13} />
          Choose Another
        </button>
        <button
          data-testid="workspace-error-reset-btn"
          type="button"
          onClick={handleReset}
          className="flex items-center gap-2 rounded-md border border-gray-600 bg-gray-700 px-4 py-2 text-sm font-medium text-gray-400 transition-colors hover:border-gray-500 hover:bg-gray-600 hover:text-gray-300"
        >
          <RotateCcw size={13} />
          Reset
        </button>
      </div>
    </div>
  );
}
