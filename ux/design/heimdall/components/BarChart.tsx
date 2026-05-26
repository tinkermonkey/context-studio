import React from 'react'
import './BarChart.css'
import { chartColors } from './chartColors'
import type { BarChartSeries } from './statusColors'
import { statusColorMap } from './statusColors'

export type { BarChartSeries }

export interface BarChartProps extends React.HTMLAttributes<HTMLDivElement> {
  series: BarChartSeries[]
  xLabels?: string[]
  yMin?: number
  yMax?: number
  yTickCount?: number
  legend?: boolean
  width?: number
  height?: number
  ariaLabel?: string
}

export const BarChart = React.forwardRef<HTMLDivElement, BarChartProps>(
  (
    {
      series,
      xLabels = [],
      yMin: customYMin,
      yMax: customYMax,
      yTickCount = 5,
      legend = false,
      width = 400,
      height = 200,
      ariaLabel,
      className = '',
      ...rest
    },
    ref
  ) => {
    if (!series || series.length === 0) {
      return (
        <div ref={ref} className={className} style={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgb(var(--canvas-fg-3))', fontSize: '12px' }} {...rest}>
          No data
        </div>
      )
    }

    // Find actual data min/max using loop to avoid stack overflow with large arrays
    let dataMin = Infinity
    let dataMax = -Infinity

    series.forEach((s) => {
      if (s.data && s.data.length > 0) {
        for (let i = 0; i < s.data.length; i++) {
          const value = s.data[i]
          if (value < dataMin) dataMin = value
          if (value > dataMax) dataMax = value
        }
      }
    })

    // Provide default range if no data found
    const hasData = isFinite(dataMin) && isFinite(dataMax)
    const yMin = customYMin !== undefined ? customYMin : hasData ? Math.floor(dataMin * 10) / 10 : 0
    const yMax = customYMax !== undefined ? customYMax : hasData ? Math.ceil(dataMax * 10) / 10 : 1
    const yRange = yMax - yMin

    // SVG dimensions
    const svgWidth = 100
    const svgHeight = 100
    const padding = { top: 5, right: 5, bottom: 20, left: 15 }
    const chartWidth = svgWidth - padding.left - padding.right
    const chartHeight = svgHeight - padding.top - padding.bottom

    // Generate Y-axis ticks
    const yTicks = Array.from({ length: yTickCount }, (_, i) => {
      const divisor = yTickCount === 1 ? 1 : yTickCount - 1
      const value = yMin + (yRange * i) / divisor
      return {
        value: value.toFixed(1),
        y: padding.top + chartHeight - (i / divisor) * chartHeight,
      }
    })
    // Remove duplicate tick values (when yRange = 0)
    const uniqueYTicks = Array.from(
      new Map(yTicks.map((tick) => [tick.value, tick])).values()
    )

    // Calculate data dimensions (grouped layout: series displayed side-by-side at each x position)
    let dataPointCount = 0
    for (let i = 0; i < series.length; i++) {
      if (series[i].data.length > dataPointCount) {
        dataPointCount = series[i].data.length
      }
    }
    // Ensure barWidth is finite: if no data points, render nothing; ensure minimum spacing
    const barWidth = dataPointCount === 0 ? 0 : Math.max(chartWidth / (dataPointCount * series.length * 1.5), 0.5)

    if (dataPointCount === 0) {
      return (
        <div ref={ref} className={className} style={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgb(var(--canvas-fg-3))', fontSize: '12px' }} {...rest}>
          No data
        </div>
      )
    }

    return (
      <div ref={ref} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }} className={className} {...rest}>
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          width={width}
          height={height}
          style={{ overflow: 'visible' }}
          role="img"
          aria-label={ariaLabel ?? series.map((s) => s.name).join(', ')}
        >
          {ariaLabel && <title>{ariaLabel}</title>}
          {/* Y-axis grid lines and ticks */}
          {uniqueYTicks.map((tick, idx) => (
            <g key={`y-tick-${idx}`}>
              {/* Grid line */}
              <line
                x1={padding.left}
                y1={tick.y}
                x2={svgWidth - padding.right}
                y2={tick.y}
                stroke="rgb(var(--canvas-border))"
                strokeWidth="0.5"
              />
              {/* Tick label */}
              <text
                x={padding.left - 1}
                y={tick.y + 1}
                textAnchor="end"
                fontSize="3"
                fill="currentColor"
                style={{ fill: 'rgb(var(--canvas-fg-2))' }}
              >
                {tick.value}
              </text>
            </g>
          ))}

          {/* Y-axis line */}
          <line
            x1={padding.left}
            y1={padding.top}
            x2={padding.left}
            y2={svgHeight - padding.bottom}
            stroke="rgb(var(--canvas-border))"
            strokeWidth="0.5"
          />

          {/* X-axis line */}
          <line
            x1={padding.left}
            y1={svgHeight - padding.bottom}
            x2={svgWidth - padding.right}
            y2={svgHeight - padding.bottom}
            stroke="rgb(var(--canvas-border))"
            strokeWidth="0.5"
          />

          {/* Data series bars */}
          {series.map((s, seriesIdx) => {
            const color = s.color ? statusColorMap[s.color] : chartColors[seriesIdx % chartColors.length]
            const seriesDataLength = s.data.length

            return (
              <g key={`series-${seriesIdx}`}>
                {s.data.map((value, dataIdx) => {
                  const normalizedY = yRange === 0 ? 0.5 : Math.max(0, value - yMin) / yRange
                  const barHeight = normalizedY * chartHeight

                  // All series side by side at each x position
                  const xCenter = padding.left + (dataIdx + 0.5) * (chartWidth / seriesDataLength)
                  const seriesOffset = (seriesIdx - series.length / 2 + 0.5) * barWidth
                  const xPos = xCenter + seriesOffset - barWidth / 2

                  const yPos = svgHeight - padding.bottom - barHeight

                  return (
                    <rect
                      key={`bar-${seriesIdx}-${dataIdx}`}
                      x={xPos}
                      y={yPos}
                      width={barWidth}
                      height={barHeight}
                      fill={color}
                      stroke={color}
                      strokeWidth="0.5"
                    />
                  )
                })}
              </g>
            )
          })}

          {/* X-axis labels */}
          {xLabels.length > 0 &&
            xLabels.map((label, idx) => {
              const x = padding.left + (idx + 0.5) * (chartWidth / xLabels.length)
              return (
                <text
                  key={`x-label-${idx}`}
                  x={x}
                  y={svgHeight - padding.bottom + 4}
                  textAnchor="middle"
                  fontSize="3"
                  fill="currentColor"
                  style={{ fill: 'rgb(var(--canvas-fg-2))' }}
                >
                  {label}
                </text>
              )
            })}
        </svg>

        {/* Legend */}
        {legend && (
          <div style={{ display: 'flex', gap: '12px', fontSize: '12px', flexWrap: 'wrap', color: 'rgb(var(--canvas-fg-2))' }}>
            {series.map((s, idx) => (
              <div key={`legend-${idx}`} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <div
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '1px',
                    backgroundColor: s.color ? statusColorMap[s.color] : chartColors[idx % chartColors.length],
                  }}
                />
                <span>{s.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }
)

BarChart.displayName = 'BarChart'

export default BarChart
