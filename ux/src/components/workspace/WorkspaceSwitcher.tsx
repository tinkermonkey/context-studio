import { useState, useRef } from "react";
import { FolderOpen, Plus, GitBranch } from "lucide-react";

interface WorkspaceSwitcherProps {
  onSelect: (path: string) => void;
  isLoading?: boolean;
}

export function WorkspaceSwitcher({ onSelect, isLoading = false }: WorkspaceSwitcherProps) {
  const [isSelectingFolder, setIsSelectingFolder] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleOpenFolder = async () => {
    setIsSelectingFolder(true);
    try {
      if (fileInputRef.current) {
        fileInputRef.current.click();
      }
    } catch (error) {
      console.error("Failed to open folder picker:", error);
    } finally {
      setIsSelectingFolder(false);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.currentTarget.files;
    if (files && files.length > 0) {
      const file = files[0];
      const path = file.webkitRelativePath || file.name;
      onSelect(path);
    }
  };

  const handleNewWorkspace = async () => {
    const folderName = prompt("Enter workspace folder name:");
    if (folderName) {
      onSelect(folderName);
    }
  };

  const handleCloneFromGit = async () => {
    const gitUrl = prompt("Enter git repository URL:");
    if (gitUrl) {
      try {
        onSelect(gitUrl);
      } catch (error) {
        console.error("Failed to clone from git:", error);
      }
    }
  };

  const isDisabled = isLoading || isSelectingFolder;

  return (
    <div
      data-testid="workspace-switcher-overlay"
      className="fixed inset-0 flex items-center justify-center bg-black/50"
    >
      <input
        ref={fileInputRef}
        type="file"
        style={{ display: "none" }}
        onChange={handleFileInputChange}
        data-testid="workspace-folder-input"
        {...({ webkitdirectory: "" } as any)}
      />
      <div
        data-testid="workspace-switcher-modal"
        className="w-[700px] rounded-lg border border-gray-700 bg-gray-900 shadow-lg"
      >
        <div className="space-y-2 border-b border-gray-700 px-8 py-8">
          <h1 className="text-xl font-semibold text-gray-100">Select Workspace</h1>
          <p className="text-sm text-gray-400">
            Choose how to set up your Context Studio workspace
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 p-8">
          <Tile
            testId="workspace-open-folder-tile"
            icon={<FolderOpen size={32} />}
            title="Open folder…"
            description="Use an existing folder as your workspace"
            onClick={handleOpenFolder}
            disabled={isDisabled}
          />
          <Tile
            testId="workspace-new-workspace-tile"
            icon={<Plus size={32} />}
            title="New workspace…"
            description="Create a new workspace in a new folder"
            onClick={handleNewWorkspace}
            disabled={isDisabled}
          />
          <Tile
            testId="workspace-clone-git-tile"
            icon={<GitBranch size={32} />}
            title="Clone from git…"
            description="Clone a workspace from a git repository"
            onClick={handleCloneFromGit}
            disabled={isDisabled}
          />
        </div>
      </div>
    </div>
  );
}

interface TileProps {
  testId: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
  disabled?: boolean;
}

function Tile({ testId, icon, title, description, onClick, disabled = false }: TileProps) {
  return (
    <button
      data-testid={testId}
      onClick={onClick}
      disabled={disabled}
      className="flex flex-col items-center gap-4 rounded-lg border border-gray-700 bg-gray-800 px-6 py-6 transition-all hover:border-cyan-500 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <div className="text-gray-500">{icon}</div>
      <div className="text-center">
        <div className="mb-1 font-semibold text-gray-100">{title}</div>
        <div className="text-sm text-gray-400">{description}</div>
      </div>
    </button>
  );
}
