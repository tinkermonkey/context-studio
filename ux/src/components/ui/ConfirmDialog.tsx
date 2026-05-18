import { useState } from "react";
import { Modal as HeimdallModal } from "@tinkermonkey/heimdall-ui";
import { Button } from "./Button";
import type { ReactNode } from "react";

interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  message: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void | Promise<void>;
  onError?: (error: Error) => void;
  isLoading?: boolean;
  isConfirmDisabled?: boolean;
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
  onError,
  isLoading = false,
  isConfirmDisabled = false,
}: ConfirmDialogProps) {
  const [isProcessing, setIsProcessing] = useState(false);

  const handleConfirm = async () => {
    setIsProcessing(true);
    try {
      await onConfirm();
      onClose();
    } catch (error) {
      if (onError) {
        onError(error instanceof Error ? error : new Error(String(error)));
      }
    } finally {
      setIsProcessing(false);
    }
  };

  const isConfirmDisabledState = isProcessing || isLoading || isConfirmDisabled;
  const isCancelDisabled = isProcessing || isLoading;

  const footer = (
    <div className="confirm-dialog__footer">
      <Button
        variant="ghost"
        size="sm"
        onClick={onClose}
        disabled={isCancelDisabled}
        data-testid="confirm-dialog-cancel"
      >
        {cancelLabel}
      </Button>
      <Button
        variant={danger ? "danger" : "primary"}
        size="sm"
        onClick={handleConfirm}
        disabled={isConfirmDisabledState}
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
