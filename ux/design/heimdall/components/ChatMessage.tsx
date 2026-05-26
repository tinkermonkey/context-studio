import React from 'react'
import './ChatMessage.css'
import { Icon } from './Icon'

export interface ToolBlockData {
  name: string
  status: 'running' | 'success' | 'error'
  output?: Array<{ key?: string; value: string }>
}

export interface ThinkingBlockData {
  content: string
}

export interface ChatMessageProps extends React.HTMLAttributes<HTMLDivElement> {
  role: 'user' | 'bot'
  senderName: string
  timestamp: string
  body: React.ReactNode
  avatar?: string
  badge?: string
  toolBlock?: ToolBlockData
  thinkingBlock?: ThinkingBlockData
}

const isUrl = (s: string) => /^https?:\/\//.test(s) || s.startsWith('/')

export const ChatMessage = React.forwardRef<HTMLDivElement, ChatMessageProps>(
  (
    {
      role,
      senderName,
      timestamp,
      body,
      avatar,
      badge,
      toolBlock,
      thinkingBlock,
      className = '',
      ...props
    },
    ref
  ) => {
    const avatarContent =
      avatar && isUrl(avatar) ? (
        <img src={avatar} alt={senderName} className="chat-message__avatar-img" />
      ) : (
        (avatar || senderName.slice(0, 2).toUpperCase())
      )

    return (
      <div
        ref={ref}
        className={['chat-message', `chat-message--${role}`, className]
          .filter(Boolean)
          .join(' ')}
        data-testid={`chat-message-${role}`}
        {...props}
      >
        <div className="chat-message__avatar">{avatarContent}</div>
        <div className="chat-message__content">
          <div className="chat-message__meta">
            <span className="chat-message__sender">{senderName}</span>
            {badge && <span className="chat-message__badge">{badge}</span>}
            <span className="chat-message__timestamp">{timestamp}</span>
          </div>
          <div className="chat-message__body">{body}</div>
          {thinkingBlock && <ThinkingBlock content={thinkingBlock.content} />}
          {toolBlock && (
            <ToolBlock
              name={toolBlock.name}
              status={toolBlock.status}
              output={toolBlock.output}
            />
          )}
        </div>
      </div>
    )
  }
)

ChatMessage.displayName = 'ChatMessage'

export interface ToolBlockProps extends React.HTMLAttributes<HTMLDivElement> {
  name: string
  status: 'running' | 'success' | 'error'
  output?: Array<{ key?: string; value: string }>
  defaultCollapsed?: boolean
  onToggleCollapsed?: (collapsed: boolean) => void
}

export const ToolBlock = React.forwardRef<HTMLDivElement, ToolBlockProps>(
  (
    {
      name,
      status,
      output = [],
      defaultCollapsed = false,
      onToggleCollapsed,
      className = '',
      ...props
    },
    ref
  ) => {
    const [isCollapsed, setIsCollapsed] = React.useState(defaultCollapsed)
    const outputId = React.useId()

    const handleToggle = React.useCallback(() => {
      const newCollapsed = !isCollapsed
      setIsCollapsed(newCollapsed)
      onToggleCollapsed?.(newCollapsed)
    }, [isCollapsed, onToggleCollapsed])

    const statusColor =
      status === 'running' ? 'amber' : status === 'success' ? 'emerald' : 'rose'

    return (
      <div
        ref={ref}
        className={['tool-block', className].filter(Boolean).join(' ')}
        data-testid="tool-block"
        {...props}
      >
        <button
          type="button"
          className="tool-block__header"
          onClick={handleToggle}
          aria-expanded={!isCollapsed}
          aria-controls={output.length > 0 ? outputId : undefined}
        >
          <Icon
            name={isCollapsed ? 'chevronRight' : 'chevronDown'}
            size={12}
            className="tool-block__toggle-icon"
          />
          <span className="tool-block__name">{name}</span>
          <span className={`tool-block__status tool-block__status--${statusColor}`}>
            {status === 'running' ? 'running' : status === 'success' ? 'success' : 'error'}
          </span>
        </button>
        {!isCollapsed && output.length > 0 && (
          <div id={outputId} className="tool-block__output">
            {output.map((item, idx) => (
              <div key={idx} className="tool-block__output-row">
                {item.key && <span className="tool-block__key">{item.key}</span>}
                <span className="tool-block__value">{item.value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }
)

ToolBlock.displayName = 'ToolBlock'

export interface ThinkingBlockProps extends React.HTMLAttributes<HTMLDivElement> {
  content: string
  label?: string
  defaultCollapsed?: boolean
  onToggleCollapsed?: (collapsed: boolean) => void
}

export const ThinkingBlock = React.forwardRef<HTMLDivElement, ThinkingBlockProps>(
  (
    {
      content,
      label = 'thinking',
      defaultCollapsed = false,
      onToggleCollapsed,
      className = '',
      ...props
    },
    ref
  ) => {
    const [isCollapsed, setIsCollapsed] = React.useState(defaultCollapsed)
    const contentId = React.useId()

    const handleToggle = React.useCallback(() => {
      const newCollapsed = !isCollapsed
      setIsCollapsed(newCollapsed)
      onToggleCollapsed?.(newCollapsed)
    }, [isCollapsed, onToggleCollapsed])

    return (
      <div
        ref={ref}
        className={['thinking-block', className].filter(Boolean).join(' ')}
        data-testid="thinking-block"
        {...props}
      >
        <button
          type="button"
          className="thinking-block__header"
          onClick={handleToggle}
          aria-expanded={!isCollapsed}
          aria-controls={!isCollapsed ? contentId : undefined}
        >
          <Icon
            name={isCollapsed ? 'chevronRight' : 'chevronDown'}
            size={12}
            className="thinking-block__toggle-icon"
          />
          <span className="thinking-block__label">{label}</span>
        </button>
        {!isCollapsed && (
          <div id={contentId} className="thinking-block__content">
            {content}
          </div>
        )}
      </div>
    )
  }
)

ThinkingBlock.displayName = 'ThinkingBlock'

export default ChatMessage
