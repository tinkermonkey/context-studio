import { type ReactNode, useEffect } from "react";
import { X } from "lucide-react";
import { useKeyboardShortcut } from "@/hooks/useKeyboardShortcut";

type ModalSize = "sm" | "md" | "lg";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: string;
  size?: ModalSize;
  children: ReactNode;
  footer?: ReactNode;
}

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  size = "md",
  children,
  footer,
}: ModalProps) {
  useKeyboardShortcut({ key: "Escape", onKeydown: onClose, enabled: open });

  useEffect(() => {
    if (open) document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className={`modal modal-${size}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal
      >
        <div className="modal-head">
          <div className="modal-head-text">
            <div className="modal-title">{title}</div>
            {subtitle && <div className="modal-sub">{subtitle}</div>}
          </div>
          <button className="modal-x" onClick={onClose} type="button" aria-label="Close">
            <X size={14} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}
