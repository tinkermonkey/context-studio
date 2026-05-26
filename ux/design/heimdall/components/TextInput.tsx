import React from 'react'
import './inputs.css'

export interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  mono?: boolean
  error?: boolean
}

export const TextInput = React.forwardRef<HTMLInputElement, TextInputProps>(
  ({ mono = false, error = false, className = '', ...props }, ref) => {
    const classNames = [
      'text-input',
      mono && 'text-input--mono',
      error && 'text-input--error',
      className,
    ]
      .filter(Boolean)
      .join(' ')

    return (
      <input
        type="text"
        ref={ref}
        className={classNames}
        {...props}
      />
    )
  }
)

TextInput.displayName = 'TextInput'

export default TextInput
