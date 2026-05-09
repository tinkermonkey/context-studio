import { type ReactNode } from "react";
import { X, Loader, CheckCircle, AlertCircle } from "lucide-react";
import { useKeyboardShortcut } from "@/hooks/useKeyboardShortcut";
import { Button } from "./Button";

type AutosaveState = "idle" | "saving" | "saved" | "error";

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  autosaveState?: AutosaveState;
  isDirty?: boolean;
  onRevert?: () => void;
  onDelete?: () => void;
  lastSavedAt?: Date;
  headerAction?: ReactNode;
}

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

export function Drawer({
  open,
  onClose,
  title,
  children,
  autosaveState,
  isDirty,
  onRevert,
  onDelete,
  lastSavedAt,
  headerAction,
}: DrawerProps) {
  useKeyboardShortcut({ key: "Escape", onKeydown: onClose, enabled: open });

  if (!open) return null;

  return (
    <aside className="drawer">
      <div className="drawer-head">
        <span className="title">{title}</span>
        <div className="drawer-actions">
          {headerAction}
          {autosaveState && autosaveState !== "idle" && (
            <div className="drawer-autosave-status" data-testid="drawer-autosave-status">
              {autosaveState === "saving" && (
                <>
                  <Loader size={14} className="spin" />
                  <span className="autosave-label">Saving…</span>
                </>
              )}
              {autosaveState === "saved" && lastSavedAt && (
                <>
                  <CheckCircle size={14} className="autosave-icon-saved" />
                  <span className="autosave-label">Saved {formatTimeAgo(lastSavedAt)}</span>
                </>
              )}
              {autosaveState === "error" && (
                <>
                  <AlertCircle size={14} className="autosave-icon-error" />
                  <span className="autosave-label">Save failed</span>
                </>
              )}
            </div>
          )}
          {isDirty && onRevert && (
            <Button variant="ghost" size="sm" onClick={onRevert} data-testid="drawer-revert-button">
              Revert
            </Button>
          )}
          {onDelete && (
            <Button
              variant="danger"
              size="sm"
              onClick={onDelete}
              data-testid="drawer-delete-button"
            >
              Delete
            </Button>
          )}
          <button className="modal-x" onClick={onClose} type="button" aria-label="Close drawer">
            <X size={14} />
          </button>
        </div>
      </div>
      <div className="drawer-body">{children}</div>
    </aside>
  );
}
