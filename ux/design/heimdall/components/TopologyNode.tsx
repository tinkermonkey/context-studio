import React from 'react'
import './TopologyNode.css'
import type { StatusColor } from './statusColors'

export type TopologyNodeStatus = 'ok' | 'warning' | 'error' | 'idle'

export interface TopologyNodeMetric {
  label: string
  value: number | string
  unit?: string
  percent: number
  sparklineData: number[]
  color?: StatusColor
}

export interface TopologyNodeProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'role'> {
  title: string
  nodeRole?: string
  status?: TopologyNodeStatus
  metrics?: TopologyNodeMetric[]
  selected?: boolean
  x?: number
  y?: number
  onSelect?: () => void
}

const statusDotColorMap: Record<TopologyNodeStatus, string> = {
  ok: 'rgb(var(--status-emerald))',
  warning: 'rgb(var(--status-amber))',
  error: 'rgb(var(--status-rose))',
  idle: 'rgb(var(--status-neutral))',
}

export const TopologyNode = React.forwardRef<HTMLDivElement, TopologyNodeProps>(
  (
    { title, nodeRole = '', status = 'idle', metrics = [], selected = false, x, y, onSelect, className = '', style: userStyle, ...props },
    ref
  ) => {
    const classNames = [
      'topology-node',
      `topology-node--${status}`,
      selected ? 'topology-node--selected' : '',
      onSelect ? 'topology-node--interactive' : '',
      className,
    ]
      .filter(Boolean)
      .join(' ')

    const style = {
      ...(x !== undefined && y !== undefined
        ? {
            position: 'absolute' as const,
            left: `${x}px`,
            top: `${y}px`,
          }
        : {}),
      ...userStyle,
    }

    const slugTitle = title.replace(/\s+/g, '-').toLowerCase()

    const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (onSelect && (e.key === 'Enter' || e.key === ' ')) {
        e.preventDefault()
        onSelect()
      }
    }

    return (
      <div
        ref={ref}
        className={classNames}
        style={style}
        data-testid={`topology-node-${slugTitle}`}
        onClick={onSelect}
        onKeyDown={handleKeyDown}
        tabIndex={onSelect ? 0 : undefined}
        aria-selected={selected}
        role={onSelect ? 'button' : undefined}
        {...props}
      >
        <div className="topology-node__head">
          <div className="topology-node__title">{title}</div>
          <div
            className="topology-node__status-dot"
            style={{ backgroundColor: statusDotColorMap[status] }}
            data-testid={`topology-status-${slugTitle}`}
            aria-label={`Status: ${status}`}
          />
        </div>

        <div className="topology-node__role" data-testid={`topology-role-${slugTitle}`}>
          {nodeRole}
        </div>

        {metrics.length > 0 && (
          <div className="topology-node__metrics" data-testid={`topology-metrics-${slugTitle}`}>
            {metrics.map((metric, idx) => (
              <div key={idx} className="topology-node__metric-row">
                <div className="topology-node__metric-label">{metric.label}</div>
                <div className="topology-node__metric-value">
                  {metric.value}
                  {metric.unit && <span className="topology-node__metric-unit">{metric.unit}</span>}
                </div>
                <div className="topology-node__metric-bar">
                  <div
                    className="topology-node__metric-fill"
                    style={{
                      width: `${Number.isFinite(metric.percent) ? Math.max(0, Math.min(100, metric.percent)) : 0}%`,
                      backgroundColor: metric.color ? `rgb(var(--status-${metric.color}))` : 'rgb(var(--accent-primary))',
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }
)

TopologyNode.displayName = 'TopologyNode'

export default TopologyNode
