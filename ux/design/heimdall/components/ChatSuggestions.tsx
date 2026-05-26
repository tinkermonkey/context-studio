import React from 'react'
import './ChatSuggestions.css'

export interface ChatSuggestionsProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onSelect'> {
  suggestions: string[]
  onSelect: (suggestion: string) => void
  selected?: string
}

export const ChatSuggestions = React.forwardRef<HTMLDivElement, ChatSuggestionsProps>(
  ({ suggestions, onSelect, selected, className = '', 'aria-label': ariaLabel = 'Suggestions', ...props }, ref) => {
    if (!suggestions || suggestions.length === 0) {
      return null
    }

    const hasSelection = selected !== undefined

    return (
      <div
        ref={ref}
        role="group"
        aria-label={ariaLabel}
        className={['chat-suggestions', className].filter(Boolean).join(' ')}
        data-testid="chat-suggestions"
        {...props}
      >
        {suggestions.map((suggestion) => {
          const isSelected = suggestion === selected
          const isDisabled = hasSelection && !isSelected
          return (
            <button
              key={suggestion}
              className={[
                'chat-suggestions__pill',
                isSelected ? 'chat-suggestions__pill--selected' : '',
                isDisabled ? 'chat-suggestions__pill--disabled' : '',
              ].filter(Boolean).join(' ')}
              onClick={() => !isDisabled && onSelect(suggestion)}
              type="button"
              disabled={isDisabled}
              aria-pressed={isSelected}
            >
              {suggestion}
            </button>
          )
        })}
      </div>
    )
  }
)

ChatSuggestions.displayName = 'ChatSuggestions'

export default ChatSuggestions
