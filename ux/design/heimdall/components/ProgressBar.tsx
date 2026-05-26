import React from 'react'
import './ProgressBar.css'
import type { StatusColor } from './statusColors'

export type ProgressBarColor = StatusColor

export interface ProgressBarProps extends React.HTMLAttributes<HTMLDivElement> {
  percent: number
  color?: ProgressBarColor
  height?: number
  label?: string
}

export const ProgressBar = React.forwardRef<HTMLDivElement, ProgressBarProps>(
  ({ percent, color = 'emerald', height = 6, label, className = '', ...rest }, ref) => {
    const clampedPercent = Number.isNaN(percent) ? 0 : Math.min(Math.max(percent, 0), 100)
    const colorClass = `progress-bar--${color}`

    return (
      <div
        ref={ref}
        className={`progress-bar ${colorClass} ${className}`.trim()}
        style={{ height: `${height}px` }}
        role="progressbar"
        aria-valuenow={clampedPercent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        {...rest}
      >
        <div className="progress-bar__fill" style={{ width: `${clampedPercent}%` }} />
      </div>
    )
  }
)

ProgressBar.displayName = 'ProgressBar'

export default ProgressBar
