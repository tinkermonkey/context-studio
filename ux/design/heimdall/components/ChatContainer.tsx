import React, { useRef, useEffect } from 'react'
import './ChatContainer.css'

export interface BotTab {
  id: string
  label: string
  role: string
  status: 'idle' | 'busy' | 'healthy' | 'error'
}

export interface ChatContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  bots?: BotTab[]
  activeBotId?: string
  onBotChange?: (botId: string) => void
  autoScroll?: boolean
  composer?: React.ReactNode
}

export const ChatContainer = React.forwardRef<HTMLDivElement, ChatContainerProps>(
  (
    {
      children,
      bots = [],
      activeBotId,
      onBotChange,
      autoScroll = true,
      composer,
      className = '',
      ...props
    },
    ref
  ) => {
    const threadRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
      if (autoScroll && threadRef.current) {
        threadRef.current.scrollTop = threadRef.current.scrollHeight
      }
    }, [children, autoScroll])

    return (
      <div
        ref={ref}
        className={['chat-container', className].filter(Boolean).join(' ')}
        {...props}
      >
        {bots && bots.length > 0 && (
          <div className="chat-container__bot-tabs" role="group" aria-label="Bot tabs">
            {bots.map((bot) => (
              <button
                key={bot.id}
                type="button"
                className={[
                  'chat-container__bot-tab',
                  activeBotId === bot.id && 'chat-container__bot-tab--active',
                ]
                  .filter(Boolean)
                  .join(' ')}
                onClick={() => onBotChange?.(bot.id)}
                aria-pressed={activeBotId === bot.id}
                aria-label={`${bot.label} — ${bot.role}`}
              >
                <span className="chat-container__bot-label">
                  <span
                    className={[
                      'chat-container__bot-status',
                      `chat-container__bot-status--${bot.status}`,
                    ]
                      .filter(Boolean)
                      .join(' ')}
                  />
                  {bot.label}
                </span>
                <span className="chat-container__bot-role">{bot.role}</span>
              </button>
            ))}
          </div>
        )}

        <div
          ref={threadRef}
          className="chat-container__thread"
          role="log"
          aria-live="polite"
          aria-atomic="false"
        >
          <div className="chat-container__messages">
            {children}
          </div>
        </div>

        {composer}
      </div>
    )
  }
)

ChatContainer.displayName = 'ChatContainer'

export default ChatContainer
