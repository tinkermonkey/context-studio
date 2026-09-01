interface FilterDropdownContextValue {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "checkbox" | "radio";
  selectedValues: Set<string>;
  onValueChange: (value: string, selected: boolean) => void;
  focusedValue: string | null;
  setFocusedValue: (value: string | null) => void;
  triggerRef: React.RefObject<HTMLButtonElement>;
  panelRef: React.RefObject<HTMLDivElement>;
  placement: DropdownPlacement;
}

const FilterDropdownContext = createContext<FilterDropdownContextValue | undefined>(undefined);

function useFilterDropdown() {
  const context = useContext(FilterDropdownContext);
  if (!context) {
    throw new Error("FilterDropdown components must be used within FilterDropdown");
  }
  return context;
}

interface FilterDropdownProps {
  mode?: "checkbox" | "radio";
  children: ReactNode;
  onChange?: (selectedValues: string[]) => void;
  className?: string;
  defaultValue?: string[];
  value?: string[];
  /** Where the dropdown panel opens relative to the trigger. */
  placement?: DropdownPlacement;
}

const FilterDropdownComponent = React.forwardRef<HTMLDivElement, FilterDropdownProps>(
  (
    {
      mode = "checkbox",
      children,
      onChange,
      className = "",
      defaultValue,
      value,
      placement = "bottom-start",
    },
    ref,
  ) => {
    const [isOpen, setIsOpen] = useState(false);
    const isControlled = value !== undefined;
    const [internalValues, setInternalValues] = useState<Set<string>>(new Set(defaultValue ?? []));
    const selectedValues = isControlled ? new Set(value) : internalValues;
    const triggerRef = useRef<HTMLButtonElement>(null);
    const panelRef = useRef<HTMLDivElement>(null);
    const rootRef = useRef<HTMLDivElement>(null);

    const handleClose = useCallback(() => setIsOpen(false), []);

    const { focusedValue, setFocusedValue } = useDropdownMenu({
      triggerRef,
      panelRef,
      isOpen,
      onClose: handleClose,
    });

    const handleOpenChange = useCallback((open: boolean) => {
      setIsOpen(open);
    }, []);

    const handleValueChange = useCallback(
      (itemValue: string, selected: boolean) => {
        const nextValues = new Set(selectedValues);

        if (selected) {
          if (mode === "radio") nextValues.clear();
          nextValues.add(itemValue);
        } else {
          nextValues.delete(itemValue);
        }

        if (!isControlled) setInternalValues(nextValues);
        onChange?.(Array.from(nextValues));

        if (mode === "radio" && selected) setIsOpen(false);
      },
      [selectedValues, mode, onChange, isControlled],
    );

    const contextValue: FilterDropdownContextValue = {
      isOpen,
      onOpenChange: handleOpenChange,
      mode,
      selectedValues,
      onValueChange: handleValueChange,
      focusedValue,
      setFocusedValue,
      triggerRef,
      panelRef,
      placement,
    };

    return (
      <FilterDropdownContext.Provider value={contextValue}>
        <div
          ref={(node) => {
            (rootRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
            if (typeof ref === "function") ref(node);
            else if (ref) (ref as React.MutableRefObject<HTMLDivElement | null>).current = node;
          }}
          className={`filter-dropdown ${className}`.trim()}
        >
          {children}
        </div>
      </FilterDropdownContext.Provider>
    );
  },
);

FilterDropdownComponent.displayName = "FilterDropdown";

interface FilterDropdownTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  summary: ReactNode;
}

function FilterDropdownTrigger({ label, summary, ...props }: FilterDropdownTriggerProps) {
  const { isOpen, onOpenChange, triggerRef, mode } = useFilterDropdown();

  return (
    <button
      ref={triggerRef}
      type="button"
      {...props}
      className="filter-dropdown__trigger"
      onClick={() => onOpenChange(!isOpen)}
      aria-haspopup={mode === "radio" ? "dialog" : "listbox"}
      aria-expanded={isOpen}
    >
      <span className="filter-dropdown__label">{label}</span>
      <span className="filter-dropdown__summary">{summary}</span>
      <Icon
        name="chevronDown"
        size={14}
        className={`filter-dropdown__chevron ${isOpen ? "filter-dropdown__chevron--open" : ""}`}
      />
    </button>
  );
}

interface FilterDropdownPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

function FilterDropdownPanel({
  children,
  className = "",
  style,
  ...restProps
}: FilterDropdownPanelProps) {
  const { isOpen, mode, panelRef, placement } = useFilterDropdown();

  return (
    <div
      ref={panelRef}
      className={`dropdown-panel ${dropdownPlacementClass(placement)} filter-dropdown__panel ${className}`.trim()}
      role={mode === "checkbox" ? "listbox" : "radiogroup"}
      aria-multiselectable={mode === "checkbox" ? true : undefined}
      hidden={!isOpen}
      style={isOpen ? style : undefined}
      {...restProps}
    >
      {children}
    </div>
  );
}

interface FilterDropdownSectionProps {
  title?: string;
  children: ReactNode;
}

function FilterDropdownSection({ title, children }: FilterDropdownSectionProps) {
  return (
    <div className="dropdown-section">
      {title && <div className="dropdown-section-title">{title}</div>}
      <div className="filter-dropdown__section-content">{children}</div>
    </div>
  );
}

interface FilterDropdownCheckboxProps {
  value: string;
  label: ReactNode;
  description?: ReactNode;
}

function FilterDropdownCheckbox({ value, label, description }: FilterDropdownCheckboxProps) {
  const { selectedValues, onValueChange, focusedValue, setFocusedValue, mode } =
    useFilterDropdown();
  const rowRef = useRef<HTMLButtonElement>(null);

  const isSelected = selectedValues.has(value);
  const isFocused = focusedValue === value;

  useEffect(() => {
    if (isFocused) rowRef.current?.focus();
  }, [isFocused]);

  return (
    <button
      ref={rowRef}
      type="button"
      role={mode === "checkbox" ? "option" : undefined}
      aria-selected={isSelected}
      tabIndex={isFocused ? 0 : -1}
      data-dropdown-item={value}
      onClick={() => onValueChange(value, !isSelected)}
      onMouseEnter={() => setFocusedValue(value)}
      className={["dropdown-item", isFocused && "dropdown-item--focused"].filter(Boolean).join(" ")}
    >
      <span className="dropdown-item__leading">
        <input
          type="checkbox"
          className="dropdown-item__checkbox"
          checked={isSelected}
          readOnly
          tabIndex={-1}
          aria-hidden="true"
        />
      </span>
      <span className="dropdown-item__body">
        <span className="dropdown-item__label">{label}</span>
        {description && <span className="dropdown-item__description">{description}</span>}
      </span>
    </button>
  );
}

interface FilterDropdownRadioProps {
  value: string;
  label: ReactNode;
  description?: ReactNode;
}

function FilterDropdownRadio({ value, label, description }: FilterDropdownRadioProps) {
  const { selectedValues, onValueChange, focusedValue, setFocusedValue } = useFilterDropdown();
  const rowRef = useRef<HTMLButtonElement>(null);

  const isSelected = selectedValues.has(value);
  const isFocused = focusedValue === value;

  useEffect(() => {
    if (isFocused) rowRef.current?.focus();
  }, [isFocused]);

  return (
    <button
      ref={rowRef}
      type="button"
      role="radio"
      aria-checked={isSelected}
      tabIndex={isFocused ? 0 : -1}
      data-dropdown-item={value}
      onClick={() => onValueChange(value, true)}
      onMouseEnter={() => setFocusedValue(value)}
      className={["dropdown-item", isFocused && "dropdown-item--focused"].filter(Boolean).join(" ")}
    >
      <span className="dropdown-item__leading">
        <input
          type="radio"
          className="dropdown-item__radio"
          checked={isSelected}
          readOnly
          tabIndex={-1}
          aria-hidden="true"
        />
      </span>
      <span className="dropdown-item__body">
        <span className="dropdown-item__label">{label}</span>
        {description && <span className="dropdown-item__description">{description}</span>}
      </span>
    </button>
  );
}

interface FilterDropdownComponentType extends React.ForwardRefExoticComponent<
  FilterDropdownProps & React.RefAttributes<HTMLDivElement>
> {
  Trigger: typeof FilterDropdownTrigger;
  Panel: typeof FilterDropdownPanel;
  Section: typeof FilterDropdownSection;
  Checkbox: typeof FilterDropdownCheckbox;
  Radio: typeof FilterDropdownRadio;
}

const FilterDropdown = Object.assign(FilterDropdownComponent, {
  Trigger: FilterDropdownTrigger,
  Panel: FilterDropdownPanel,
  Section: FilterDropdownSection,
  Checkbox: FilterDropdownCheckbox,
  Radio: FilterDropdownRadio,
}) as FilterDropdownComponentType;

// --- Babel-standalone: expose runtime values to window ---
window.FilterDropdown = FilterDropdown;
