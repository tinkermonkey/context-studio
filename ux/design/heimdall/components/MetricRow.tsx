import React from 'react'
import { Sparkline, type SparklineColor } from './Sparkline'
import { ProgressBar } from './ProgressBar'
import './MetricRow.css'

export interface MetricRowProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string
  value: number | string
  unit?: string
  percent: number
  sparklineData?: number[]
  color?: SparklineColor
  progressLabel?: string
}

export const MetricRow = React.forwardRef<HTMLDivElement, MetricRowProps>(
  ({ label, value, unit, percent, sparklineData = [], color = 'emerald', progressLabel, className = '', 'aria-label': ariaLabel, ...rest }, ref) => {
    return (
      <div
        ref={ref}
        role="row"
        aria-label={ariaLabel ?? label}
        className={`metric-row ${className}`.trim()}
        {...rest}
      >
        <div className="metric-row__label">{label}</div>
        <div className="metric-row__progress">
          <ProgressBar percent={percent} color={color} height={6} label={progressLabel ?? label} />
        </div>
        <div className="metric-row__sparkline">
          <Sparkline data={sparklineData} width={60} height={18} color={color} />
        </div>
        <div className="metric-row__value">
          {value}
          {unit && <span className="metric-row__unit">{unit}</span>}
        </div>
      </div>
    )
  }
)

MetricRow.displayName = 'MetricRow'

export default MetricRow
