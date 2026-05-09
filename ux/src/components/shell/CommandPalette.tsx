import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { Search } from "lucide-react";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useKeyboardShortcut } from "@/hooks/useKeyboardShortcut";

export function CommandPalette() {
  const { open, actions, closePalette, togglePalette } = useCommandPaletteStore();
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const activeItemRef = useRef<HTMLButtonElement>(null);

  useKeyboardShortcut({ key: "k", modifiers: ["meta"], onKeydown: togglePalette });
  useKeyboardShortcut({ key: "Escape", onKeydown: closePalette, enabled: open });

  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  useEffect(() => {
    activeItemRef.current?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  const filtered = useMemo(() => {
    if (!query.trim()) return actions;
    const q = query.toLowerCase();
    return actions.filter(
      (a) =>
        a.label.toLowerCase().includes(q) ||
        a.description?.toLowerCase().includes(q)
    );
  }, [query, actions]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && filtered[activeIndex]) {
      e.preventDefault();
      filtered[activeIndex].onSelect();
      closePalette();
    }
  }, [filtered, activeIndex, closePalette]);

  if (!open) return null;

  return (
    <div className="palette-backdrop" onClick={closePalette}>
      <div className="palette" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal aria-label="Command palette" onKeyDown={handleKeyDown}>
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
            filtered.map((action, i) => (
              <button
                key={action.id}
                ref={i === activeIndex ? activeItemRef : undefined}
                className={`palette-item${i === activeIndex ? " active" : ""}`}
                type="button"
                onMouseEnter={() => setActiveIndex(i)}
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
