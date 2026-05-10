import { useState, useRef } from "react";
import { FolderOpen, Plus, GitBranch } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

interface WorkspaceSwitcherProps {
  onSelect: (path: string) => void;
  isLoading?: boolean;
}

export function WorkspaceSwitcher({ onSelect, isLoading = false }: WorkspaceSwitcherProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showNewWorkspaceModal, setShowNewWorkspaceModal] = useState(false);
  const [showCloneModal, setShowCloneModal] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [gitUrl, setGitUrl] = useState("");

  const handleOpenFolder = () => {
    fileInputRef.current?.click();
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.currentTarget.files;
    if (files && files.length > 0) {
      const file = files[0];
      const path = file.webkitRelativePath || file.name;
      onSelect(path);
    }
  };

  const handleNewWorkspaceSubmit = () => {
    if (newWorkspaceName.trim()) {
      onSelect(newWorkspaceName);
      setNewWorkspaceName("");
      setShowNewWorkspaceModal(false);
    }
  };

  const handleCloneSubmit = () => {
    if (gitUrl.trim()) {
      onSelect(gitUrl);
      setGitUrl("");
      setShowCloneModal(false);
    }
  };

  const isDisabled = isLoading;

  return (
    <>
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
              onClick={() => setShowNewWorkspaceModal(true)}
              disabled={isDisabled}
            />
            <Tile
              testId="workspace-clone-git-tile"
              icon={<GitBranch size={32} />}
              title="Clone from git…"
              description="Clone a workspace from a git repository"
              onClick={() => setShowCloneModal(true)}
              disabled={isDisabled}
            />
          </div>
        </div>
      </div>

      <Modal
        open={showNewWorkspaceModal}
        onClose={() => {
          setShowNewWorkspaceModal(false);
          setNewWorkspaceName("");
        }}
        title="New Workspace"
        size="sm"
        data-testid="new-workspace-modal"
        footer={
          <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
            <Button
              variant="ghost"
              onClick={() => {
                setShowNewWorkspaceModal(false);
                setNewWorkspaceName("");
              }}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleNewWorkspaceSubmit}
              disabled={!newWorkspaceName.trim()}
            >
              Create
            </Button>
          </div>
        }
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          <label style={{ display: "block", fontSize: "var(--text-sm)" }}>Folder name</label>
          <Input
            type="text"
            placeholder="my-workspace"
            value={newWorkspaceName}
            onChange={(e) => setNewWorkspaceName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleNewWorkspaceSubmit();
              }
            }}
            data-testid="new-workspace-name-input"
            autoFocus
          />
        </div>
      </Modal>

      <Modal
        open={showCloneModal}
        onClose={() => {
          setShowCloneModal(false);
          setGitUrl("");
        }}
        title="Clone from Git"
        size="sm"
        data-testid="clone-git-modal"
        footer={
          <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
            <Button
              variant="ghost"
              onClick={() => {
                setShowCloneModal(false);
                setGitUrl("");
              }}
            >
              Cancel
            </Button>
            <Button variant="primary" onClick={handleCloneSubmit} disabled={!gitUrl.trim()}>
              Clone
            </Button>
          </div>
        }
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          <label style={{ display: "block", fontSize: "var(--text-sm)" }}>Git repository URL</label>
          <Input
            type="text"
            placeholder="https://github.com/user/repo.git"
            value={gitUrl}
            onChange={(e) => setGitUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleCloneSubmit();
              }
            }}
            data-testid="clone-git-url-input"
            autoFocus
          />
        </div>
      </Modal>
    </>
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
