import { type ReactNode, useRef, useEffect } from "react";
import { Loader, CheckCircle, AlertCircle, X } from "lucide-react";
import { useFocusTrap } from "@tinkermonkey/heimdall-ui";
import { useBodyOverflow } from "@tinkermonkey/heimdall-ui";
import { formatTimeAgo } from "@/utils/dateFormatting";
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
  const drawerRef = useRef<HTMLDivElement>(null);

  useFocusTrap(drawerRef, open);
  useBodyOverflow(open);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        onClose();
      }
    };

    if (open) {
      document.addEventListener("keydown", handleEscape);
      return () => {
        document.removeEventListener("keydown", handleEscape);
      };
    }
  }, [open, onClose]);

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const hasAutosaveStatus = autosaveState && autosaveState !== "idle";
  const hasRevert = isDirty && onRevert;
  const hasDelete = onDelete;
  const hasActions = headerAction || hasAutosaveStatus || hasRevert || hasDelete;

  if (!open) return null;

  return (
    <div className="drawer-backdrop" onClick={handleBackdropClick}>
      <div
        ref={drawerRef}
        className="drawer drawer--right"
        role="dialog"
        aria-modal="true"
      >
        <div className="drawer-head">
          <div className="title">{title}</div>
          <div className="drawer-actions">
            {headerAction}
            {hasAutosaveStatus && (
              <div
                className="drawer-autosave-status"
                data-testid="drawer-autosave-status"
              >
                {autosaveState === "saving" && (
                  <>
                    <Loader size={14} className="spin" />
                    <span className="autosave-label">Saving…</span>
                  </>
                )}
                {autosaveState === "saved" && lastSavedAt && (
                  <>
                    <CheckCircle size={14} className="autosave-icon-saved" />
                    <span className="autosave-label">
                      Saved {formatTimeAgo(lastSavedAt)}
                    </span>
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
            {hasRevert && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onRevert}
                data-testid="drawer-revert-button"
              >
                Revert
              </Button>
            )}
            {hasDelete && (
              <Button
                variant="danger"
                size="sm"
                onClick={onDelete}
                data-testid="drawer-delete-button"
              >
                Delete
              </Button>
            )}
          </div>
          <button className="drawer-close" onClick={onClose} aria-label="Close drawer">
            <X size={14} />
          </button>
        </div>
        <div className="drawer-body">{children}</div>
      </div>
    </div>
  );
}
