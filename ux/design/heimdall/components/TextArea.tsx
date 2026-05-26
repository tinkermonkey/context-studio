import React from 'react'
import './inputs.css'

export interface TextAreaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  mono?: boolean
  error?: boolean
}

export const TextArea = React.forwardRef<HTMLTextAreaElement, TextAreaProps>(
  ({ mono = false, error = false, className = '', ...props }, ref) => {
    const classNames = [
      'text-area',
      mono && 'text-area--mono',
      error && 'text-area--error',
      className,
    ]
      .filter(Boolean)
      .join(' ')

    return (
      <textarea
        ref={ref}
        className={classNames}
        {...props}
      />
    )
  }
)

TextArea.displayName = 'TextArea'

export default TextArea
