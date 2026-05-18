import { useState, useCallback, createContext, useContext, ReactNode } from "react";
import { Toast as HeimdallToast, type ToastVariant } from "@tinkermonkey/heimdall-ui";
import { Button } from "./Button";

type ToastType = "success" | "error" | "warning" | "info";

interface ToastItem {
  id: string;
  type: ToastType;
  title: string;
  sub?: string;
  action?: {
    label: string;
    onAction: () => void;
  };
}

interface ToastContextType {
  toasts: ToastItem[];
  dismiss: (id: string) => void;
  toast: (
    type: ToastType,
    title: string,
    sub?: string,
    options?: { action?: ToastItem["action"]; autoDismissMs?: number },
  ) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

interface ToastProviderProps {
  children: ReactNode;
}

export function ToastProvider({ children }: ToastProviderProps) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (
      type: ToastType,
      title: string,
      sub?: string,
      options?: { action?: ToastItem["action"]; autoDismissMs?: number },
    ) => {
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev, { id, type, title, sub, action: options?.action }]);
      const dismissDelay = options?.autoDismissMs ?? 8000;
      setTimeout(() => dismiss(id), dismissDelay);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ toasts, dismiss, toast }}>{children}</ToastContext.Provider>
  );
}

interface ToastProps {
  item: ToastItem;
  onDismiss: (id: string) => void;
}

function Toast({ item, onDismiss }: ToastProps) {
  return (
    <div data-testid={`toast-${item.id}`} className="toast-wrapper">
      <HeimdallToast
        isOpen={true}
        onClose={() => onDismiss(item.id)}
        title={item.title}
        subtitle={item.sub}
        variant={item.type as ToastVariant}
        duration={0}
        data-testid={`toast-content-${item.id}`}
      />
      {item.action && (
        <Button
          variant="ghost"
          size="sm"
          onClick={item.action.onAction}
          data-testid={`toast-action-${item.id}`}
        >
          {item.action.label}
        </Button>
      )}
    </div>
  );
}

interface ToastViewportProps {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}

export function ToastViewport({ toasts, onDismiss }: ToastViewportProps) {
  return (
    <div className="toast-viewport">
      {toasts.map((t) => (
        <Toast key={t.id} item={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

export function useToasts(): ToastContextType {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToasts must be used within a ToastProvider");
  }
  return context;
}

export type { ToastItem };
