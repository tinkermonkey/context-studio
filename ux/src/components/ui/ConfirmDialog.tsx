import { useState } from "react";
import { Modal as HeimdallModal, Button as HeimdallButton } from "@tinkermonkey/heimdall-ui";
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
  onError: (error: Error) => void;
  onConfirmButtonRef?: React.MutableRefObject<(() => Promise<void>) | null>;
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
  onConfirmButtonRef,
  isLoading = false,
  isConfirmDisabled = false,
}: ConfirmDialogProps) {
  const [isProcessing, setIsProcessing] = useState(false);

  const handleConfirm = async () => {
    if (isProcessing) return;
    setIsProcessing(true);
    try {
      await onConfirm();
      onClose();
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      onError(err);
    } finally {
      setIsProcessing(false);
    }
  };

  if (onConfirmButtonRef) {
    onConfirmButtonRef.current = handleConfirm;
  }

  const isConfirmDisabledState = isProcessing || isLoading || isConfirmDisabled;
  const isCancelDisabled = isProcessing || isLoading;

  return (
    <HeimdallModal isOpen={open} onClose={onClose} title={title}>
      <div className="confirm-dialog__message" data-testid="confirm-dialog">
        {message}
      </div>
      <div className="confirm-dialog__footer">
        <HeimdallButton
          variant="ghost"
          size="sm"
          onClick={onClose}
          disabled={isCancelDisabled}
          data-testid="confirm-dialog-cancel"
        >
          {cancelLabel}
        </HeimdallButton>
        <HeimdallButton
          variant={danger ? "danger" : "primary"}
          size="sm"
          onClick={handleConfirm}
          disabled={isConfirmDisabledState}
          data-testid="confirm-dialog-confirm"
        >
          {confirmLabel}
        </HeimdallButton>
      </div>
    </HeimdallModal>
  );
}
