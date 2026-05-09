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
  const isConfirmed = input === confirmText;

  const handleConfirm = async () => {
    if (isConfirmed) {
      try {
        await onConfirm();
        setInput("");
        onClose();
      } catch {
        // Error is handled by the consumer's error handling
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && isConfirmed) {
      handleConfirm();
    }
  };

  const handleClose = () => {
    setInput("");
    onClose();
  };

  const footer = (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <span style={{ flex: 1 }} />
      <Button
        variant="ghost"
        size="sm"
        onClick={handleClose}
        disabled={isLoading}
        data-testid="type-confirm-cancel"
      >
        Cancel
      </Button>
      <Button
        variant="danger"
        size="sm"
        onClick={handleConfirm}
        disabled={!isConfirmed || isLoading}
        data-testid="type-confirm-button"
      >
        {confirmLabel}
      </Button>
    </div>
  );

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={title}
      size="sm"
      footer={footer}
    >
      <div
        style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}
        data-testid="type-confirm-dialog"
      >
        <div style={{ color: "var(--canvas-fg-2)", lineHeight: 1.5 }}>
          {message}
        </div>
        <div
          style={{
            fontFamily: "var(--mono)",
            background: "var(--canvas-bg-2)",
            padding: "var(--space-2) var(--space-3)",
            borderRadius: "var(--radius-sm)",
            fontSize: "12px",
            color: "var(--canvas-fg)",
            wordBreak: "break-all",
            marginTop: "var(--space-2)",
          }}
        >
          {confirmText}
        </div>
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
