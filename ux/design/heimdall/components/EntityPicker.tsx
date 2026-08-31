interface EntityPickerResult {
  id: string;
  label: string;
  domain?: string;
  domainColor?: StatusColor;
}

interface EntityPickerProps extends Omit<
  React.HTMLAttributes<HTMLDivElement>,
  "onChange" | "onSelect" | "results"
> {
  query: string;
  onQueryChange: (query: string) => void;
  results?: EntityPickerResult[];
  onSelect: (result: EntityPickerResult) => void;
  onClear: () => void;
  placeholder?: string;
  disabled?: boolean;
  inputId?: string;
  /** Where the results panel opens relative to the input. */
  placement?: DropdownPlacement;
}

const EntityPicker = React.forwardRef<HTMLDivElement, EntityPickerProps>(
  (
    {
      query,
      onQueryChange,
      results = [],
      onSelect,
      onClear,
      placeholder = "Search entities...",
      disabled = false,
      inputId,
      placement = "bottom-start",
      className,
      ...props
    },
    ref,
  ) => {
    const [isOpen, setIsOpen] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const panelRef = useRef<HTMLDivElement>(null);
    const listboxId = React.useId();
    const getOptionId = (id: string) => `${listboxId}-option-${id}`;

    const handleClose = useCallback(() => setIsOpen(false), []);

    const { focusedValue, setFocusedValue } = useDropdownMenu({
      triggerRef: inputRef,
      panelRef,
      isOpen,
      onClose: handleClose,
      restoreFocus: false,
    });

    // Seed focus to first result when results change.
    useEffect(() => {
      if (results.length === 0) {
        setFocusedValue(null);
      } else if (!results.some((r) => r.id === focusedValue)) {
        setFocusedValue(results[0].id);
      }
    }, [results, focusedValue, setFocusedValue]);

    // Combobox-specific Enter handling — pick the active result.
    useEffect(() => {
      if (!isOpen) return;
      const handleEnter = (e: KeyboardEvent) => {
        if (e.key !== "Enter") return;
        if (!inputRef.current?.contains(e.target as Node)) return;
        const result = results.find((r) => r.id === focusedValue);
        if (result) {
          e.preventDefault();
          onSelect(result);
          setIsOpen(false);
        }
      };
      document.addEventListener("keydown", handleEnter);
      return () => document.removeEventListener("keydown", handleEnter);
    }, [isOpen, results, focusedValue, onSelect]);

    useImperativeHandle(ref, () => containerRef.current as HTMLDivElement);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (disabled) return;
      onQueryChange(e.target.value);
      setIsOpen(true);
    };

    const handleInputFocus = () => {
      if (disabled) return;
      if (query.length > 0 && results.length > 0) {
        setIsOpen(true);
      }
    };

    const handleClear = () => {
      onClear();
      setIsOpen(false);
      inputRef.current?.focus();
    };

    const handleResultClick = (result: EntityPickerResult) => {
      onSelect(result);
      setIsOpen(false);
    };

    const panelOpen = isOpen && results.length > 0;
    const activeId = panelOpen && focusedValue ? getOptionId(focusedValue) : undefined;

    return (
      <div
        ref={containerRef}
        className={["entity-picker", disabled && "entity-picker--disabled", className]
          .filter(Boolean)
          .join(" ")}
        {...props}
      >
        <div className="entity-picker__input-wrapper">
          <input
            ref={inputRef}
            id={inputId}
            type="text"
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={panelOpen}
            aria-controls={listboxId}
            aria-activedescendant={activeId}
            className="entity-picker__input"
            placeholder={placeholder}
            value={query}
            disabled={disabled}
            onChange={handleInputChange}
            onFocus={handleInputFocus}
            data-testid="entity-picker-input"
          />
          {query && !disabled && (
            <button
              type="button"
              className="entity-picker__clear"
              onClick={handleClear}
              aria-label="Clear search"
              data-testid="entity-picker-clear"
            >
              <Icon name="x" size={16} />
            </button>
          )}
        </div>

        {panelOpen && (
          <div
            ref={panelRef}
            id={listboxId}
            role="listbox"
            className={`dropdown-panel ${dropdownPlacementClass(placement)} entity-picker__dropdown`}
            data-testid="entity-picker-dropdown"
          >
            {results.map((result) => {
              const isFocused = result.id === focusedValue;
              return (
                <div
                  key={result.id}
                  id={getOptionId(result.id)}
                  role="option"
                  aria-selected={isFocused}
                  data-dropdown-item={result.id}
                  className={[
                    "dropdown-item",
                    "entity-picker__result",
                    isFocused && "dropdown-item--focused",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  onMouseEnter={() => setFocusedValue(result.id)}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    handleResultClick(result);
                  }}
                  data-testid={`entity-picker-result-${result.id}`}
                >
                  {result.domain && result.domainColor && (
                    <Chip variant={result.domainColor} className="entity-picker__badge">
                      {result.domain}
                    </Chip>
                  )}
                  <span className="dropdown-item__label entity-picker__label">{result.label}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  },
);

EntityPicker.displayName = "EntityPicker";

// --- Babel-standalone: expose runtime values to window ---
window.EntityPicker = EntityPicker;
