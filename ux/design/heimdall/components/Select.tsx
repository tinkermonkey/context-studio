type Mode = "single" | "multi";

interface SelectContextValue {
  mode: Mode;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  selectedValues: Set<string>;
  onValueChange: (value: string) => void;
  focusedValue: string | null;
  setFocusedValue: (value: string | null) => void;
  registerItem: (value: string, label: ReactNode) => () => void;
  panelRef: React.RefObject<HTMLDivElement>;
}

const SelectContext = createContext<SelectContextValue | undefined>(undefined);

function useSelectContext(component: string): SelectContextValue {
  const ctx = useContext(SelectContext);
  if (!ctx) {
    throw new Error(`${component} must be used inside <Select>`);
  }
  return ctx;
}

type SelectSingleProps = {
  multiple?: false;
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  values?: never;
  defaultValues?: never;
  onValuesChange?: never;
};

type SelectMultiProps = {
  multiple: true;
  values?: string[];
  defaultValues?: string[];
  onValuesChange?: (values: string[]) => void;
  value?: never;
  defaultValue?: never;
  onChange?: never;
};

type SelectBaseProps = {
  placeholder?: string;
  error?: boolean;
  disabled?: boolean;
  id?: string;
  name?: string;
  className?: string;
  ariaLabel?: string;
  children: ReactNode;
  "data-testid"?: string;
  /** Where the dropdown panel opens relative to the trigger. */
  placement?: DropdownPlacement;
};

type SelectProps = (SelectSingleProps | SelectMultiProps) & SelectBaseProps;

const SelectComponent = React.forwardRef<HTMLButtonElement, SelectProps>((props, ref) => {
  const {
    placeholder = "Select…",
    error = false,
    disabled = false,
    id,
    name,
    className = "",
    ariaLabel,
    children,
    placement = "bottom-start",
  } = props;
  const dataTestId = props["data-testid"];

  const mode: Mode = props.multiple ? "multi" : "single";

  const isControlledSingle = mode === "single" && props.value !== undefined;
  const isControlledMulti = mode === "multi" && props.values !== undefined;

  const [internalSingle, setInternalSingle] = useState<string>(
    mode === "single" ? (props.defaultValue ?? "") : "",
  );
  const [internalMulti, setInternalMulti] = useState<Set<string>>(
    () => new Set(mode === "multi" ? (props.defaultValues ?? []) : []),
  );

  const selectedValues = useMemo(() => {
    if (mode === "single") {
      const v = isControlledSingle ? (props.value ?? "") : internalSingle;
      return v ? new Set([v]) : new Set<string>();
    }
    return isControlledMulti ? new Set(props.values ?? []) : internalMulti;
  }, [
    mode,
    isControlledSingle,
    isControlledMulti,
    props.value,
    props.values,
    internalSingle,
    internalMulti,
  ]);

  const [isOpen, setIsOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  // Item registry: tracks value -> label so the trigger can render the label.
  const [items, setItems] = useState<Map<string, ReactNode>>(new Map());
  const registerItem = useCallback((value: string, label: ReactNode) => {
    setItems((prev) => {
      if (prev.get(value) === label) return prev;
      const next = new Map(prev);
      next.set(value, label);
      return next;
    });
    return () => {
      setItems((prev) => {
        if (!prev.has(value)) return prev;
        const next = new Map(prev);
        next.delete(value);
        return next;
      });
    };
  }, []);

  const handleOpenChange = useCallback(
    (open: boolean) => {
      if (disabled) return;
      setIsOpen(open);
    },
    [disabled],
  );

  const handleClose = useCallback(() => setIsOpen(false), []);

  const { focusedValue, setFocusedValue } = useDropdownMenu({
    triggerRef,
    panelRef,
    isOpen,
    onClose: handleClose,
  });

  // Seed the focused row to the currently selected value when opening.
  useEffect(() => {
    if (isOpen && selectedValues.size > 0 && !focusedValue) {
      const first = selectedValues.values().next().value as string | undefined;
      if (first) setFocusedValue(first);
    }
  }, [isOpen, selectedValues, focusedValue, setFocusedValue]);

  const handleValueChange = useCallback(
    (value: string) => {
      if (mode === "single") {
        if (!isControlledSingle) setInternalSingle(value);
        props.onChange?.(value);
        setIsOpen(false);
      } else {
        const next = new Set(selectedValues);
        if (next.has(value)) next.delete(value);
        else next.add(value);
        if (!isControlledMulti) setInternalMulti(next);
        props.onValuesChange?.(Array.from(next));
      }
    },
    [mode, isControlledSingle, isControlledMulti, selectedValues, props],
  );

  const ctx: SelectContextValue = {
    mode,
    isOpen,
    onOpenChange: handleOpenChange,
    selectedValues,
    onValueChange: handleValueChange,
    focusedValue,
    setFocusedValue,
    registerItem,
    panelRef,
  };

  const triggerLabel = useMemo(() => {
    if (selectedValues.size === 0) {
      return <span className="select__placeholder">{placeholder}</span>;
    }
    if (mode === "single") {
      const v = selectedValues.values().next().value as string;
      return <span className="select__value">{items.get(v) ?? v}</span>;
    }
    const arr = Array.from(selectedValues);
    const first = arr[0];
    const firstLabel = items.get(first) ?? first;
    if (arr.length === 1) return <span className="select__value">{firstLabel}</span>;
    return (
      <span className="select__value">
        {firstLabel} <span className="select__value-count">+{arr.length - 1}</span>
      </span>
    );
  }, [selectedValues, items, mode, placeholder]);

  const handleTriggerKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (isOpen) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleOpenChange(true);
    }
  };

  // Hidden inputs so the Select participates in native form submission.
  const hiddenInputs =
    name && selectedValues.size > 0
      ? Array.from(selectedValues).map((v) => <input key={v} type="hidden" name={name} value={v} />)
      : null;

  const setRefs = (node: HTMLButtonElement | null) => {
    (triggerRef as React.MutableRefObject<HTMLButtonElement | null>).current = node;
    if (typeof ref === "function") ref(node);
    else if (ref) (ref as React.MutableRefObject<HTMLButtonElement | null>).current = node;
  };

  return (
    <SelectContext.Provider value={ctx}>
      <div
        ref={rootRef}
        className={["select", error && "select--error", disabled && "select--disabled", className]
          .filter(Boolean)
          .join(" ")}
        data-testid={dataTestId}
      >
        <button
          ref={setRefs}
          id={id}
          type="button"
          className="select__trigger"
          aria-haspopup="listbox"
          aria-expanded={isOpen}
          aria-invalid={error || undefined}
          aria-label={ariaLabel}
          disabled={disabled}
          onClick={() => handleOpenChange(!isOpen)}
          onKeyDown={handleTriggerKeyDown}
        >
          {triggerLabel}
          <Icon
            name="chevronDown"
            size={14}
            className={`select__chevron ${isOpen ? "select__chevron--open" : ""}`}
          />
        </button>
        {hiddenInputs}
        <div
          ref={panelRef}
          role="listbox"
          aria-multiselectable={mode === "multi" ? true : undefined}
          className={`dropdown-panel ${dropdownPlacementClass(placement)} select__panel`}
          hidden={!isOpen}
        >
          {children}
        </div>
      </div>
    </SelectContext.Provider>
  );
});

SelectComponent.displayName = "Select";

/* ----------------------------------------------------------------------------
   Select.Item
   -------------------------------------------------------------------------- */

interface SelectItemProps {
  value: string;
  icon?: IconName;
  description?: ReactNode;
  disabled?: boolean;
  children: ReactNode;
}

function SelectItem({ value, icon, description, disabled = false, children }: SelectItemProps) {
  const { selectedValues, onValueChange, focusedValue, setFocusedValue, registerItem, mode } =
    useSelectContext("Select.Item");
  const rowRef = useRef<HTMLButtonElement>(null);
  const isSelected = selectedValues.has(value);
  const isFocused = focusedValue === value;

  useEffect(() => registerItem(value, children), [value, children, registerItem]);

  useEffect(() => {
    if (isFocused) rowRef.current?.focus();
  }, [isFocused]);

  return (
    <button
      ref={rowRef}
      type="button"
      role="option"
      aria-selected={isSelected}
      tabIndex={isFocused ? 0 : -1}
      data-dropdown-item={value}
      data-disabled={disabled || undefined}
      disabled={disabled}
      onClick={() => onValueChange(value)}
      onMouseEnter={() => !disabled && setFocusedValue(value)}
      className={[
        "dropdown-item",
        isSelected && "dropdown-item--selected",
        isFocused && "dropdown-item--focused",
        disabled && "dropdown-item--disabled",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {icon ? (
        <span className="dropdown-item__leading">
          <Icon name={icon} size={16} />
        </span>
      ) : null}
      <span className="dropdown-item__body">
        <span className="dropdown-item__label">{children}</span>
        {description && <span className="dropdown-item__description">{description}</span>}
      </span>
      {mode === "single" && isSelected && (
        <span className="dropdown-item__trailing">
          <Icon name="check" size={14} />
        </span>
      )}
    </button>
  );
}

/* ----------------------------------------------------------------------------
   Select.CheckboxItem
   -------------------------------------------------------------------------- */

interface SelectCheckboxItemProps {
  value: string;
  description?: ReactNode;
  disabled?: boolean;
  children: ReactNode;
}

function SelectCheckboxItem({
  value,
  description,
  disabled = false,
  children,
}: SelectCheckboxItemProps) {
  const { selectedValues, onValueChange, focusedValue, setFocusedValue, registerItem } =
    useSelectContext("Select.CheckboxItem");
  const rowRef = useRef<HTMLButtonElement>(null);
  const isSelected = selectedValues.has(value);
  const isFocused = focusedValue === value;

  useEffect(() => registerItem(value, children), [value, children, registerItem]);

  useEffect(() => {
    if (isFocused) rowRef.current?.focus();
  }, [isFocused]);

  return (
    <button
      ref={rowRef}
      type="button"
      role="option"
      aria-selected={isSelected}
      tabIndex={isFocused ? 0 : -1}
      data-dropdown-item={value}
      data-disabled={disabled || undefined}
      disabled={disabled}
      onClick={() => onValueChange(value)}
      onMouseEnter={() => !disabled && setFocusedValue(value)}
      className={[
        "dropdown-item",
        isFocused && "dropdown-item--focused",
        disabled && "dropdown-item--disabled",
      ]
        .filter(Boolean)
        .join(" ")}
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
        <span className="dropdown-item__label">{children}</span>
        {description && <span className="dropdown-item__description">{description}</span>}
      </span>
    </button>
  );
}

/* ----------------------------------------------------------------------------
   Select.Separator + Select.SectionTitle
   -------------------------------------------------------------------------- */

function SelectSeparator() {
  return <div role="separator" className="dropdown-separator" />;
}

interface SelectSectionTitleProps {
  children: ReactNode;
}

function SelectSectionTitle({ children }: SelectSectionTitleProps) {
  return <div className="dropdown-section-title">{children}</div>;
}

interface SelectCompound extends React.ForwardRefExoticComponent<
  SelectProps & React.RefAttributes<HTMLButtonElement>
> {
  Item: typeof SelectItem;
  CheckboxItem: typeof SelectCheckboxItem;
  Separator: typeof SelectSeparator;
  SectionTitle: typeof SelectSectionTitle;
}

const Select = Object.assign(SelectComponent, {
  Item: SelectItem,
  CheckboxItem: SelectCheckboxItem,
  Separator: SelectSeparator,
  SectionTitle: SelectSectionTitle,
}) as SelectCompound;

// --- Babel-standalone: expose runtime values to window ---
window.Select = Select;
