import React from 'react'
import { Badge } from './Badge'
import type { StatusColor } from './statusColors'
import { statusColorMap } from './statusColors'
import './ActivityTimeline.css'

export type ActivityEventType = 'create' | 'update' | 'delete' | 'run'

export interface ActivityEvent {
  id: string
  type: ActivityEventType
  subject: string
  timestamp: Date | string
  kind?: string
  kindLabel?: string
  dotColor?: StatusColor
  headline?: React.ReactNode
  meta?: string
  onClick?: (event: ActivityEvent) => void
}

export interface ActivityTimelineProps extends React.HTMLAttributes<HTMLDivElement> {
  events?: ActivityEvent[]
  emptyState?: string
}

const EVENT_COLOR_MAP: Record<ActivityEventType, 'emerald' | 'cyan' | 'rose' | 'amber'> = {
  create: 'emerald',
  update: 'cyan',
  delete: 'rose',
  run: 'amber',
}

const formatTimestamp = (timestamp: Date | string): string => {
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()

  if (Number.isNaN(diffMs)) {
    return ''
  }

  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString()
}

export const ActivityTimeline = React.forwardRef<HTMLDivElement, ActivityTimelineProps>(
  ({ events = [], emptyState = 'No activity recorded', className = '', ...props }, ref) => {
    const classNames = ['activity-timeline', className].filter(Boolean).join(' ')

    if (events.length === 0) {
      return (
        <div ref={ref} className={classNames} data-testid="activity-timeline" {...props}>
          <div className="activity-timeline__empty" data-testid="activity-timeline-empty">
            {emptyState}
          </div>
        </div>
      )
    }

    return (
      <div ref={ref} className={classNames} data-testid="activity-timeline" {...props}>
        <div className="activity-timeline__list">
          {events.map(event => (
            <div
              key={event.id}
              className={['activity-timeline__event', event.onClick ? 'activity-timeline__event--clickable' : ''].filter(Boolean).join(' ')}
              data-testid={`activity-event-${event.id}`}
              {...(event.kind && { 'data-kind': event.kind })}
              {...(event.onClick && {
                role: 'button',
                tabIndex: 0,
                onClick: () => event.onClick!(event),
                onKeyDown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); event.onClick!(event) } },
              })}
            >
              <div className="activity-timeline__dot-container">
                {event.dotColor ? (
                  <div
                    className="activity-timeline__dot--custom"
                    style={{ backgroundColor: statusColorMap[event.dotColor] }}
                    data-testid={`activity-dot-custom-${event.id}`}
                  />
                ) : (
                  <Badge color={EVENT_COLOR_MAP[event.type]} className="activity-timeline__dot" data-testid={`activity-dot-${event.type}`} />
                )}
              </div>
              <div className="activity-timeline__content">
                <div className="activity-timeline__header">
                  {event.kind && (
                    <span className="activity-timeline__kind-label" data-testid={`activity-kind-tag-${event.id}`}>
                      {event.kindLabel || event.kind}
                    </span>
                  )}
                  <div className="activity-timeline__subject" data-testid="activity-subject">
                    {event.headline || event.subject}
                  </div>
                </div>
                {event.meta && (
                  <div className="activity-timeline__meta" data-testid="activity-meta">
                    {event.meta}
                  </div>
                )}
                <div className="activity-timeline__timestamp" data-testid="activity-timestamp">
                  {formatTimestamp(event.timestamp)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }
)

ActivityTimeline.displayName = 'ActivityTimeline'

export default ActivityTimeline
