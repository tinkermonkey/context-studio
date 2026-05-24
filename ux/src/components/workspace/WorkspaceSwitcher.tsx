import { TextInput as Input, Button, Modal, WorkspaceSwitcherDialog } from "@tinkermonkey/heimdall-ui";
import { useState } from "react";
import { useConfig } from "@/api/hooks/admin/useConfig";
import type { Workspace } from "@tinkermonkey/heimdall-ui";

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

  const currentWorkspace: Workspace | undefined = defaultDbPath
    ? { id: "configured", name: defaultDbPath.split("/").pop() ?? "workspace", path: defaultDbPath }
    : undefined;

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

  return (
    <>
      <WorkspaceSwitcherDialog
        isOpen={true}
        onClose={() => {}}
        current={currentWorkspace}
        recent={currentWorkspace ? [currentWorkspace] : []}
        onPickRecent={(workspace) => {
          if (workspace.path) onSelect(workspace.path);
        }}
        onOpenFolder={() => setShowOpenModal(true)}
        onNewWorkspace={() => setShowNewWorkspaceModal(true)}
        onCloneFromGit={() => setShowCloneModal(true)}
      />

      <Modal
        isOpen={showOpenModal}
        onClose={() => {
          setShowOpenModal(false);
          setOpenPath("");
        }}
        title="Open Folder"
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
            <Button variant="primary" onClick={handleOpenSubmit} disabled={!openPath.trim() || isLoading}>
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
        isOpen={showNewWorkspaceModal}
        onClose={() => {
          setShowNewWorkspaceModal(false);
          setNewWorkspaceName("");
        }}
        title="New Workspace"
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
              disabled={!newWorkspaceName.trim() || isLoading}
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
        isOpen={showCloneModal}
        onClose={() => {
          setShowCloneModal(false);
          setGitUrl("");
        }}
        title="Clone from Git"
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
            <Button variant="primary" onClick={handleCloneSubmit} disabled={!gitUrl.trim() || isLoading}>
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
