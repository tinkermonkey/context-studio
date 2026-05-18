import { useState } from "react";
import { Modal as HeimdallModal } from "@tinkermonkey/heimdall-ui";
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
  const [isProcessing, setIsProcessing] = useState(false);

  const handleConfirm = async () => {
    setIsProcessing(true);
    try {
      await onConfirm();
      onClose();
    } catch {
      // Error is handled by the consumer's error handling
    } finally {
      setIsProcessing(false);
    }
  };

  const isDisabled = isProcessing || isLoading;

  const footer = (
    <div className="confirm-dialog__footer">
      <Button
        variant="ghost"
        size="sm"
        onClick={onClose}
        disabled={isDisabled}
        data-testid="confirm-dialog-cancel"
      >
        {cancelLabel}
      </Button>
      <Button
        variant={danger ? "danger" : "primary"}
        size="sm"
        onClick={handleConfirm}
        disabled={isDisabled}
        data-testid="confirm-dialog-confirm"
      >
        {confirmLabel}
      </Button>
    </div>
  );

  return (
    <HeimdallModal isOpen={open} onClose={onClose} title={title}>
      <div className="confirm-dialog__message" data-testid="confirm-dialog">
        {message}
      </div>
      {footer}
    </HeimdallModal>
  );
}
