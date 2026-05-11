import { useState } from "react";
import { Database, FolderOpen, Plus, GitBranch } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useConfig } from "@/api/hooks/admin/useConfig";

interface WorkspaceSwitcherProps {
  onSelect: (path: string) => void;
  isLoading?: boolean;
}

export function WorkspaceSwitcher({ onSelect, isLoading = false }: WorkspaceSwitcherProps) {
  const [showOpenModal, setShowOpenModal] = useState(false);
  const [showNewWorkspaceModal, setShowNewWorkspaceModal] = useState(false);
  const [showCloneModal, setShowCloneModal] = useState(false);
  const [openPath, setOpenPath] = useState("");
  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [gitUrl, setGitUrl] = useState("");

  const { data: config } = useConfig();
  const defaultDbPath = config?.sections?.database?.local_db_path as string | undefined;

  const handleOpenSubmit = () => {
    if (openPath.trim()) {
      onSelect(openPath.trim());
      setOpenPath("");
      setShowOpenModal(false);
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
            {defaultDbPath && (
              <Tile
                testId="workspace-use-default-tile"
                icon={<Database size={32} />}
                title="Use configured workspace"
                description={defaultDbPath}
                onClick={() => onSelect(defaultDbPath)}
                disabled={isDisabled}
                highlight
              />
            )}
            <Tile
              testId="workspace-open-folder-tile"
              icon={<FolderOpen size={32} />}
              title="Open folder…"
              description="Use an existing folder as your workspace"
              onClick={() => setShowOpenModal(true)}
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
        open={showOpenModal}
        onClose={() => {
          setShowOpenModal(false);
          setOpenPath("");
        }}
        title="Open Folder"
        size="sm"
        footer={
          <div className="form-actions">
            <Button
              variant="ghost"
              onClick={() => {
                setShowOpenModal(false);
                setOpenPath("");
              }}
            >
              Cancel
            </Button>
            <Button variant="primary" onClick={handleOpenSubmit} disabled={!openPath.trim()}>
              Open
            </Button>
          </div>
        }
      >
        <div className="form-group">
          <label className="form-group-label">Folder path</label>
          <Input
            type="text"
            placeholder="/path/to/workspace"
            value={openPath}
            onChange={(e) => setOpenPath(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleOpenSubmit();
            }}
            data-testid="workspace-folder-input"
            autoFocus
          />
        </div>
      </Modal>

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
          <div className="form-actions">
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
        <div className="form-group">
          <label className="form-group-label">Folder name</label>
          <Input
            type="text"
            placeholder="my-workspace"
            value={newWorkspaceName}
            onChange={(e) => setNewWorkspaceName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleNewWorkspaceSubmit();
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
          <div className="form-actions">
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
        <div className="form-group">
          <label className="form-group-label">Git repository URL</label>
          <Input
            type="text"
            placeholder="https://github.com/user/repo.git"
            value={gitUrl}
            onChange={(e) => setGitUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleCloneSubmit();
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
  highlight?: boolean;
}

function Tile({
  testId,
  icon,
  title,
  description,
  onClick,
  disabled = false,
  highlight = false,
}: TileProps) {
  return (
    <button
      data-testid={testId}
      onClick={onClick}
      disabled={disabled}
      className={[
        "flex flex-col items-center gap-4 rounded-lg border px-6 py-6 transition-all disabled:cursor-not-allowed disabled:opacity-50",
        highlight
          ? "border-cyan-600 bg-cyan-950 hover:border-cyan-400"
          : "border-gray-700 bg-gray-800 hover:border-cyan-500",
      ].join(" ")}
    >
      <div className={highlight ? "text-cyan-400" : "text-gray-500"}>{icon}</div>
      <div className="text-center">
        <div className="mb-1 font-semibold text-gray-100">{title}</div>
        <div className="text-sm text-gray-400">{description}</div>
      </div>
    </button>
  );
}
