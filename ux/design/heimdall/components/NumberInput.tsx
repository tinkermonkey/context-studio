import React from 'react'
import './inputs.css'

export interface NumberInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  mono?: boolean
  error?: boolean
}

export const NumberInput = React.forwardRef<HTMLInputElement, NumberInputProps>(
  ({ mono = false, error = false, className = '', ...props }, ref) => {
    const classNames = [
      'number-input',
      mono && 'number-input--mono',
      error && 'number-input--error',
      className,
    ]
      .filter(Boolean)
      .join(' ')

    return (
      <input
        ref={ref}
        type="number"
        className={classNames}
        {...props}
      />
    )
  }
)

NumberInput.displayName = 'NumberInput'

export default NumberInput
