import React from 'react'
import './Sparkline.css'
import type { StatusColor } from './statusColors'
import { statusColorMap } from './statusColors'

export type SparklineColor = StatusColor

export interface SparklineProps extends Omit<React.SVGAttributes<SVGSVGElement>, 'children'> {
  data: number[]
  width?: number
  height?: number
  color?: SparklineColor | (string & {})
  area?: boolean
  label?: string
}

function resolveColor(color: string): string {
  return color in statusColorMap ? statusColorMap[color as StatusColor] : color
}

function linePath(pts: [number, number][]): string {
  return pts.map(([x, y], i) => (i ? 'L' : 'M') + x.toFixed(2) + ',' + y.toFixed(2)).join(' ')
}

export const Sparkline = React.forwardRef<SVGSVGElement, SparklineProps>(
  ({ data, width = 88, height = 28, color = 'emerald', area = true, label, className = '', style, ...rest }, ref) => {
    const gradId = React.useId()

    const geometry = React.useMemo(() => {
      if (!data || data.length < 2) return null
      const min = Math.min(...data)
      const max = Math.max(...data)
      const pts: [number, number][] = data.map((v, i) => [
        (i / (data.length - 1)) * width,
        height - 2 - ((v - min) / (max - min || 1)) * (height - 4),
      ])
      const line = linePath(pts)
      const fill = `${line} L${width},${height} L0,${height} Z`
      return { line, fill }
    }, [data, width, height])

    if (!geometry) return null

    const c = resolveColor(String(color))
    const { line, fill } = geometry

    return (
      <svg
        ref={ref}
        role="img"
        aria-label={label ?? 'trend sparkline'}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        style={{ display: 'block', ...style }}
        className={className}
        {...rest}
      >
        {area && (
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={c} stopOpacity="0.22" />
              <stop offset="100%" stopColor={c} stopOpacity="0" />
            </linearGradient>
          </defs>
        )}
        {area && <path d={fill} fill={`url(#${gradId})`} />}
        <path d={line} stroke={c} strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  }
)

Sparkline.displayName = 'Sparkline'
export default Sparkline
