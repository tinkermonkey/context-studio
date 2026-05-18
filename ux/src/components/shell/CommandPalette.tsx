import { useEffect, useState, useMemo, useCallback } from "react";
import { CommandPalette as HeimdallCommandPalette, type Command } from "@tinkermonkey/heimdall-ui";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useKeyboardShortcut } from "@/hooks/useKeyboardShortcut";

export function CommandPalette() {
  const { open, actions, closePalette, togglePalette } = useCommandPaletteStore();
  const [query, setQuery] = useState("");

  useKeyboardShortcut({ key: "k", modifiers: ["meta"], onKeydown: togglePalette });
  useKeyboardShortcut({ key: "Escape", onKeydown: closePalette, enabled: open });

  useEffect(() => {
    if (open) {
      setQuery("");
    }
  }, [open]);

  const filtered = useMemo(() => {
    if (!query.trim()) return actions;
    const q = query.toLowerCase();
    return actions.filter(
      (a) => a.label.toLowerCase().includes(q) || a.description?.toLowerCase().includes(q),
    );
  }, [query, actions]);

  const commands: Command[] = filtered.map((action) => ({
    id: action.id,
    label: action.label,
    description: action.description,
    icon: action.icon as any,
    onSelect: () => {
      action.onSelect();
      closePalette();
    },
  }));

  return (
    <HeimdallCommandPalette
      isOpen={open}
      onClose={closePalette}
      commands={commands}
      placeholder="Search or run command…"
    />
  );
}
