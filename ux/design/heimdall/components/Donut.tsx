import React from 'react'
import './Donut.css'
import { SERIES_COLORS } from './chartColors'
import { TONE, type ChartTone } from './chartTone'

export interface DonutSlice {
  value: number
  color?: string
}

export interface DonutProps extends Omit<React.SVGAttributes<SVGSVGElement>, 'children'> {
  slices: DonutSlice[]
  /** Hex colors per slice. Defaults to SERIES_COLORS. */
  colors?: string[]
  width?: number
  height?: number
  /** Ring width in pixels (default 14) */
  thickness?: number
  /** Gap in radians between slices (default 0.03) */
  gap?: number
  /** Bold number in the ring center */
  centerValue?: string
  /** Mono label below center value */
  centerLabel?: string
  /** Accessible label for the chart. Defaults to "Donut chart". */
  'aria-label'?: string
  tone?: ChartTone
  className?: string
  style?: React.CSSProperties
}

export const Donut = React.forwardRef<SVGSVGElement, DonutProps>(
  (
    {
      slices,
      colors,
      width = 160,
      height = 160,
      thickness = 14,
      gap = 0.03,
      centerValue,
      centerLabel,
      'aria-label': ariaLabel,
      tone = 'light',
      className = '',
      style,
      ...rest
    },
    ref
  ) => {
    const T = TONE[tone]
    const cs = colors ?? SERIES_COLORS

    if (!slices || slices.length === 0) return null

    const cx = width / 2
    const cy = height / 2
    const r = Math.min(width, height) / 2 - 4
    const ri = r - thickness
    const total = slices.reduce((a, s) => a + s.value, 0) || 1

    function arc(a0: number, a1: number): string {
      const cos0 = Math.cos(a0), sin0 = Math.sin(a0)
      const cos1 = Math.cos(a1), sin1 = Math.sin(a1)
      const large = a1 - a0 > Math.PI ? 1 : 0
      return [
        `M ${cx + r * cos0} ${cy + r * sin0}`,
        `A ${r} ${r} 0 ${large} 1 ${cx + r * cos1} ${cy + r * sin1}`,
        `L ${cx + ri * cos1} ${cy + ri * sin1}`,
        `A ${ri} ${ri} 0 ${large} 0 ${cx + ri * cos0} ${cy + ri * sin0}`,
        'Z',
      ].join(' ')
    }

    const effectiveGap = slices.length > 1 ? gap : 0
    let acc = -Math.PI / 2
    const arcs = slices.map((s, i) => {
      const span = (s.value / total) * Math.PI * 2
      const a0 = acc + effectiveGap / 2
      let a1 = acc + span - effectiveGap / 2
      if (a1 - a0 >= Math.PI * 2 - 1e-6) a1 = a0 + Math.PI * 2 - 1e-6
      if (a1 <= a0) a1 = a0 + 1e-4
      acc += span
      return { d: arc(a0, a1), color: s.color ?? cs[i % cs.length] }
    })

    const valFontSize = Math.min(width, height) * 0.22
    const labelY = cy + Math.min(width, height) * 0.18

    return (
      <svg
        ref={ref}
        role="img"
        aria-label={ariaLabel ?? 'Donut chart'}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className={className}
        style={{ display: 'block', ...style }}
        {...rest}
      >
        {arcs.map((a, i) => (
          <path key={i} d={a.d} fill={a.color} />
        ))}
        {centerValue != null && (
          <text x={cx} y={cy + 1} textAnchor="middle"
            fontFamily="Inter, sans-serif" fontSize={valFontSize} fontWeight="700"
            fill={T.fg1} style={{ letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>
            {centerValue}
          </text>
        )}
        {centerLabel != null && (
          <text x={cx} y={labelY} textAnchor="middle"
            fontFamily="JetBrains Mono, monospace" fontSize="10" fill={T.fg3}
            style={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            {centerLabel}
          </text>
        )}
      </svg>
    )
  }
)

Donut.displayName = 'Donut'
export default Donut
