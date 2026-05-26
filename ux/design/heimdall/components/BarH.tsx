import React from 'react'
import './BarH.css'
import { SERIES_COLORS } from './chartColors'
import { TONE, fmt, type ChartTone } from './chartTone'

export interface BarHItem {
  label: string
  value: number
  color?: string
}

export interface BarHProps extends Omit<React.SVGAttributes<SVGSVGElement>, 'children'> {
  items: BarHItem[]
  width?: number
  height?: number
  tone?: ChartTone
  showValues?: boolean
  valueFormat?: (value: number) => string
  maxValue?: number
  label?: string
  className?: string
  style?: React.CSSProperties
}

export const BarH = React.forwardRef<SVGSVGElement, BarHProps>(
  (
    {
      items,
      width = 320,
      height = 200,
      tone = 'light',
      showValues = true,
      valueFormat,
      maxValue,
      label,
      className = '',
      style,
      ...rest
    },
    ref
  ) => {
    const T = TONE[tone]

    const pad = { top: 4, right: 36, bottom: 4, left: 92 }
    const innerW = width - pad.left - pad.right
    const innerH = height - pad.top - pad.bottom

    if (!items || items.length === 0) return null

    const hi = maxValue ?? Math.max(...items.map(it => it.value))
    const rowH = innerH / items.length
    const barH = Math.min(rowH * 0.62, 14)
    const formatValue = valueFormat ?? fmt

    return (
      <svg
        ref={ref}
        role="img"
        aria-label={label ?? 'Horizontal bar chart'}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className={className}
        style={{ display: 'block', ...style }}
        {...rest}
      >
        {items.map((it, i) => {
          const y = pad.top + i * rowH + (rowH - barH) / 2
          const w = (it.value / (hi || 1)) * innerW
          const c = it.color ?? SERIES_COLORS[i % SERIES_COLORS.length]
          return (
            <g key={it.label}>
              <text x={pad.left - 10} y={y + barH * 0.78}
                textAnchor="end" fontFamily="JetBrains Mono, monospace" fontSize="11" fill={T.fg2}>
                {it.label}
              </text>
              <rect x={pad.left} y={y} width={innerW} height={barH} fill={T.inset} rx="2" />
              <rect x={pad.left} y={y} width={w} height={barH} fill={c} rx="2" />
              {showValues && (
                <text x={pad.left + w + 6} y={y + barH * 0.78}
                  fontFamily="JetBrains Mono, monospace" fontSize="11" fill={T.fg2} fontWeight="500">
                  {formatValue(it.value)}
                </text>
              )}
            </g>
          )
        })}
      </svg>
    )
  }
)

BarH.displayName = 'BarH'
export default BarH
