import { useState } from "react";
import { Modal, Button, TextInput as Input } from "@tinkermonkey/heimdall-ui";

interface TypeToConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  message: string;
  confirmText: string;
  confirmLabel?: string;
  onConfirm: () => void | Promise<void>;
  onError: (error: Error) => void;
  isLoading?: boolean;
}

export function TypeToConfirmDialog({
  open,
  onClose,
  title,
  message,
  confirmText,
  confirmLabel = "Delete",
  onConfirm,
  onError,
  isLoading = false,
}: TypeToConfirmDialogProps) {
  const [input, setInput] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);

  const isConfirmed = input === confirmText;
  const isDisabled = isProcessing || isLoading || !isConfirmed;

  const handleClose = () => {
    setInput("");
    onClose();
  };

  const handleConfirm = async () => {
    if (isDisabled) return;
    setIsProcessing(true);
    try {
      await onConfirm();
      setInput("");
      onClose();
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      onError(err);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && isConfirmed && !isDisabled) {
      void handleConfirm();
    }
  };

  return (
    <Modal isOpen={open} onClose={isProcessing || isLoading ? () => {} : handleClose} title={title}>
      <div className="stack-lg" data-testid="type-confirm-dialog">
        <div className="type-confirm-message">{message}</div>
        <div className="type-confirm-text">{confirmText}</div>
        <Input
          placeholder="Type the above to confirm"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          data-testid="type-confirm-input"
        />
      </div>
      <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end", marginTop: "var(--space-4)" }}>
        <Button
          variant="ghost"
          onClick={handleClose}
          disabled={isProcessing || isLoading}
          data-testid="type-confirm-cancel"
        >
          Cancel
        </Button>
        <Button
          variant="danger"
          onClick={() => { void handleConfirm(); }}
          disabled={isDisabled}
          data-testid="type-confirm-button"
        >
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
