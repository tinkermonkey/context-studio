import React, { useEffect, useRef, useImperativeHandle } from 'react'
import './Drawer.css'
import { Icon } from './Icon'
import { useFocusTrap } from '../hooks/useFocusTrap'
import { useBodyOverflow } from '../hooks/useBodyOverflow'

export interface DrawerProps extends React.HTMLAttributes<HTMLDivElement> {
  isOpen: boolean
  onClose: () => void
  title?: string
  position?: 'left' | 'right'
  width?: string
  children: React.ReactNode
}

export const Drawer = React.forwardRef<HTMLDivElement, DrawerProps>(
  ({ isOpen, onClose, title, position = 'right', width = '320px', children, className = '', ...props }, ref) => {
    const titleId = React.useId()
    const drawerRef = useRef<HTMLDivElement>(null)

    useImperativeHandle(ref, () => drawerRef.current as HTMLDivElement)

    useFocusTrap(drawerRef, isOpen)
    useBodyOverflow(isOpen)

    useEffect(() => {
      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === 'Escape' && isOpen) {
          onClose()
        }
      }

      if (isOpen) {
        document.addEventListener('keydown', handleEscape)
        return () => {
          document.removeEventListener('keydown', handleEscape)
        }
      }
    }, [isOpen, onClose])

    const handleBackdropClick = (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) {
        onClose()
      }
    }

    if (!isOpen) return null

    return (
      <div
        className="drawer-backdrop"
        onClick={handleBackdropClick}
      >
        <div
          ref={drawerRef}
          className={['drawer', `drawer--${position}`, className].filter(Boolean).join(' ')}
          style={{ width }}
          role="dialog"
          aria-modal="true"
          aria-labelledby={title ? titleId : undefined}
          {...props}
        >
          <div className={['drawer__header', !title ? 'drawer__header--no-title' : ''].filter(Boolean).join(' ')}>
            {title && <h2 id={titleId} className="drawer__title">{title}</h2>}
            <button
              type="button"
              className="drawer__close"
              onClick={onClose}
              aria-label="Close drawer"
            >
              <Icon name="x" size={14} />
            </button>
          </div>
          <div className="drawer__body">{children}</div>
        </div>
      </div>
    )
  }
)

Drawer.displayName = 'Drawer'

export default Drawer
