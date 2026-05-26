import React from 'react'
import './BarV.css'
import { SERIES_COLORS } from './chartColors'
import { TONE, fmt, type ChartTone } from './chartTone'

export interface BarVProps extends Omit<React.SVGAttributes<SVGSVGElement>, 'children' | 'values'> {
  values: number[]
  xLabels?: string[]
  /** Hex color. Defaults to amber (SERIES_COLORS[2]). */
  color?: string
  width?: number
  height?: number
  axes?: boolean
  grid?: boolean
  ticks?: number
  threshold?: { value: number; label?: string }
  tone?: ChartTone
  label?: string
  className?: string
  style?: React.CSSProperties
}

export const BarV = React.forwardRef<SVGSVGElement, BarVProps>(
  (
    {
      values,
      xLabels,
      color,
      width = 480,
      height = 200,
      axes = false,
      grid = false,
      ticks = 4,
      threshold,
      tone = 'light',
      label,
      className = '',
      style,
      ...rest
    },
    ref
  ) => {
    const T = TONE[tone]
    const c = color ?? SERIES_COLORS[2]

    const pad = { top: 8, right: 8, bottom: axes ? 22 : 6, left: axes ? 30 : 6 }
    const innerW = width - pad.left - pad.right
    const innerH = height - pad.top - pad.bottom

    if (!values || values.length === 0) return null

    const hi = Math.max(...values, threshold ? threshold.value : 0)
    const n = values.length
    const gap = Math.max(2, (innerW / n) * 0.22)
    const bw = (innerW - gap * (n - 1)) / n

    const yAt = (v: number) => pad.top + innerH - (v / (hi || 1)) * innerH
    const yTickVals: number[] = []
    for (let i = 0; i <= ticks; i++) yTickVals.push((i / ticks) * hi)

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
                {fmt(v)}
              </text>
            ))}
          </>
        )}

        {values.map((v, i) => {
          const x = pad.left + i * (bw + gap)
          const y = yAt(v)
          return (
            <g key={i}>
              <rect x={x} y={y} width={bw} height={pad.top + innerH - y} fill={c} rx="1" />
              {axes && xLabels && xLabels[i] !== undefined && (
                <text x={x + bw / 2} y={pad.top + innerH + 14}
                  textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="10" fill={T.fg3}>
                  {xLabels[i]}
                </text>
              )}
            </g>
          )
        })}

        {threshold && (
          <>
            <line x1={pad.left} x2={width - pad.right}
              y1={yAt(threshold.value)} y2={yAt(threshold.value)}
              stroke={T.fg3} strokeWidth="1" strokeDasharray="3 3" />
            {threshold.label && (
              <text x={width - pad.right - 4} y={yAt(threshold.value) - 4}
                textAnchor="end" fontFamily="JetBrains Mono, monospace" fontSize="9.5" fill={T.fg3}
                style={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {threshold.label}
              </text>
            )}
          </>
        )}
      </svg>
    )
  }
)

BarV.displayName = 'BarV'
export default BarV
