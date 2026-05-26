import React, { useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react'
import './RowMenu.css'
import { Icon, type IconName } from './Icon'

export type RowMenuAction = {
  id: string
  label: string
  icon?: IconName
  danger?: boolean
  disabled?: boolean
} | {
  type: 'separator'
}

export interface RowMenuProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onChange'> {
  actions: RowMenuAction[]
  onAction: (actionId: string) => void
  trigger?: React.ReactNode
  triggerIcon?: IconName
  triggerLabel?: string
}

const isSeparator = (action: RowMenuAction): action is { type: 'separator' } => {
  return 'type' in action && action.type === 'separator'
}

export const RowMenu = React.forwardRef<HTMLDivElement, RowMenuProps>(
  ({ actions, onAction, trigger, triggerIcon = 'moreVertical', triggerLabel = 'Menu', className, ...props }, ref) => {
    const [isOpen, setIsOpen] = useState(false)
    const containerRef = useRef<HTMLDivElement>(null)
    const dropdownRef = useRef<HTMLDivElement>(null)
    const triggerRef = useRef<HTMLButtonElement>(null)

    const focusItem = useCallback((index: number) => {
      const items = dropdownRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not([disabled])')
      items?.[index]?.focus()
    }, [])

    useEffect(() => {
      const container = containerRef.current

      const handleClickOutside = (e: MouseEvent) => {
        if (container && !container.contains(e.target as Node)) {
          setIsOpen(false)
        }
      }

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          setIsOpen(false)
          triggerRef.current?.focus()
          return
        }
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
          e.preventDefault()
          const items = dropdownRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not([disabled])')
          if (!items || items.length === 0) return
          const focused = dropdownRef.current?.querySelector<HTMLButtonElement>('[role="menuitem"]:focus')
          const idx = focused ? Array.from(items).indexOf(focused) : -1
          if (e.key === 'ArrowDown') {
            focusItem(idx < items.length - 1 ? idx + 1 : 0)
          } else {
            focusItem(idx > 0 ? idx - 1 : items.length - 1)
          }
        }
        if (e.key === 'Home') {
          e.preventDefault()
          focusItem(0)
        }
        if (e.key === 'End') {
          e.preventDefault()
          const items = dropdownRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not([disabled])')
          if (items) focusItem(items.length - 1)
        }
      }

      if (isOpen) {
        document.addEventListener('mousedown', handleClickOutside)
        document.addEventListener('keydown', handleKeyDown)
        return () => {
          document.removeEventListener('mousedown', handleClickOutside)
          document.removeEventListener('keydown', handleKeyDown)
        }
      }
    }, [isOpen, focusItem])

    useEffect(() => {
      if (isOpen) {
        const items = dropdownRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not([disabled])')
        items?.[0]?.focus()
      }
    }, [isOpen])

    useImperativeHandle(ref, () => containerRef.current as HTMLDivElement)

    const handleActionClick = useCallback((actionId: string) => {
      onAction(actionId)
      setIsOpen(false)
    }, [onAction])

    const handleTriggerClick = () => {
      setIsOpen(!isOpen)
    }

    return (
      <div ref={containerRef} className={['row-menu', className].filter(Boolean).join(' ')} data-testid="row-menu" {...props}>
        <button
          ref={triggerRef}
          type="button"
          className="row-menu__trigger"
          onClick={handleTriggerClick}
          aria-label={triggerLabel}
          aria-haspopup="menu"
          aria-expanded={isOpen}
          data-testid="row-menu-trigger"
        >
          {trigger || <Icon name={triggerIcon} size={16} />}
        </button>

        {isOpen && (
          <div
            ref={dropdownRef}
            role="menu"
            aria-label={triggerLabel}
            className="row-menu__dropdown"
            data-testid="row-menu-dropdown"
          >
            {actions.map((action, index) =>
              isSeparator(action) ? (
                <div
                  key={`separator-${index}`}
                  role="separator"
                  className="row-menu__separator"
                  data-testid={`row-menu-separator-${index}`}
                />
              ) : (
                <button
                  key={action.id}
                  type="button"
                  role="menuitem"
                  tabIndex={-1}
                  disabled={action.disabled}
                  className={[
                    'row-menu__action',
                    action.danger && 'row-menu__action--danger',
                    action.disabled && 'row-menu__action--disabled',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={() => !action.disabled && handleActionClick(action.id)}
                  data-testid={`row-menu-action-${action.id}`}
                >
                  {action.icon && <Icon name={action.icon} size={16} />}
                  <span className="row-menu__label">{action.label}</span>
                </button>
              )
            )}
          </div>
        )}
      </div>
    )
  }
)

RowMenu.displayName = 'RowMenu'

export default RowMenu
