import { useEffect } from "react";

type Modifier = "meta" | "ctrl" | "alt" | "shift";

interface ShortcutOptions {
  key: string;
  modifiers?: Modifier[];
  onKeydown: (e: KeyboardEvent) => void;
  enabled?: boolean;
}

export function useKeyboardShortcut({
  key,
  modifiers = [],
  onKeydown,
  enabled = true,
}: ShortcutOptions) {
  useEffect(() => {
    if (!enabled) return;

    function handler(e: KeyboardEvent) {
      const metaOk = !modifiers.includes("meta") || e.metaKey || e.ctrlKey;
      const ctrlOk = !modifiers.includes("ctrl") || e.ctrlKey;
      const altOk = !modifiers.includes("alt") || e.altKey;
      const shiftOk = !modifiers.includes("shift") || e.shiftKey;

      if (e.key === key && metaOk && ctrlOk && altOk && shiftOk) {
        e.preventDefault();
        onKeydown(e);
      }
    }

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [key, modifiers, onKeydown, enabled]);
}
