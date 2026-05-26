import React from 'react'
import './StackedBar.css'
import { SERIES_COLORS } from './chartColors'
import { TONE, fmt, type ChartTone } from './chartTone'

export interface StackedBarStack {
  label: string
  parts: number[]
}

export interface StackedBarProps extends Omit<React.SVGAttributes<SVGSVGElement>, 'children'> {
  stacks: StackedBarStack[]
  colors?: string[]
  width?: number
  height?: number
  axes?: boolean
  grid?: boolean
  ticks?: number
  normalized?: boolean
  tone?: ChartTone
  label?: string
  className?: string
  style?: React.CSSProperties
}

export const StackedBar = React.forwardRef<SVGSVGElement, StackedBarProps>(
  (
    {
      stacks,
      colors,
      width = 480,
      height = 200,
      axes = false,
      grid = false,
      ticks = 4,
      normalized = false,
      tone = 'light',
      label = 'Stacked bar chart',
      className = '',
      style,
      ...rest
    },
    ref
  ) => {
    const T = TONE[tone]
    const cs = colors ?? SERIES_COLORS

    const pad = { top: 8, right: 8, bottom: axes ? 22 : 6, left: axes ? 30 : 6 }
    const innerW = width - pad.left - pad.right
    const innerH = height - pad.top - pad.bottom

    if (!stacks || stacks.length === 0) return null

    const totals = stacks.map(s => s.parts.reduce((a, b) => a + b, 0))
    const hi = normalized ? 1 : Math.max(...totals)
    const n = stacks.length
    const gap = Math.max(2, (innerW / n) * 0.22)
    const bw = (innerW - gap * (n - 1)) / n

    const yTickVals: number[] = []
    for (let i = 0; i <= ticks; i++) yTickVals.push((i / ticks) * hi)
    const yAt = (v: number) => pad.top + innerH - (v / (hi || 1)) * innerH

    return (
      <svg
        ref={ref}
        role="img"
        aria-label={label}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className={className}
        style={{ display: 'block', ...style }}
        {...rest}
      >
        {grid && yTickVals.map((v, i) => (
          <line key={'g' + i}
            x1={pad.left} x2={width - pad.right} y1={yAt(v)} y2={yAt(v)}
            stroke={T.grid} strokeWidth="1" />
        ))}

        {axes && (
          <>
            <line x1={pad.left} x2={pad.left} y1={pad.top} y2={pad.top + innerH}
              stroke={T.border} strokeWidth="1" />
            <line x1={pad.left} x2={width - pad.right} y1={pad.top + innerH} y2={pad.top + innerH}
              stroke={T.border} strokeWidth="1" />
            {yTickVals.map((v, i) => (
              <text key={'yt' + i} x={pad.left - 6} y={yAt(v) + 3}
                textAnchor="end" fontFamily="JetBrains Mono, monospace" fontSize="10" fill={T.fg3}>
                {normalized ? `${Math.round(v * 100)}%` : fmt(v)}
              </text>
            ))}
          </>
        )}

        {stacks.map((s, si) => {
          const x = pad.left + si * (bw + gap)
          const total = totals[si] || 1
          let acc = 0
          return (
            <g key={si}>
              {s.parts.map((p, pi) => {
                const v = normalized ? p / total : p
                const ph = (v / (hi || 1)) * innerH
                const y = pad.top + innerH - acc - ph
                acc += ph
                return <rect key={pi} x={x} y={y} width={bw} height={ph} fill={cs[pi % cs.length]} />
              })}
              {axes && (
                <text x={x + bw / 2} y={pad.top + innerH + 14}
                  textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="10" fill={T.fg3}>
                  {s.label}
                </text>
              )}
            </g>
          )
        })}
      </svg>
    )
  }
)

StackedBar.displayName = 'StackedBar'
export default StackedBar
