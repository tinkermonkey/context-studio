import { ReactNode } from "react";
import { Modal } from "./Modal";
import { Button } from "./Button";

interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void | Promise<void>;
  isLoading?: boolean;
}

export function ConfirmDialog({
  open,
  onClose,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
  onConfirm,
  isLoading = false,
}: ConfirmDialogProps) {
  const handleConfirm = async () => {
    await onConfirm();
    onClose();
  };

  const footer = (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <span style={{ flex: 1 }} />
      <Button
        variant="ghost"
        size="sm"
        onClick={onClose}
        disabled={isLoading}
        data-testid="confirm-dialog-cancel"
      >
        {cancelLabel}
      </Button>
      <Button
        variant={danger ? "danger" : "primary"}
        size="sm"
        onClick={handleConfirm}
        disabled={isLoading}
        data-testid="confirm-dialog-confirm"
      >
        {confirmLabel}
      </Button>
    </div>
  );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="sm"
      footer={footer}
    >
      <div style={{ color: "var(--canvas-fg-2)", lineHeight: 1.5 }} data-testid="confirm-dialog">
        {message}
      </div>
    </Modal>
  );
}
