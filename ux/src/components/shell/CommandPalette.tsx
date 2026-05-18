import { useEffect, useState, useMemo, useRef } from "react";
import { CommandPalette as HeimdallCommandPalette, type Command } from "@tinkermonkey/heimdall-ui";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useKeyboardShortcut } from "@/hooks/useKeyboardShortcut";

export function CommandPalette() {
  const { open, actions, closePalette, togglePalette } = useCommandPaletteStore();
  const [query, setQuery] = useState("");
  const paletteRef = useRef<HTMLDivElement>(null);

  useKeyboardShortcut({ key: "k", modifiers: ["meta"], onKeydown: togglePalette });
  useKeyboardShortcut({ key: "Escape", onKeydown: closePalette, enabled: open });

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

  useEffect(() => {
    if (open) {
      setQuery("");
      instrumentCommandPalette();
    }
  }, [open, commands]);

  const instrumentCommandPalette = () => {
    if (!paletteRef.current) return;
    const root = paletteRef.current;

    root.setAttribute("data-testid", "command-palette");

    const backdrop = root.querySelector("[role='dialog']") as HTMLElement;
    if (backdrop) {
      backdrop.setAttribute("data-testid", "command-palette-backdrop");
    }

    const input = root.querySelector("input") as HTMLInputElement;
    if (input) {
      input.setAttribute("data-testid", "command-palette-input");
    }

    const results = root.querySelector("[role='listbox']") as HTMLElement;
    if (results) {
      results.setAttribute("data-testid", "command-palette-results");
    }

    const empty = root.querySelector("[role='status']") as HTMLElement;
    if (empty) {
      empty.setAttribute("data-testid", "command-palette-empty-state");
    }

    const escButton = root.querySelector("button[title*='Esc'], button[title*='esc']") as HTMLElement;
    if (escButton) {
      escButton.setAttribute("data-testid", "command-palette-esc-button");
    }

    const items = root.querySelectorAll("[role='option']");
    items.forEach((item, index) => {
      const actionId = commands[index]?.id || `item-${index}`;
      item.setAttribute("data-testid", `command-palette-item-${actionId}`);
    });
  };

  return (
    <div ref={paletteRef}>
      <HeimdallCommandPalette
        isOpen={open}
        onClose={closePalette}
        commands={commands}
        placeholder="Search or run command…"
      />
    </div>
  );
}
