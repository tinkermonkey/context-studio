import { useMemo } from "react";
import { CommandPalette as HeimdallCommandPalette, type Command } from "@tinkermonkey/heimdall-ui";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useKeyboardShortcut } from "@/hooks/useKeyboardShortcut";

export function CommandPalette() {
  const { open, query, actions, closePalette, togglePalette } = useCommandPaletteStore();

  useKeyboardShortcut({ key: "k", modifiers: ["meta"], onKeydown: togglePalette });
  useKeyboardShortcut({ key: "Escape", onKeydown: closePalette, enabled: open });

  const filtered = useMemo(() => {
    if (!query.trim()) return actions;
    const q = query.toLowerCase();
    return actions.filter(
      (a) => a.label.toLowerCase().includes(q) || a.description?.toLowerCase().includes(q),
    );
  }, [query, actions]);

  const commands: Command[] = useMemo(
    () =>
      filtered.map((action) => ({
        id: action.id,
        label: action.label,
        description: action.description,
        icon: action.icon,
        onSelect: () => {
          action.onSelect();
          closePalette();
        },
      })),
    [filtered, closePalette],
  );

  return (
    <div data-testid="command-palette">
      <HeimdallCommandPalette
        isOpen={open}
        onClose={closePalette}
        commands={commands}
        placeholder="Search or run command…"
      />
    </div>
  );
}
