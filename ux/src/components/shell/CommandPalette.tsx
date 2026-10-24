import { useMemo } from "react";
import { CommandPalette as HeimdallCommandPalette, type Command } from "@tinkermonkey/heimdall-ui";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useKeyboardShortcut } from "@/hooks/useKeyboardShortcut";

export function CommandPalette() {
  const { open, query, actions, closePalette, togglePalette, setQuery } = useCommandPaletteStore();

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
    // Heimdall's palette owns its input and exposes no query callback; capture
    // the bubbling change event so entity actions can be searched server-side.
    <div
      data-testid="command-palette"
      onChange={(e) => {
        const target = e.target as HTMLElement;
        if (target instanceof HTMLInputElement) setQuery(target.value);
      }}
    >
      <HeimdallCommandPalette
        isOpen={open}
        onClose={closePalette}
        commands={commands}
        placeholder="Search or run command…"
      />
    </div>
  );
}
