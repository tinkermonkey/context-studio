import React, { useEffect, useRef, useImperativeHandle } from 'react'
import { Icon } from './Icon'
import { useFocusTrap } from '../hooks/useFocusTrap'
import { useBodyOverflow } from '../hooks/useBodyOverflow'
import './Modal.css'

export type ModalSize = 'sm' | 'md' | 'lg' | 'xl'

export interface ModalProps extends React.HTMLAttributes<HTMLDivElement> {
  isOpen: boolean
  onClose: () => void
  title?: string
  subtitle?: string
  children: React.ReactNode
  footer?: React.ReactNode
  hintFooter?: string
  size?: ModalSize
}

export const Modal = React.forwardRef<HTMLDivElement, ModalProps>(
  ({ isOpen, onClose, title, subtitle, children, footer, hintFooter, size = 'md', className = '', ...props }, ref) => {
    const titleId = React.useId()
    const backdropRef = useRef<HTMLDivElement>(null)
    const modalRef = useRef<HTMLDivElement>(null)

    useImperativeHandle(ref, () => modalRef.current as HTMLDivElement)

    useFocusTrap(modalRef, isOpen)
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
      if (e.target === backdropRef.current) {
        onClose()
      }
    }

    if (!isOpen) return null

    return (
      <div
        ref={backdropRef}
        className="modal-backdrop"
        onClick={handleBackdropClick}
      >
        <div
          ref={modalRef}
          className={['modal', `modal--${size}`, className].filter(Boolean).join(' ')}
          role="dialog"
          aria-modal="true"
          aria-labelledby={title ? titleId : undefined}
          {...props}
        >
          {title && (
            <div className="modal__header">
              <div className="modal__header-text">
                <div id={titleId} className="modal__title">{title}</div>
                {subtitle && <div className="modal__subtitle">{subtitle}</div>}
              </div>
              <button
                type="button"
                className="modal__close"
                onClick={onClose}
                aria-label="Close dialog"
              >
                <Icon name="x" size={14} />
              </button>
            </div>
          )}
          <div className="modal__body">{children}</div>
          {footer && <div className="modal__footer">{footer}</div>}
          {hintFooter && <div className="modal__foot-hint">{hintFooter}</div>}
        </div>
      </div>
    )
  }
)

Modal.displayName = 'Modal'

export default Modal
