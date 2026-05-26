import React, {
  useState,
  useRef,
  useCallback,
  useEffect,
  createContext,
  useContext,
  ReactNode,
} from 'react'
import './FilterDropdown.css'
import { Icon } from './Icon'

interface FilterDropdownContextValue {
  isOpen: boolean
  onOpenChange: (open: boolean) => void
  mode: 'checkbox' | 'radio'
  selectedValues: Set<string>
  onValueChange: (value: string, selected: boolean) => void
  focusedValue: string | null
  onFocusedValueChange: (value: string | null) => void
  triggerRef: React.RefObject<HTMLButtonElement>
  panelRef: React.RefObject<HTMLDivElement>
}

const FilterDropdownContext = createContext<FilterDropdownContextValue | undefined>(undefined)

function useFilterDropdown() {
  const context = useContext(FilterDropdownContext)
  if (!context) {
    throw new Error('FilterDropdown components must be used within FilterDropdown')
  }
  return context
}

export interface FilterDropdownProps {
  mode?: 'checkbox' | 'radio'
  children: ReactNode
  onChange?: (selectedValues: string[]) => void
  className?: string
  defaultValue?: string[]
  value?: string[]
}

const FilterDropdownComponent = React.forwardRef<HTMLDivElement, FilterDropdownProps>(
  ({ mode = 'checkbox', children, onChange, className = '', defaultValue, value }, ref) => {
    const [isOpen, setIsOpen] = useState(false)
    const isControlled = value !== undefined
    const [internalValues, setInternalValues] = useState<Set<string>>(new Set(defaultValue ?? []))
    const selectedValues = isControlled ? new Set(value) : internalValues
    const [focusedValue, setFocusedValue] = useState<string | null>(null)
    const triggerRef = useRef<HTMLButtonElement>(null)
    const panelRef = useRef<HTMLDivElement>(null)
    const rootRef = useRef<HTMLDivElement>(null)

    const handleOpenChange = useCallback((open: boolean) => {
      setIsOpen(open)
      if (open && panelRef.current) {
        const rows = Array.from(panelRef.current.querySelectorAll('[data-focusable-value]'))
        const firstFocusableValue = rows[0]?.getAttribute('data-focusable-value')
        if (firstFocusableValue) {
          setFocusedValue(firstFocusableValue)
        }
      } else if (!open) {
        setFocusedValue(null)
        triggerRef.current?.focus()
      }
    }, [panelRef, triggerRef])

    const handleValueChange = useCallback(
      (itemValue: string, selected: boolean) => {
        const nextValues = new Set(selectedValues)

        if (selected) {
          if (mode === 'radio') {
            nextValues.clear()
          }
          nextValues.add(itemValue)
        } else {
          nextValues.delete(itemValue)
        }

        if (!isControlled) {
          setInternalValues(nextValues)
        }
        onChange?.(Array.from(nextValues))

        if (mode === 'radio' && selected) {
          handleOpenChange(false)
        }
      },
      [selectedValues, mode, onChange, handleOpenChange, isControlled]
    )

    const handleFocusedValueChange = useCallback((value: string | null) => {
      setFocusedValue(value)
    }, [])

    const handleKeyDown = useCallback(
      (e: KeyboardEvent) => {
        if (!isOpen || !panelRef.current) return

        const rows = Array.from(panelRef.current.querySelectorAll('[data-focusable-value]'))
        const focusableRowsInDomOrder = rows
          .map((row) => row.getAttribute('data-focusable-value'))
          .filter((v): v is string => v !== null)

        if (focusableRowsInDomOrder.length === 0) return

        const currentIndex = focusableRowsInDomOrder.indexOf(
          focusedValue || focusableRowsInDomOrder[0]
        )

        if (e.key === 'ArrowDown') {
          e.preventDefault()
          const nextIndex = (currentIndex + 1) % focusableRowsInDomOrder.length
          setFocusedValue(focusableRowsInDomOrder[nextIndex])
        } else if (e.key === 'ArrowUp') {
          e.preventDefault()
          const nextIndex =
            (currentIndex - 1 + focusableRowsInDomOrder.length) % focusableRowsInDomOrder.length
          setFocusedValue(focusableRowsInDomOrder[nextIndex])
        } else if (e.key === 'Tab') {
          e.preventDefault()
          const nextIndex = e.shiftKey
            ? (currentIndex - 1 + focusableRowsInDomOrder.length) % focusableRowsInDomOrder.length
            : (currentIndex + 1) % focusableRowsInDomOrder.length
          setFocusedValue(focusableRowsInDomOrder[nextIndex])
        }
      },
      [isOpen, focusedValue, panelRef]
    )

    // Close on ESC or outside click
    useEffect(() => {
      if (!isOpen) return

      const panelElement = panelRef.current

      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          e.preventDefault()
          handleOpenChange(false)
        }
      }

      const handleClickOutside = (e: MouseEvent) => {
        const target = e.target as Node
        if (rootRef.current && !rootRef.current.contains(target)) {
          handleOpenChange(false)
        }
      }

      // Add keyboard handler to panel for arrow navigation
      panelElement?.addEventListener('keydown', handleKeyDown as EventListener)
      document.addEventListener('keydown', handleEscape)
      document.addEventListener('mousedown', handleClickOutside)

      return () => {
        panelElement?.removeEventListener('keydown', handleKeyDown as EventListener)
        document.removeEventListener('keydown', handleEscape)
        document.removeEventListener('mousedown', handleClickOutside)
      }
    }, [isOpen, handleOpenChange, handleKeyDown])

    const contextValue: FilterDropdownContextValue = {
      isOpen,
      onOpenChange: handleOpenChange,
      mode,
      selectedValues,
      onValueChange: handleValueChange,
      focusedValue,
      onFocusedValueChange: handleFocusedValueChange,
      triggerRef,
      panelRef,
    }

    return (
      <FilterDropdownContext.Provider value={contextValue}>
        <div ref={(node) => {
          (rootRef as React.MutableRefObject<HTMLDivElement | null>).current = node
          if (typeof ref === 'function') ref(node)
          else if (ref) (ref as React.MutableRefObject<HTMLDivElement | null>).current = node
        }} className={`filter-dropdown ${className}`.trim()}>
          {children}
        </div>
      </FilterDropdownContext.Provider>
    )
  }
)

FilterDropdownComponent.displayName = 'FilterDropdown'

export interface FilterDropdownTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  label: string
  summary: ReactNode
}

function FilterDropdownTrigger({ label, summary, ...props }: FilterDropdownTriggerProps) {
  const { isOpen, onOpenChange, triggerRef, mode } = useFilterDropdown()

  return (
    <button
      ref={triggerRef}
      type="button"
      {...props}
      className="filter-dropdown__trigger"
      onClick={() => onOpenChange(!isOpen)}
      aria-haspopup={mode === 'radio' ? 'dialog' : 'listbox'}
      aria-expanded={isOpen}
    >
      <span className="filter-dropdown__label">{label}</span>
      <span className="filter-dropdown__summary">{summary}</span>
      <Icon
        name="chevronDown"
        size={14}
        className={`filter-dropdown__chevron ${isOpen ? 'filter-dropdown__chevron--open' : ''}`}
      />
    </button>
  )
}

export interface FilterDropdownPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  children: ReactNode
}

function FilterDropdownPanel({ children, className = '', style, ...restProps }: FilterDropdownPanelProps) {
  const { isOpen, mode, panelRef } = useFilterDropdown()

  return (
    <div
      ref={panelRef}
      className={`filter-dropdown__panel ${className}`.trim()}
      role={mode === 'checkbox' ? 'listbox' : 'radiogroup'}
      aria-multiselectable={mode === 'checkbox' ? true : undefined}
      hidden={!isOpen}
      style={isOpen ? style : undefined}
      {...restProps}
    >
      {children}
    </div>
  )
}

export interface FilterDropdownSectionProps {
  title?: string
  children: ReactNode
}

function FilterDropdownSection({ title, children }: FilterDropdownSectionProps) {
  return (
    <div className="filter-dropdown__section">
      {title && <div className="filter-dropdown__section-title">{title}</div>}
      <div className="filter-dropdown__section-content">{children}</div>
    </div>
  )
}

export interface FilterDropdownCheckboxProps {
  value: string
  label: ReactNode
  description?: ReactNode
}

function FilterDropdownCheckbox({ value, label, description }: FilterDropdownCheckboxProps) {
  const {
    selectedValues,
    onValueChange,
    focusedValue,
    mode,
  } = useFilterDropdown()
  const rowRef = useRef<HTMLDivElement>(null)

  const isSelected = selectedValues.has(value)
  const isFocused = focusedValue === value

  useEffect(() => {
    if (isFocused && rowRef.current) {
      rowRef.current.focus()
    }
  }, [isFocused])

  const handleClick = () => {
    onValueChange(value, !isSelected)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onValueChange(value, !isSelected)
    }
  }

  return (
    <div
      ref={rowRef}
      className={`filter-dropdown__row ${isFocused ? 'filter-dropdown__row--focused' : ''}`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      tabIndex={isFocused ? 0 : -1}
      role={mode === 'checkbox' ? 'option' : undefined}
      aria-selected={isSelected}
      data-focusable-value={value}
    >
      <div className="filter-dropdown__row-checkbox">
        <input
          type="checkbox"
          className="filter-dropdown__checkbox"
          checked={isSelected}
          onChange={(e) => onValueChange(value, e.target.checked)}
          onClick={(e) => e.stopPropagation()}
          aria-hidden="true"
          tabIndex={-1}
        />
      </div>
      <div className="filter-dropdown__row-content">
        <div className="filter-dropdown__row-label">{label}</div>
        {description && (
          <div className="filter-dropdown__row-description">{description}</div>
        )}
      </div>
    </div>
  )
}

export interface FilterDropdownRadioProps {
  value: string
  label: ReactNode
  description?: ReactNode
}

function FilterDropdownRadio({ value, label, description }: FilterDropdownRadioProps) {
  const {
    selectedValues,
    onValueChange,
    focusedValue,
  } = useFilterDropdown()
  const rowRef = useRef<HTMLDivElement>(null)

  const isSelected = selectedValues.has(value)
  const isFocused = focusedValue === value

  useEffect(() => {
    if (isFocused && rowRef.current) {
      rowRef.current.focus()
    }
  }, [isFocused])

  const handleClick = () => {
    onValueChange(value, true)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onValueChange(value, true)
    }
  }

  return (
    <div
      ref={rowRef}
      className={`filter-dropdown__row ${isFocused ? 'filter-dropdown__row--focused' : ''}`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      tabIndex={isFocused ? 0 : -1}
      role="radio"
      aria-checked={isSelected}
      data-focusable-value={value}
    >
      <div className="filter-dropdown__row-radio">
        <input
          type="radio"
          checked={isSelected}
          onChange={() => onValueChange(value, true)}
          onClick={(e) => e.stopPropagation()}
          aria-hidden="true"
          tabIndex={-1}
        />
      </div>
      <div className="filter-dropdown__row-content">
        <div className="filter-dropdown__row-label">{label}</div>
        {description && (
          <div className="filter-dropdown__row-description">{description}</div>
        )}
      </div>
    </div>
  )
}

interface FilterDropdownComponentType extends React.ForwardRefExoticComponent<FilterDropdownProps & React.RefAttributes<HTMLDivElement>> {
  Trigger: typeof FilterDropdownTrigger
  Panel: typeof FilterDropdownPanel
  Section: typeof FilterDropdownSection
  Checkbox: typeof FilterDropdownCheckbox
  Radio: typeof FilterDropdownRadio
}

const FilterDropdown = Object.assign(FilterDropdownComponent, {
  Trigger: FilterDropdownTrigger,
  Panel: FilterDropdownPanel,
  Section: FilterDropdownSection,
  Checkbox: FilterDropdownCheckbox,
  Radio: FilterDropdownRadio,
}) as FilterDropdownComponentType

export { FilterDropdown }
export default FilterDropdown
