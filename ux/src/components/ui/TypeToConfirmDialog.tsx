import { useState } from "react";
import { Modal } from "./Modal";
import { Button } from "./Button";
import { Input } from "./Input";

interface TypeToConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  message: string;
  confirmText: string;
  confirmLabel?: string;
  onConfirm: () => void | Promise<void>;
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
  isLoading = false,
}: TypeToConfirmDialogProps) {
  const [input, setInput] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const isConfirmed = input === confirmText;
  const isDisabled = isLoading || isProcessing || !isConfirmed;

  const handleConfirm = async () => {
    if (isConfirmed) {
      setIsProcessing(true);
      try {
        await onConfirm();
        setInput("");
        onClose();
      } catch {
        // Error is handled by the consumer's error handling
      } finally {
        setIsProcessing(false);
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && isConfirmed && !isDisabled) {
      handleConfirm();
    }
  };

  const handleClose = () => {
    setInput("");
    onClose();
  };

  const footer = (
    <div className="flex-between">
      <Button
        variant="ghost"
        size="sm"
        onClick={handleClose}
        disabled={isLoading || isProcessing}
        data-testid="type-confirm-cancel"
      >
        Cancel
      </Button>
      <Button
        variant="danger"
        size="sm"
        onClick={handleConfirm}
        disabled={isDisabled}
        data-testid="type-confirm-button"
      >
        {confirmLabel}
      </Button>
    </div>
  );

  return (
    <Modal open={open} onClose={handleClose} title={title} size="sm" footer={footer}>
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
    </Modal>
  );
}
