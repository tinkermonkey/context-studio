import { type ReactNode } from "react";
import { Loader, AlertCircle } from "lucide-react";
import { InspectorPanel, Button, Icon, RowMenu } from "@tinkermonkey/heimdall-ui";
import type { RowMenuAction } from "@tinkermonkey/heimdall-ui";
import { formatTimeAgo } from "@/utils/dateFormatting";

export type InlineInspectorMode = "view" | "edit";

interface InlineInspectorProps {
  eyebrow: string;
  title: string;
  id?: string;
  version?: number;
  mode: InlineInspectorMode;
  onEdit: () => void;
  onDone: () => void;
  onDelete: () => void;
  onDuplicate?: () => void;
  autosaveStatus?: "saving" | "saved" | "error";
  lastSavedAt?: Date | null;
  editNote?: string | false;
  extraViewActions?: ReactNode;
  children: ReactNode;
  "data-testid"?: string;
}

export function InlineInspector({
  eyebrow,
  title,
  id,
  version,
  mode,
  onEdit,
  onDone,
  onDelete,
  onDuplicate,
  autosaveStatus,
  lastSavedAt,
  editNote = "Editing — fields save automatically",
  extraViewActions,
  children,
  "data-testid": testId,
}: InlineInspectorProps) {
  const menuActions: RowMenuAction[] = [
    { id: "edit", label: "Edit", icon: "edit" },
    ...(onDuplicate ? [{ id: "duplicate", label: "Duplicate", icon: "copy" as const }] : []),
    { type: "separator" as const },
    { id: "delete", label: "Delete", icon: "trash", danger: true },
  ];

  const handleMenuAction = (actionId: string) => {
    if (actionId === "edit") onEdit();
    else if (actionId === "duplicate") onDuplicate?.();
    else if (actionId === "delete") onDelete();
  };

  const viewActions = (
    <>
      {extraViewActions}
      <Button
        variant="ghost"
        size="sm"
        icon
        onClick={onEdit}
        aria-label="Edit"
        data-testid="inline-inspector-edit-button"
      >
        <Icon name="edit" size={13} />
      </Button>
      <RowMenu
        actions={menuActions}
        onAction={handleMenuAction}
        triggerLabel="Entity actions"
        data-testid="inline-inspector-row-menu"
      />
    </>
  );

  const editActions = (
    <>
      <span className="drawer-autosave-status" data-testid="inspector-autosave-status">
        {autosaveStatus === "saving" && <Loader size={14} className="spin" />}
        {autosaveStatus === "saved" && lastSavedAt && (
          <span className="autosave-icon-saved">Saved {formatTimeAgo(lastSavedAt)}</span>
        )}
        {autosaveStatus === "error" && <AlertCircle size={14} className="autosave-icon-error" />}
      </span>
      <Button variant="ghost" size="sm" onClick={onDone} data-testid="inline-inspector-done-button">
        Done
      </Button>
    </>
  );

  return (
    <div className="inline-inspector" data-testid={testId}>
      {mode === "edit" && editNote !== false && (
        <div className="inline-inspector__editing-note" role="note">
          {editNote}
        </div>
      )}
      <InspectorPanel
        eyebrow={eyebrow}
        title={title}
        id={id ?? ""}
        version={version}
        actions={mode === "view" ? viewActions : editActions}
      >
        {children}
      </InspectorPanel>
    </div>
  );
}
