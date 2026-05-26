import React from 'react'
import './ChatDivider.css'

export interface ChatDividerProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string
}

export const ChatDivider = React.forwardRef<HTMLDivElement, ChatDividerProps>(
  ({ label, className = '', ...props }, ref) => {
    return (
      <div
        ref={ref}
        role="separator"
        aria-label={label}
        className={['chat-divider', className].filter(Boolean).join(' ')}
        data-testid="chat-divider"
        {...props}
      >
        <span className="chat-divider__line" />
        <span className="chat-divider__label" aria-hidden="true">{label}</span>
        <span className="chat-divider__line" />
      </div>
    )
  }
)

ChatDivider.displayName = 'ChatDivider'

export default ChatDivider
