import { useState } from "react";
import { Modal, Button } from "@tinkermonkey/heimdall-ui";
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

/**
 * App-specific confirm dialog that wraps Heimdall Modal and Button with:
 * - Async operation handling with loading states
 * - Error handling via onError callback
 * - Conditional disabling via isLoading/isConfirmDisabled
 * - Ref support for programmatic confirmation
 * - Test ID support for button elements
 */
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
    if (isProcessing || isLoading || isConfirmDisabled) return;
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

  // Use Heimdall Modal and Button but maintain testid contract for existing tests
  return (
    <div data-testid="confirm-dialog">
      <Modal isOpen={open} onClose={isCancelDisabled ? () => {} : onClose} title={title}>
        <div style={{ marginBottom: "var(--space-4)" }}>{message}</div>
        <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={isCancelDisabled}
            data-testid="confirm-dialog-cancel"
          >
            {cancelLabel}
          </Button>
          <Button
            variant={danger ? "danger" : "primary"}
            onClick={handleConfirm}
            disabled={isConfirmDisabledState}
            data-testid="confirm-dialog-confirm"
          >
            {confirmLabel}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
