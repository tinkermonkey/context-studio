interface UseDropdownMenuOptions {
  triggerRef: React.RefObject<HTMLElement>;
  panelRef: React.RefObject<HTMLElement>;
  isOpen: boolean;
  onClose: () => void;
  itemSelector?: string;
  restoreFocus?: boolean;
}

interface UseDropdownMenuReturn {
  focusedValue: string | null;
  setFocusedValue: (value: string | null) => void;
}

const DEFAULT_ITEM_SELECTOR = "[data-dropdown-item]:not([data-disabled])";

function useDropdownMenu({
  triggerRef,
  panelRef,
  isOpen,
  onClose,
  itemSelector = DEFAULT_ITEM_SELECTOR,
  restoreFocus = true,
}: UseDropdownMenuOptions): UseDropdownMenuReturn {
  const [focusedValue, setFocusedValue] = useState<string | null>(null);
  const wasOpenRef = useRef(false);

  const getItems = useCallback((): string[] => {
    const panel = panelRef.current;
    if (!panel) return [];
    return Array.from(panel.querySelectorAll<HTMLElement>(itemSelector))
      .map((el) => el.getAttribute("data-dropdown-item"))
      .filter((v): v is string => v !== null && v.length > 0);
  }, [panelRef, itemSelector]);

  // Initialize focus on open; restore trigger focus on close.
  useEffect(() => {
    if (isOpen && !wasOpenRef.current) {
      wasOpenRef.current = true;
      const items = getItems();
      setFocusedValue((prev) => (prev && items.includes(prev) ? prev : (items[0] ?? null)));
    } else if (!isOpen && wasOpenRef.current) {
      wasOpenRef.current = false;
      setFocusedValue(null);
      if (restoreFocus) triggerRef.current?.focus();
    }
  }, [isOpen, getItems, restoreFocus, triggerRef]);

  // Outside click + document-level Escape.
  useEffect(() => {
    if (!isOpen) return;

    const handleMouseDown = (e: MouseEvent) => {
      const target = e.target as Node;
      const trigger = triggerRef.current;
      const panel = panelRef.current;
      if (trigger?.contains(target) || panel?.contains(target)) return;
      onClose();
    };

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };

    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen, onClose, triggerRef, panelRef]);

  // Arrow / Tab / Home / End nav — attached to both the trigger and the panel
  // so it works whether focus is on a combobox input (EntityPicker) or on a
  // focused item button (Select, FilterDropdown, RowMenu).
  useEffect(() => {
    if (!isOpen) return;
    const trigger = triggerRef.current;
    const panel = panelRef.current;

    const handleKeyDown = (e: KeyboardEvent) => {
      const items = getItems();
      if (items.length === 0) return;

      const currentIndex = items.indexOf(focusedValue ?? "");
      const lastIndex = items.length - 1;
      const targetIsItem = (e.target as HTMLElement | null)?.hasAttribute("data-dropdown-item");

      switch (e.key) {
        case "ArrowDown": {
          e.preventDefault();
          const next = currentIndex < lastIndex ? currentIndex + 1 : 0;
          setFocusedValue(items[next]);
          break;
        }
        case "ArrowUp": {
          e.preventDefault();
          const next = currentIndex > 0 ? currentIndex - 1 : lastIndex;
          setFocusedValue(items[next]);
          break;
        }
        case "Tab": {
          if (!targetIsItem) return;
          e.preventDefault();
          const delta = e.shiftKey ? -1 : 1;
          const next = (currentIndex + delta + items.length) % items.length;
          setFocusedValue(items[next]);
          break;
        }
        case "Home": {
          e.preventDefault();
          setFocusedValue(items[0]);
          break;
        }
        case "End": {
          e.preventDefault();
          setFocusedValue(items[lastIndex]);
          break;
        }
      }
    };

    trigger?.addEventListener("keydown", handleKeyDown);
    panel?.addEventListener("keydown", handleKeyDown);
    return () => {
      trigger?.removeEventListener("keydown", handleKeyDown);
      panel?.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, focusedValue, getItems, triggerRef, panelRef]);

  return { focusedValue, setFocusedValue };
}

// --- Babel-standalone: expose runtime values to window ---
window.useDropdownMenu = useDropdownMenu;
