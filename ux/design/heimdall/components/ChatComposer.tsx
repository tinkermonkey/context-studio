import React, { useRef, useEffect } from 'react'
import './ChatComposer.css'
import { Button } from './Button'
import { Icon } from './Icon'

const generateId = (): string => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `id-${Math.random().toString(36).slice(2, 11)}-${Date.now()}`
}

export interface ContextItem {
  id: string
  label: string
}

export interface Attachment {
  id: string
  name: string
  size?: number
}

export interface ChatComposerProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onChange' | 'onSubmit' | 'placeholder' | 'value'> {
  placeholder?: string
  value: string
  onChange: (value: string) => void
  onSubmit: (value: string, contextItems: ContextItem[]) => void
  onContextChange?: (items: ContextItem[]) => void
  onAttachmentChange?: (attachments: Attachment[]) => void
  scopeLabel?: string
  contextItems?: ContextItem[]
  attachments?: Attachment[]
  disabled?: boolean
  loading?: boolean
  label?: string
}

export const ChatComposer = React.forwardRef<HTMLDivElement, ChatComposerProps>(
  (
    {
      placeholder = 'Type a message...',
      value,
      onChange,
      onSubmit,
      onContextChange,
      onAttachmentChange,
      scopeLabel,
      contextItems = [],
      attachments = [],
      disabled = false,
      loading = false,
      label = 'Message',
      className,
      ...props
    },
    ref
  ) => {
    const textareaRef = useRef<HTMLTextAreaElement>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)

    useEffect(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
        const newHeight = Math.min(
          textareaRef.current.scrollHeight,
          200
        )
        textareaRef.current.style.height = `${newHeight}px`
      }
    }, [value])

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        if (value.trim() && !disabled && !loading) {
          onSubmit(value, contextItems)
        }
      }
    }

    const handleSubmit = () => {
      if (value.trim() && !disabled && !loading) {
        onSubmit(value, contextItems)
      }
    }

    const handleRemoveContext = (id: string) => {
      const updated = contextItems.filter((item) => item.id !== id)
      onContextChange?.(updated)
    }

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!e.target.files) return

      const files = Array.from(e.target.files)
      const newAttachments = files.map((file) => ({
        id: generateId(),
        name: file.name,
        size: file.size,
      }))

      const updated = [...attachments, ...newAttachments]
      onAttachmentChange?.(updated)

      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }

    const handleRemoveAttachment = (id: string) => {
      const updated = attachments.filter((item) => item.id !== id)
      onAttachmentChange?.(updated)
    }

    return (
      <div
        ref={ref}
        className={['chat-composer', disabled && 'chat-composer--disabled', className].filter(Boolean).join(' ')}
        {...props}
      >
        <div className="chat-composer__tools">
          {scopeLabel && (
            <span className="chat-composer__scope">
              talking to <b>{scopeLabel}</b>
            </span>
          )}
          {contextItems.map((item) => (
            <div key={item.id} className="chat-composer__context-pill">
              <span className="chat-composer__context-label">{item.label}</span>
              <button
                className="chat-composer__context-remove"
                onClick={() => handleRemoveContext(item.id)}
                aria-label={`Remove ${item.label}`}
                type="button"
              >
                <Icon name="x" size={10} />
              </button>
            </div>
          ))}
          {attachments.map((attachment) => (
            <div key={attachment.id} className="chat-composer__attachment-pill">
              <Icon name="paperclip" size={10} />
              <span className="chat-composer__attachment-label">{attachment.name}</span>
              <button
                className="chat-composer__attachment-remove"
                onClick={() => handleRemoveAttachment(attachment.id)}
                aria-label={`Remove ${attachment.name}`}
                type="button"
              >
                <Icon name="x" size={10} />
              </button>
            </div>
          ))}
        </div>

        <div className="chat-composer__input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-composer__input"
            placeholder={placeholder}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            disabled={disabled}
            aria-label={label}
          />

          <div className="chat-composer__footer">
            <div className="chat-composer__footer-start">
              <span className="chat-composer__hint">
                <b>↵</b> send · <b>⇧↵</b> newline
              </span>
            </div>
            <div className="chat-composer__footer-end">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileSelect}
                className="chat-composer__file-input"
                aria-label="Attach files"
              />
              <button
                className="chat-composer__attach-button"
                onClick={() => fileInputRef.current?.click()}
                type="button"
                aria-label="Attach files"
                disabled={disabled}
              >
                <Icon name="paperclip" size={12} />
              </button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSubmit}
                disabled={!value.trim() || disabled || loading}
              >
                <Icon name="send" size={12} />
                send
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }
)

ChatComposer.displayName = 'ChatComposer'

export default ChatComposer
