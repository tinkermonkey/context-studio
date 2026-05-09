import { useEffect, useRef, useState, useMemo } from "react";
import { Search } from "lucide-react";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useKeyboardShortcut } from "@/hooks/useKeyboardShortcut";

export function CommandPalette() {
  const { open, actions, closePalette, togglePalette } = useCommandPaletteStore();
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useKeyboardShortcut({ key: "k", modifiers: ["meta"], onKeydown: togglePalette });
  useKeyboardShortcut({ key: "Escape", onKeydown: closePalette, enabled: open });

  useEffect(() => {
    if (open) {
      setQuery("");
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  const filtered = useMemo(() => {
    if (!query.trim()) return actions;
    const q = query.toLowerCase();
    return actions.filter(
      (a) =>
        a.label.toLowerCase().includes(q) ||
        a.description?.toLowerCase().includes(q)
    );
  }, [query, actions]);

  if (!open) return null;

  return (
    <div className="palette-backdrop" onClick={closePalette}>
      <div className="palette" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal aria-label="Command palette">
        <div className="palette-input-row">
          <Search size={18} />
          <input
            ref={inputRef}
            placeholder="Search or run command…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <kbd className="palette-esc" onClick={closePalette}>esc</kbd>
        </div>
        <div className="palette-results">
          {filtered.length === 0 ? (
            <div className="palette-empty">No results for "{query}"</div>
          ) : (
            filtered.map((action) => (
              <button
                key={action.id}
                className="palette-item"
                type="button"
                onClick={() => {
                  action.onSelect();
                  closePalette();
                }}
              >
                {action.icon && <span className="palette-kind">{action.icon}</span>}
                <span className="palette-label">{action.label}</span>
                {action.description && (
                  <span className="palette-hint">{action.description}</span>
                )}
                <span className="palette-arrow">↵</span>
              </button>
            ))
          )}
        </div>
        <div className="palette-foot">
          <span>↑↓ navigate</span>
          <span>↵ open</span>
          <span>esc close</span>
        </div>
      </div>
    </div>
  );
}
