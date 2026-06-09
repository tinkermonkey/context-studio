
type RowMenuAction =
  | {
      id: string
      label: string
      icon?: IconName
      danger?: boolean
      disabled?: boolean
    }
  | {
      type: 'separator'
    }

interface RowMenuProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onChange'> {
  actions: RowMenuAction[]
  onAction: (actionId: string) => void
  trigger?: React.ReactNode
  triggerIcon?: IconName
  triggerLabel?: string
  /** Where the dropdown panel opens relative to the trigger. Defaults to
   *  `bottom-start` (panel hangs below, left-aligned with trigger). Use
   *  `bottom-end` for the classic kebab-at-row-right pattern. */
  placement?: DropdownPlacement
}

const isSeparator = (action: RowMenuAction): action is { type: 'separator' } =>
  'type' in action && action.type === 'separator'

const RowMenu = React.forwardRef<HTMLDivElement, RowMenuProps>(
  (
    {
      actions,
      onAction,
      trigger,
      triggerIcon = 'moreVertical',
      triggerLabel = 'Menu',
      placement = 'bottom-start',
      className,
      ...props
    },
    ref
  ) => {
    const [isOpen, setIsOpen] = useState(false)
    const containerRef = useRef<HTMLDivElement>(null)
    const panelRef = useRef<HTMLDivElement>(null)
    const triggerRef = useRef<HTMLButtonElement>(null)

    const handleClose = useCallback(() => setIsOpen(false), [])

    const { focusedValue, setFocusedValue } = useDropdownMenu({
      triggerRef,
      panelRef,
      isOpen,
      onClose: handleClose,
    })

    useImperativeHandle(ref, () => containerRef.current as HTMLDivElement)

    const handleActionClick = useCallback(
      (actionId: string) => {
        onAction(actionId)
        setIsOpen(false)
      },
      [onAction]
    )

    return (
      <div
        ref={containerRef}
        className={['row-menu', className].filter(Boolean).join(' ')}
        data-testid="row-menu"
        {...props}
      >
        <button
          ref={triggerRef}
          type="button"
          className="row-menu__trigger"
          onClick={() => setIsOpen((o) => !o)}
          aria-label={triggerLabel}
          aria-haspopup="menu"
          aria-expanded={isOpen}
          data-testid="row-menu-trigger"
        >
          {trigger || <Icon name={triggerIcon} size={16} />}
        </button>

        {isOpen && (
          <div
            ref={panelRef}
            role="menu"
            aria-label={triggerLabel}
            className={`dropdown-panel ${dropdownPlacementClass(placement)} row-menu__dropdown`}
            data-testid="row-menu-dropdown"
          >
            {actions.map((action, index) =>
              isSeparator(action) ? (
                <div
                  key={`separator-${index}`}
                  role="separator"
                  className="dropdown-separator"
                  data-testid={`row-menu-separator-${index}`}
                />
              ) : (
                <RowMenuAction
                  key={action.id}
                  action={action}
                  isFocused={focusedValue === action.id}
                  onFocus={() => setFocusedValue(action.id)}
                  onClick={() => handleActionClick(action.id)}
                />
              )
            )}
          </div>
        )}
      </div>
    )
  }
)

RowMenu.displayName = 'RowMenu'

interface RowMenuActionProps {
  action: Extract<RowMenuAction, { id: string }>
  isFocused: boolean
  onFocus: () => void
  onClick: () => void
}

function RowMenuAction({ action, isFocused, onFocus, onClick }: RowMenuActionProps) {
  const ref = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (isFocused) ref.current?.focus()
  }, [isFocused])

  return (
    <button
      ref={ref}
      type="button"
      role="menuitem"
      tabIndex={isFocused ? 0 : -1}
      disabled={action.disabled}
      data-dropdown-item={action.id}
      data-disabled={action.disabled || undefined}
      onClick={onClick}
      onMouseEnter={() => !action.disabled && onFocus()}
      className={[
        'dropdown-item',
        action.danger && 'dropdown-item--danger',
        isFocused && 'dropdown-item--focused',
        action.disabled && 'dropdown-item--disabled',
      ]
        .filter(Boolean)
        .join(' ')}
      data-testid={`row-menu-action-${action.id}`}
    >
      {action.icon && (
        <span className="dropdown-item__leading">
          <Icon name={action.icon} size={16} />
        </span>
      )}
      <span className="dropdown-item__label">{action.label}</span>
    </button>
  )
}



// --- Babel-standalone: expose runtime values to window ---
window.RowMenu = RowMenu;
