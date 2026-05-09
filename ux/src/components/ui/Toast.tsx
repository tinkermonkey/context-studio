import { useState, useCallback } from "react";
import { CheckCircle, AlertCircle, X } from "lucide-react";

type ToastType = "success" | "error";

interface ToastItem {
  id: string;
  type: ToastType;
  title: string;
  sub?: string;
}

interface ToastProps {
  item: ToastItem;
  onDismiss: (id: string) => void;
}

function Toast({ item, onDismiss }: ToastProps) {
  return (
    <div className={`toast toast-${item.type}`}>
      <div className="toast-mark">
        {item.type === "success" ? <CheckCircle size={13} /> : <AlertCircle size={13} />}
      </div>
      <div className="toast-body">
        <div className="toast-title">{item.title}</div>
        {item.sub && <div className="toast-sub">{item.sub}</div>}
      </div>
      <button className="toast-x" onClick={() => onDismiss(item.id)} type="button" aria-label="Dismiss">
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

export function useToasts() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (type: ToastType, title: string, sub?: string) => {
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev, { id, type, title, sub }]);
      setTimeout(() => dismiss(id), 4000);
    },
    [dismiss]
  );

  return { toasts, dismiss, toast };
}

export type { ToastItem };
