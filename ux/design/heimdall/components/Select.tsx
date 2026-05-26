import React from 'react'
import './Select.css'

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  error?: boolean
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ error = false, className = '', ...props }, ref) => {
    const classNames = [
      'select',
      error && 'select--error',
      className,
    ]
      .filter(Boolean)
      .join(' ')

    return (
      <select
        ref={ref}
        className={classNames}
        aria-invalid={error || undefined}
        {...props}
      />
    )
  }
)

Select.displayName = 'Select'

export default Select
