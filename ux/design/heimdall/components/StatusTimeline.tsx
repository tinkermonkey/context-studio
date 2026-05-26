import React from 'react'
import './StatusTimeline.css'
import { TONE, type ChartTone } from './chartTone'

export type SegmentKind = 'ok' | 'warn' | 'error' | 'idle' | 'info'

export interface StatusSegment {
  start: number
  end: number
  kind: SegmentKind | string
}

export interface StatusTrack {
  label: string
  segments: StatusSegment[]
}

export interface StatusTimelineProps extends Omit<React.SVGAttributes<SVGSVGElement>, 'children'> {
  tracks: StatusTrack[]
  range?: [number, number]
  width?: number
  height?: number
  axes?: boolean
  xLabels?: string[]
  marker?: { x: number; label?: string }
  tone?: ChartTone
  'aria-label'?: string
  className?: string
  style?: React.CSSProperties
}

const KIND_COLORS: Record<SegmentKind, string> = {
  ok:    '#10B981',
  warn:  '#F59E0B',
  error: '#F43F5E',
  idle:  '',          // filled per tone at render time
  info:  '#22D3EE',
}

export const StatusTimeline = React.forwardRef<SVGSVGElement, StatusTimelineProps>(
  (
    {
      tracks,
      range = [0, 100],
      width = 480,
      height = 160,
      axes = false,
      xLabels,
      marker,
      tone = 'light',
      'aria-label': ariaLabel,
      className = '',
      style,
      ...rest
    },
    ref
  ) => {
    const T = TONE[tone]

    if (!tracks || tracks.length === 0) return null

    const pad = { top: 6, right: 8, bottom: axes ? 22 : 6, left: 92 }
    const innerW = width - pad.left - pad.right
    const innerH = height - pad.top - pad.bottom
    const rowH = innerH / tracks.length
    const barH = Math.min(rowH * 0.60, 14)

    const xAt = (v: number) =>
      pad.left + ((v - range[0]) / (range[1] - range[0] || 1)) * innerW

    function kindColor(kind: string): string {
      if (kind === 'idle') return T.inset
      return KIND_COLORS[kind as SegmentKind] ?? kind
    }

    return (
      <svg
        ref={ref}
        role="img"
        aria-label={ariaLabel}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className={className}
        style={{ display: 'block', ...style }}
        {...rest}
      >
        {tracks.map((t, i) => {
          const y = pad.top + i * rowH + (rowH - barH) / 2
          return (
            <g key={i}>
              <text x={pad.left - 10} y={y + barH * 0.78}
                textAnchor="end" fontFamily="JetBrains Mono, monospace" fontSize="11" fill={T.fg2}>
                {t.label}
              </text>
              {/* inset track */}
              <rect x={pad.left} y={y} width={innerW} height={barH} fill={T.inset} rx="2" />
              {t.segments.map((s, si) => (
                <rect key={si}
                  x={xAt(s.start)} y={y}
                  width={Math.max(2, xAt(s.end) - xAt(s.start))}
                  height={barH}
                  fill={kindColor(s.kind)}
                  rx="2" />
              ))}
            </g>
          )
        })}

        {axes && xLabels && xLabels.map((lab, i) => (
          <text key={'x' + i}
            x={pad.left + (i / (xLabels.length - 1)) * innerW}
            y={pad.top + innerH + 14}
            textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="10" fill={T.fg3}>
            {lab}
          </text>
        ))}

        {marker && (
          <>
            <line x1={xAt(marker.x)} x2={xAt(marker.x)}
              y1={pad.top - 2} y2={pad.top + innerH + 2}
              stroke={KIND_COLORS.warn} strokeWidth="1" strokeDasharray="2 2" />
            <circle cx={xAt(marker.x)} cy={pad.top - 2} r="3" fill={KIND_COLORS.warn} />
            {marker.label && (
              <text x={xAt(marker.x) + 6} y={pad.top + 2}
                fontFamily="JetBrains Mono, monospace" fontSize="9.5" fill={T.fg2}
                style={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {marker.label}
              </text>
            )}
          </>
        )}
      </svg>
    )
  }
)

StatusTimeline.displayName = 'StatusTimeline'
export default StatusTimeline
