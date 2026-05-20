import { useRef, useState } from "react";
import { TextInput as Input } from "@tinkermonkey/heimdall-ui";
import { ConfirmDialog } from "./ConfirmDialog";

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
  const confirmButtonRef = useRef<() => Promise<void>>(null);

  const isConfirmed = input === confirmText;

  const handleClose = () => {
    setInput("");
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && isConfirmed && !isLoading) {
      confirmButtonRef.current?.();
    }
  };

  const handleConfirmDialog = async () => {
    if (isConfirmed) {
      await onConfirm();
      setInput("");
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
      onConfirmButtonRef={confirmButtonRef}
      isLoading={isLoading}
      isConfirmDisabled={!isConfirmed}
    />
  );
}
