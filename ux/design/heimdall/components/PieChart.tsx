import React from 'react'
import './PieChart.css'
import { SERIES_COLORS } from './chartColors'
import { TONE, type ChartTone } from './chartTone'

export interface PieChartSegment {
  name: string
  value: number
  color?: string
}

export interface PieChartProps extends React.HTMLAttributes<HTMLDivElement> {
  segments: PieChartSegment[]
  legend?: boolean
  width?: number
  height?: number
  tone?: ChartTone
  'aria-label'?: string
}

export const PieChart = React.forwardRef<HTMLDivElement, PieChartProps>(
  (
    {
      segments,
      legend = false,
      width = 200,
      height = 200,
      tone = 'light',
      'aria-label': ariaLabel,
      className = '',
      ...rest
    },
    ref
  ) => {
    const T = TONE[tone]

    const slices = React.useMemo(() => {
      if (!segments || segments.length === 0) return null

      const valid = segments.filter((s) => {
        const n = Number(s.value)
        return isFinite(n) && n > 0
      })

      if (valid.length === 0) return null

      let total = 0
      for (const s of valid) total += Number(s.value)

      const svgSize = 100
      const cx = svgSize / 2
      const cy = svgSize / 2
      const r = svgSize / 2 - 5

      const polarToCartesian = (angle: number) => ({
        x: cx + r * Math.cos(angle),
        y: cy + r * Math.sin(angle),
      })

      const createArcPath = (startAngle: number, endAngle: number) => {
        const start = polarToCartesian(startAngle)
        const end = polarToCartesian(endAngle)
        const largeArc = endAngle - startAngle > Math.PI ? 1 : 0
        return [
          `M ${cx} ${cy}`,
          `L ${start.x} ${start.y}`,
          `A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`,
          'Z',
        ].join(' ')
      }

      let currentAngle = -Math.PI / 2
      return valid.map((segment, idx) => {
        const numValue = Number(segment.value)
        const sliceAngle = (numValue / total) * 2 * Math.PI
        const endAngle = currentAngle + sliceAngle
        const percentage = (numValue / total) * 100
        const d = createArcPath(currentAngle, endAngle)
        currentAngle = endAngle
        return {
          d,
          color: segment.color ?? SERIES_COLORS[idx % SERIES_COLORS.length],
          value: numValue,
          name: segment.name,
          percentage,
        }
      })
    }, [segments])

    if (!slices) return null

    return (
      <div ref={ref} className={`pie-chart${className ? ` ${className}` : ''}`} {...rest}>
        <svg
          role="img"
          aria-label={ariaLabel ?? 'Pie chart'}
          viewBox="0 0 100 100"
          width={width}
          height={height}
          style={{ overflow: 'visible', display: 'block' }}
        >
          {slices.map((slice, idx) => (
            <path
              key={`slice-${idx}`}
              d={slice.d}
              fill={slice.color}
              stroke={T.inset}
              strokeWidth="1"
            />
          ))}
        </svg>

        {legend && (
          <div className="pie-chart__legend" style={{ color: T.fg2 }}>
            {slices.map((slice, idx) => (
              <div key={`legend-${idx}`} className="pie-chart__legend-item">
                <div
                  className="pie-chart__legend-swatch"
                  style={{ backgroundColor: slice.color }}
                />
                <span>
                  {slice.name} ({slice.percentage.toFixed(1)}%)
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }
)

PieChart.displayName = 'PieChart'

export default PieChart
