import { type ReactNode } from "react";
import { X } from "lucide-react";
import { useKeyboardShortcut } from "@/hooks/useKeyboardShortcut";

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
}

export function Drawer({ open, onClose, title, children }: DrawerProps) {
  useKeyboardShortcut({ key: "Escape", onKeydown: onClose, enabled: open });

  return (
    <aside className={`drawer${open ? " open" : ""}`}>
      <div className="drawer-head">
        <span>{title}</span>
        <button className="modal-x" onClick={onClose} type="button" aria-label="Close drawer">
          <X size={14} />
        </button>
      </div>
      <div className="drawer-body">{children}</div>
    </aside>
  );
}
