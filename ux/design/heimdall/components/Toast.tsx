import React, { useEffect } from 'react'
import './Toast.css'
import { Icon, IconName } from './Icon'

export type ToastVariant = 'success' | 'error' | 'warning' | 'info'

export interface ToastProps extends React.HTMLAttributes<HTMLDivElement> {
  isOpen: boolean
  onClose: () => void
  title?: string
  subtitle?: string
  variant?: ToastVariant
  icon?: IconName
  duration?: number
}

const variantIcons: Record<ToastVariant, IconName> = {
  success: 'check',
  error: 'x',
  warning: 'alert',
  info: 'info',
}

const variantColors: Record<ToastVariant, string> = {
  success: 'emerald',
  error: 'rose',
  warning: 'amber',
  info: 'cyan',
}

export const Toast = React.forwardRef<HTMLDivElement, ToastProps>(
  ({
    isOpen,
    onClose,
    title,
    subtitle,
    variant = 'info',
    icon,
    duration = 4000,
    className = '',
    ...props
  }, ref) => {
    useEffect(() => {
      if (isOpen && duration) {
        const timer = setTimeout(onClose, duration)
        return () => clearTimeout(timer)
      }
    }, [isOpen, duration, onClose])

    if (!isOpen) return null

    const iconName = icon || variantIcons[variant]
    const color = variantColors[variant]

    return (
      <div
        ref={ref}
        className={['toast', `toast--${variant}`, className].filter(Boolean).join(' ')}
        role={variant === 'error' || variant === 'warning' ? 'alert' : 'status'}
        aria-live={variant === 'error' || variant === 'warning' ? 'assertive' : 'polite'}
        aria-atomic="true"
        {...props}
      >
        <div className={`toast__icon toast__icon--${color}`}>
          <Icon name={iconName} size={12} />
        </div>
        <div className="toast__content">
          {title && <div className="toast__title">{title}</div>}
          {subtitle && <div className="toast__subtitle">{subtitle}</div>}
        </div>
        <button
          type="button"
          className="toast__close"
          onClick={onClose}
          aria-label="Dismiss notification"
        >
          <Icon name="x" size={14} />
        </button>
      </div>
    )
  }
)

Toast.displayName = 'Toast'

export default Toast
