import React from 'react'
import './StatTile.css'
import { Icon, type IconName } from './Icon'
import { Sparkline } from './Sparkline'
import type { StatusColor } from './statusColors'

export interface StatTileProps extends React.HTMLAttributes<HTMLDivElement> {
  label?: string
  value?: string | number
  delta?: {
    value: number
    label?: string
    direction?: 'up' | 'down'
  }
  color?: StatusColor
  icon?: IconName
  sparkData?: number[]
  meta?: React.ReactNode
  metaIcon?: IconName
}

export const StatTile = React.forwardRef<HTMLDivElement, StatTileProps>(
  (
    {
      label = '',
      value = '',
      delta,
      color = 'cyan',
      icon,
      sparkData,
      meta,
      metaIcon,
      className = '',
      'aria-label': ariaLabel,
      ...props
    },
    ref
  ) => {
    const colorClass = `stat-tile--${color}`
    const classNames = ['stat-tile', colorClass, className]
      .filter(Boolean)
      .join(' ')

    return (
      <div ref={ref} className={classNames} aria-label={ariaLabel ?? `${label}: ${value}`} {...props}>
        <div className="stat-tile__header">
          <div className="stat-tile__label">{label}</div>
          {icon && <Icon name={icon} size={14} aria-hidden="true" />}
        </div>
        <div className="stat-tile__value">{value}</div>
        {(delta || meta) && (
          <div className="stat-tile__footer">
            {delta && (
              <span className={`stat-tile__delta stat-tile__delta--${delta.direction || 'up'}`}>
                <span className="stat-tile__delta-value">
                  {delta.direction === 'down' ? '−' : '+'}
                  {Math.abs(delta.value)}
                </span>
                {delta.label && <span className="stat-tile__delta-label">{delta.label}</span>}
              </span>
            )}
            {meta && (
              <div className="stat-tile__meta">
                {metaIcon && <Icon name={metaIcon} size={12} aria-hidden="true" />}
                <span className="stat-tile__meta-text">{meta}</span>
              </div>
            )}
          </div>
        )}
        {sparkData && (
          <div className="stat-tile__sparkline">
            <Sparkline data={sparkData} width={88} height={28} color={color || 'cyan'} />
          </div>
        )}
      </div>
    )
  }
)

StatTile.displayName = 'StatTile'

export default StatTile
