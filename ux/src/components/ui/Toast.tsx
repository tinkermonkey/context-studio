import { useState, useCallback, createContext, useContext, ReactNode } from "react";
import { CheckCircle, AlertCircle, AlertTriangle, Info, X } from "lucide-react";
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
  const iconMap = {
    success: <CheckCircle size={13} />,
    error: <AlertCircle size={13} />,
    warning: <AlertTriangle size={13} />,
    info: <Info size={13} />,
  };

  return (
    <div className={`toast toast-${item.type}`}>
      <div className="toast-mark">{iconMap[item.type]}</div>
      <div className="toast-body">
        <div className="toast-title">{item.title}</div>
        {item.sub && <div className="toast-sub">{item.sub}</div>}
      </div>
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
      <button
        className="toast-x"
        onClick={() => onDismiss(item.id)}
        type="button"
        aria-label="Dismiss"
      >
        <X size={12} />
      </button>
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
