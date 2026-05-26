import React from 'react'
import './LineChart.css'
import { SERIES_COLORS } from './chartColors'
import { TONE, fmt, type ChartTone } from './chartTone'

const ACCENT_PRIMARY = '#F59E0B'
const ACCENT_PRIMARY_DEEP = '#B45309'

export interface ThresholdLine {
  value: number
  label?: string
}

export interface EventMarker {
  /** Index into series data array */
  x: number
  label?: string
}

export interface LineChartProps extends Omit<React.SVGAttributes<SVGSVGElement>, 'children'> {
  /** Each inner array is one series: [v0, v1, …] */
  series: number[][]
  /** Hex color per series. Defaults to canonical SERIES_COLORS. */
  colors?: string[]
  xLabels?: string[]
  width?: number
  height?: number
  /** Gradient area fill beneath each line */
  area?: boolean
  /** Show y-axis and x-axis lines + tick labels */
  axes?: boolean
  /** Show horizontal grid lines */
  grid?: boolean
  /** Number of y-axis ticks (default 4) */
  ticks?: number
  threshold?: ThresholdLine
  markers?: EventMarker[]
  /** Feature-tier hover tooltip */
  tooltip?: boolean
  tone?: ChartTone
  padding?: { top?: number; right?: number; bottom?: number; left?: number }
}

export const LineChart = React.forwardRef<SVGSVGElement, LineChartProps>(
  (
    {
      series,
      colors,
      xLabels,
      width = 480,
      height = 200,
      area = false,
      axes = false,
      grid = false,
      ticks = 4,
      threshold,
      markers,
      tooltip = false,
      tone = 'light',
      padding: paddingOverride,
      className = '',
      style,
      ...rest
    },
    ref
  ) => {
    const T = TONE[tone]
    const gradBaseId = React.useId()
    const cs = colors ?? (series.length === 1 ? [SERIES_COLORS[0]] : SERIES_COLORS)

    const pad = {
      top: 8,
      right: tooltip ? 12 : 8,
      bottom: axes ? 22 : 6,
      left: axes ? 30 : 6,
      ...paddingOverride,
    }

    const innerW = width - pad.left - pad.right
    const innerH = height - pad.top - pad.bottom

    const flat = series.flat()
    if (flat.length === 0) return null

    let lo = Math.min(...flat)
    let hi = Math.max(...flat)
    const span = hi - lo || 1
    lo -= span * 0.08
    hi += span * 0.08
    if (threshold) {
      lo = Math.min(lo, threshold.value)
      hi = Math.max(hi, threshold.value)
    }

    const n = Math.max(...series.map(s => s.length))
    const xAt = (i: number) =>
      pad.left + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW)
    const yAt = (v: number) =>
      pad.top + innerH - ((v - lo) / (hi - lo)) * innerH

    const yTickVals: number[] = []
    for (let i = 0; i <= ticks; i++) yTickVals.push(lo + (i / ticks) * (hi - lo))

    const [hover, setHover] = React.useState<number | null>(null)

    function onMove(e: React.MouseEvent<SVGSVGElement>) {
      const rect = e.currentTarget.getBoundingClientRect()
      const px = ((e.clientX - rect.left) / rect.width) * width
      const idx = Math.max(0, Math.min(n - 1, Math.round(((px - pad.left) / innerW) * (n - 1))))
      setHover(idx)
    }

    function makeLine(pts: [number, number][]): string {
      return pts.map(([x, y], i) => (i ? 'L' : 'M') + x.toFixed(2) + ',' + y.toFixed(2)).join(' ')
    }

    const seriesPts = series.map(s => s.map((v, i) => [xAt(i), yAt(v)] as [number, number]))

    return (
      <svg
        ref={ref}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className={className}
        role="img"
        aria-label={rest['aria-label'] ?? 'Line chart'}
        style={{ display: 'block', cursor: tooltip ? 'crosshair' : 'default', ...style }}
        onMouseMove={tooltip ? onMove : undefined}
        onMouseLeave={tooltip ? () => setHover(null) : undefined}
        {...rest}
      >
        {/* gridlines */}
        {grid && yTickVals.map((v, i) => (
          <line key={'g' + i}
            x1={pad.left} x2={width - pad.right} y1={yAt(v)} y2={yAt(v)}
            stroke={T.grid} strokeWidth="1" />
        ))}

        {/* axes */}
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
            {xLabels && xLabels.map((lab, i) => (
              <text key={'xt' + i} x={xAt(i)} y={pad.top + innerH + 14}
                textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="10" fill={T.fg3}>
                {lab}
              </text>
            ))}
          </>
        )}

        {/* threshold */}
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

        {/* event markers */}
        {markers && markers.map((m, i) => (
          <g key={'mk' + i}>
            <line x1={xAt(m.x)} x2={xAt(m.x)} y1={pad.top - 2} y2={pad.top + innerH}
              stroke={ACCENT_PRIMARY} strokeWidth="1" strokeDasharray="2 2" />
            <circle cx={xAt(m.x)} cy={pad.top + 4} r="3" fill={ACCENT_PRIMARY} />
            {m.label && (
              <text x={xAt(m.x) + 6} y={pad.top + 7}
                fontFamily="JetBrains Mono, monospace" fontSize="9.5" fill={ACCENT_PRIMARY_DEEP}
                style={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {m.label}
              </text>
            )}
          </g>
        ))}

        {/* area + line per series */}
        {seriesPts.map((pts, si) => {
          const c = cs[si % cs.length]
          const line = makeLine(pts)
          const fillPath = `${line} L${pts[pts.length - 1][0].toFixed(2)},${pad.top + innerH} L${pts[0][0].toFixed(2)},${pad.top + innerH} Z`
          const gradId = `${gradBaseId}-lg${si}`
          return (
            <g key={'s' + si}>
              {area && (
                <>
                  <defs>
                    <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={c} stopOpacity="0.22" />
                      <stop offset="100%" stopColor={c} stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  <path d={fillPath} fill={`url(#${gradId})`} />
                </>
              )}
              <path d={line} stroke={c} strokeWidth={tooltip ? 1.75 : 1.5}
                fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </g>
          )
        })}

        {/* tooltip */}
        {tooltip && hover !== null && (() => {
          const tw = 132
          const th = 18 + series.length * 16
          let tx = xAt(hover) + 10
          if (tx + tw > width - 4) tx = xAt(hover) - tw - 10
          const ty = pad.top + 4
          return (
            <g>
              <line x1={xAt(hover)} x2={xAt(hover)} y1={pad.top} y2={pad.top + innerH}
                stroke={T.fg3} strokeWidth="1" strokeDasharray="2 3" />
              {series.map((s, si) => s[hover] != null && (
                <circle key={'h' + si} cx={xAt(hover)} cy={yAt(s[hover])} r="3"
                  fill={T.card}
                  stroke={cs[si % cs.length]} strokeWidth="1.75" />
              ))}
              <rect x={tx} y={ty} width={tw} height={th} rx="6"
                fill={T.card} fillOpacity="0.96" stroke={T.border} />
              <text x={tx + 9} y={ty + 13}
                fontFamily="JetBrains Mono, monospace" fontSize="9.5" fill={T.fg3}
                style={{ textTransform: 'uppercase', letterSpacing: '0.10em' }}>
                {xLabels ? xLabels[hover] : `t${hover}`}
              </text>
              {series.map((s, si) => (
                <g key={'tt' + si}>
                  <rect x={tx + 9} y={ty + 22 + si * 16} width="6" height="6" rx="1"
                    fill={cs[si % cs.length]} />
                  <text x={tx + 20} y={ty + 28 + si * 16}
                    fontFamily="JetBrains Mono, monospace" fontSize="10.5" fill={T.fg1}>
                    {s[hover] != null ? fmt(s[hover]) : '—'}
                  </text>
                </g>
              ))}
            </g>
          )
        })()}
      </svg>
    )
  }
)

LineChart.displayName = 'LineChart'
export default LineChart
