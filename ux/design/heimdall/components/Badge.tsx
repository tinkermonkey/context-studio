import React from 'react'
import './Badge.css'
import type { StatusColor } from './statusColors'

export type BadgeColor = StatusColor

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  color?: BadgeColor
  pulse?: boolean
}

export interface StatusBadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  color?: BadgeColor
  pulse?: boolean
}

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ color = 'cyan', pulse = false, className = '', ...props }, ref) => {
    const classNames = ['badge', `badge--${color}`, pulse && 'badge--pulse', className]
      .filter(Boolean)
      .join(' ')

    return (
      <span
        ref={ref}
        className={classNames}
        {...props}
      />
    )
  }
)

Badge.displayName = 'Badge'

export const StatusBadge = React.forwardRef<HTMLDivElement, StatusBadgeProps>(
  ({ color = 'cyan', pulse = false, className = '', role = 'img', ...props }, ref) => {
    const classNames = ['status-badge', `status-badge--${color}`, pulse && 'status-badge--pulse', className]
      .filter(Boolean)
      .join(' ')

    return (
      <div
        ref={ref}
        role={role}
        className={classNames}
        {...props}
      />
    )
  }
)

StatusBadge.displayName = 'StatusBadge'

export default Badge
