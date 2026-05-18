import { Modal as HeimdallModal } from "@tinkermonkey/heimdall-ui";
import type { ReactNode } from "react";

type ModalSize = "sm" | "md" | "lg";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  subtitle?: string;
  size?: ModalSize;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  testId?: string;
}

export function Modal({
  open,
  size,
  className = "",
  title,
  subtitle,
  onClose,
  children,
  footer,
  testId,
}: ModalProps) {
  const sizeClass = size ? `modal-${size}` : "modal-md";
  const combinedClassName = [sizeClass, className].filter(Boolean).join(" ");

  // Convert title to string for Heimdall, or render as ReactNode in children
  const titleString = typeof title === "string" ? title : undefined;

  return (
    <HeimdallModal
      isOpen={open}
      onClose={onClose}
      title={titleString}
      subtitle={subtitle}
      className={combinedClassName}
      data-testid={testId}
    >
      {typeof title !== "string" && title ? (
        <>
          <div className="mb-sm">{title}</div>
          {children}
        </>
      ) : (
        children
      )}
      {footer && <div className="modal__footer">{footer}</div>}
    </HeimdallModal>
  );
}

export default Modal;
