import { useEffect, useMemo, useRef } from "react";
import { CommandPalette as HeimdallCommandPalette, type Command } from "@tinkermonkey/heimdall-ui";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useKeyboardShortcut } from "@/hooks/useKeyboardShortcut";

const setNativeInputValue = Object.getOwnPropertyDescriptor(
  HTMLInputElement.prototype,
  "value",
)?.set;

/**
 * Put text into an input that React owns, the way typing would: set the value
 * through the native setter and fire `input`, so the owner's onChange runs.
 */
function typeInto(input: HTMLInputElement, value: string) {
  setNativeInputValue?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.setSelectionRange(value.length, value.length);
}

export function CommandPalette() {
  const { open, query, actions, closePalette, togglePalette, setQuery } = useCommandPaletteStore();
  const containerRef = useRef<HTMLDivElement>(null);

  useKeyboardShortcut({ key: "k", modifiers: ["meta"], onKeydown: togglePalette });
  useKeyboardShortcut({ key: "Escape", onKeydown: closePalette, enabled: open });

  // Heimdall's palette keeps its input value in internal state and takes no
  // initial query. When the store's query is set from outside (text typed in
  // the topbar search), copy it into the palette input so it starts with it.
  useEffect(() => {
    if (!open) return;
    const input = containerRef.current?.querySelector<HTMLInputElement>(
      ".command-palette__input",
    );
    if (input && input.value !== query) typeInto(input, query);
  }, [open, query]);

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
      ref={containerRef}
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
