import React, { useMemo } from 'react'
import { useGraphCanvas } from './GraphCanvasContext'
import { bezierPath, rectEdgePoint } from '../utils/graph'
import './GraphEdge.css'

export interface GraphEdgeProps extends React.SVGAttributes<SVGGElement> {
  id: string
  sourceId: string
  targetId: string
  label?: string
  variant?: 'default' | 'hot' | 'irrelevant'
}

export const GraphEdge = React.forwardRef<SVGGElement, GraphEdgeProps>(
  ({ id, sourceId, targetId, label, variant = 'default', className = '', ...props }, ref) => {
    const { getNodeRect } = useGraphCanvas()

    const path = useMemo(() => {
      const src = getNodeRect(sourceId)
      const tgt = getNodeRect(targetId)
      if (!src) { console.warn(`GraphEdge: source node "${sourceId}" not found`); return null }
      if (!tgt) { console.warn(`GraphEdge: target node "${targetId}" not found`); return null }
      const sp = rectEdgePoint(src.x, src.y, src.width, src.height, tgt.x, tgt.y)
      const tp = rectEdgePoint(tgt.x, tgt.y, tgt.width, tgt.height, src.x, src.y)
      return bezierPath(sp, tp, 0.22)
    }, [getNodeRect, sourceId, targetId])

    if (!path) return null

    const classNames = [
      'graph-edge',
      variant !== 'default' && `graph-edge--${variant}`,
      className,
    ]
      .filter(Boolean)
      .join(' ')

    const markerId = `arrow-${id}`
    const markerRoseId = `arrow-rose-${id}`
    const markerCyanId = `arrow-cyan-${id}`
    const markerUrl =
      variant === 'hot'
        ? `url(#${markerCyanId})`
        : variant === 'irrelevant'
          ? `url(#${markerRoseId})`
          : `url(#${markerId})`

    return (
      <g ref={ref} className={classNames} role="presentation" aria-hidden="true" data-testid={`graph-edge-${id}`} {...props}>
        <defs>
          <marker id={markerId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--graph-edge-strong, #94a3b8)" />
          </marker>
          <marker id={markerRoseId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="rgb(var(--status-rose))" />
          </marker>
          <marker id={markerCyanId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="rgb(var(--accent-primary))" />
          </marker>
        </defs>

        <path className="graph-edge__hit" d={path.d} data-testid={`graph-edge-hit-${id}`} />
        <path
          className="graph-edge__line"
          d={path.d}
          markerEnd={markerUrl}
          data-testid={`graph-edge-line-${id}`}
        />

        {label && (
          <g
            className="graph-edge__label"
            transform={`translate(${path.mid.x - (label.length * 3.3 + 7)}, ${path.mid.y - 9})`}
          >
            <rect
              width={label.length * 6.6 + 14}
              height="18"
              rx="3"
              className="graph-edge__label-bg"
              data-testid={`graph-edge-label-bg-${id}`}
            />
            <text
              x={label.length * 3.3 + 7}
              y="12"
              className="graph-edge__label-text"
              data-testid={`graph-edge-label-text-${id}`}
            >
              {label}
            </text>
          </g>
        )}
      </g>
    )
  }
)

GraphEdge.displayName = 'GraphEdge'

export default GraphEdge
