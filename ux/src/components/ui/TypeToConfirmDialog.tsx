import { useState } from "react";
import { ConfirmDialog } from "./ConfirmDialog";
import { Input } from "./Input";

interface TypeToConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  message: string;
  confirmText: string;
  confirmLabel?: string;
  onConfirm: () => void | Promise<void>;
  onError?: (error: Error) => void;
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

  const isConfirmed = input === confirmText;

  const handleClose = () => {
    setInput("");
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && isConfirmed && !isLoading) {
      handleConfirmDialogWithClose();
    }
  };

  const handleConfirmDialog = async () => {
    if (isConfirmed) {
      await onConfirm();
      setInput("");
    }
  };

  const handleConfirmDialogWithClose = async () => {
    try {
      await handleConfirmDialog();
      handleClose();
    } catch (error) {
      if (onError) {
        onError(error instanceof Error ? error : new Error(String(error)));
      }
    }
  };

  return (
    <ConfirmDialog
      open={open}
      onClose={handleClose}
      title={title}
      message={
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
      }
      confirmLabel={confirmLabel}
      danger
      onConfirm={handleConfirmDialog}
      onError={onError}
      isLoading={isLoading}
      isConfirmDisabled={!isConfirmed}
    />
  );
}
