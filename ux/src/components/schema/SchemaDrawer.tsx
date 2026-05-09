import { ReactNode } from "react";
import { Drawer as BaseDrawer } from "@/components/ui/Drawer";

interface SchemaDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  autosaveState?: "idle" | "saving" | "saved" | "error";
  isDirty?: boolean;
  lastSavedAt?: Date;
  onRevert?: () => void;
  onDelete?: () => void;
  children: ReactNode;
}

export function SchemaDrawer({
  open,
  onClose,
  title,
  autosaveState,
  isDirty,
  lastSavedAt,
  onRevert,
  onDelete,
  children,
}: SchemaDrawerProps) {
  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={title}
      autosaveState={autosaveState}
      isDirty={isDirty}
      lastSavedAt={lastSavedAt}
      onRevert={onRevert}
      onDelete={onDelete}
    >
      {children}
    </BaseDrawer>
  );
}
