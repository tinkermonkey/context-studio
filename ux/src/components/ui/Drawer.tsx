import { type ReactNode } from "react";
import { Loader, CheckCircle, AlertCircle } from "lucide-react";
import { Drawer as HeimdallDrawer } from "@tinkermonkey/heimdall-ui";
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
  const headerActions = (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
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
    </div>
  );

  return (
    <HeimdallDrawer
      isOpen={open}
      onClose={onClose}
      title={typeof title === "string" ? title : undefined}
    >
      {typeof title !== "string" && title ? (
        <>
          <div style={{ marginBottom: "16px" }}>{title}</div>
          {headerActions && <div style={{ marginBottom: "16px" }}>{headerActions}</div>}
          {children}
        </>
      ) : (
        <>
          {headerActions && <div style={{ marginBottom: "16px" }}>{headerActions}</div>}
          {children}
        </>
      )}
    </HeimdallDrawer>
  );
}
