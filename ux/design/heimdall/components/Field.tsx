import React from 'react'
import './Field.css'

export interface FieldProps extends React.HTMLAttributes<HTMLDivElement> {
  label?: React.ReactNode
  htmlFor?: string
  required?: boolean
  disabled?: boolean
  error?: React.ReactNode
  errorId?: string
  hint?: React.ReactNode
  children: React.ReactNode
}

export const Field = React.forwardRef<HTMLDivElement, FieldProps>(
  ({ label, htmlFor, required = false, disabled = false, error, errorId, hint, children, className = '', ...props }, ref) => {
    const classNames = ['field', disabled ? 'field--disabled' : '', className].filter(Boolean).join(' ')

    return (
      <div ref={ref} className={classNames} {...props}>
        {label && (
          <label className="field__label" htmlFor={htmlFor}>
            <span>{label}</span>
            {required && <span className="field__required">*</span>}
            {hint && <span className="field__hint">{hint}</span>}
          </label>
        )}
        <div className="field__input">{children}</div>
        {error && <div className="field__error" id={errorId}>{error}</div>}
      </div>
    )
  }
)

Field.displayName = 'Field'

export default Field
