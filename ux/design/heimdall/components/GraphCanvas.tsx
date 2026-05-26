import React, { useState, useRef, useCallback, useEffect, useLayoutEffect, useMemo, useId } from 'react'
import { bezierPath, rectEdgePoint } from '../utils/graph'
import { forceLayout } from '../utils/graphLayout'
import { GraphCanvasContext, useGraphCanvas } from './GraphCanvasContext'
import GraphNode from './GraphNode'
import './GraphCanvas.css'
import './GraphEdge.css'

export type { GraphCanvasContextValue } from './GraphCanvasContext'
export { useGraphCanvas } from './GraphCanvasContext'

// ─── Public data types ────────────────────────────────────────────────────────

export interface GraphNodeData {
  id: string
  label: string
  kind?: string
  domainColor?: string
  /** Explicit position. When omitted with layout="force", the engine places the node. */
  x?: number
  y?: number
}

export interface GraphEdge {
  id: string
  sourceId: string
  targetId: string
  label?: string
  variant?: 'default' | 'hot' | 'irrelevant'
}

/** Props that a custom node component receives from renderNode. */
export interface BaseGraphNodeComponentProps {
  id: string
  label: string
  selected?: boolean
  onSelect?: (id: string) => void
}

// ─── Internal edge component ──────────────────────────────────────────────────

const DEFAULT_NODE_W = 138
const DEFAULT_NODE_H = 30

interface InternalEdgeProps {
  id: string
  sourceId: string
  targetId: string
  label?: string
  variant?: 'default' | 'hot' | 'irrelevant'
}

function GraphEdgeInternal({ id, sourceId, targetId, label, variant = 'default' }: InternalEdgeProps) {
  const { getNodeRect } = useGraphCanvas()

  const result = useMemo(() => {
    const src = getNodeRect(sourceId)
    const tgt = getNodeRect(targetId)
    if (!src || !tgt) return null
    const sp = rectEdgePoint(src.x, src.y, src.width, src.height, tgt.x, tgt.y)
    const tp = rectEdgePoint(tgt.x, tgt.y, tgt.width, tgt.height, src.x, src.y)
    return bezierPath(sp, tp, 0.22)
  }, [getNodeRect, sourceId, targetId])

  if (!result) return null

  const markerId = `arrow-${id}`
  const markerRoseId = `arrow-rose-${id}`
  const markerCyanId = `arrow-cyan-${id}`
  const markerUrl =
    variant === 'hot'
      ? `url(#${markerCyanId})`
      : variant === 'irrelevant'
        ? `url(#${markerRoseId})`
        : `url(#${markerId})`
  const classNames = ['graph-edge', variant !== 'default' && `graph-edge--${variant}`].filter(Boolean).join(' ')
  return (
    <g className={classNames} role="presentation" aria-hidden="true" data-testid={`graph-edge-${id}`}>
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
      <path className="graph-edge__hit" d={result.d} />
      <path className="graph-edge__line" d={result.d} markerEnd={markerUrl} />
      {label && (
        <g
          transform={`translate(${result.mid.x - (label.length * 3.3 + 7)}, ${result.mid.y - 9})`}
          className="graph-edge__label"
        >
          <rect
            width={label.length * 6.6 + 14}
            height="18"
            rx="3"
            className="graph-edge__label-bg"
          />
          <text
            x={label.length * 3.3 + 7}
            y="12"
            className="graph-edge__label-text"
          >
            {label}
          </text>
        </g>
      )}
    </g>
  )
}

// ─── GraphCanvas ──────────────────────────────────────────────────────────────

export interface GraphCanvasProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onSelect'> {
  nodes: GraphNodeData[]
  edges?: GraphEdge[]
  selectedNodeId?: string
  onNodeSelect?: (nodeId: string) => void
  /**
   * Render the HTML content for each node. GraphCanvas wraps it in a foreignObject
   * and positions it via an SVG <g> transform. If omitted, the default GraphNode is used.
   *
   * Tip: memoize with useCallback to avoid unnecessary re-measurements.
   */
  renderNode?: (node: GraphNodeData, selected: boolean) => React.ReactNode
  /** 'manual' relies on explicit x/y per node. 'force' runs a spring layout for nodes
   *  without explicit coordinates; nodes with x and y are pinned. */
  layout?: 'manual' | 'force'
}

type NodeDims = Map<string, { width: number; height: number }>
type NodePositions = Map<string, { x: number; y: number }>

export const GraphCanvas = React.forwardRef<HTMLDivElement, GraphCanvasProps>(
  (
    {
      nodes = [],
      edges = [],
      selectedNodeId,
      onNodeSelect,
      renderNode,
      layout = 'manual',
      className = '',
      ...props
    },
    ref
  ) => {
    const [zoom, setZoom] = useState(1)
    const [pan, setPan] = useState({ x: 0, y: 0 })
    const [dims, setDims] = useState<NodeDims>(new Map())
    const [computedPositions, setComputedPositions] = useState<NodePositions>(new Map())

    const containerRef = useRef<HTMLDivElement>(null)
    const measureRefs = useRef<Record<string, HTMLDivElement | null>>({})
    const dragRef = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null)
    const zoomRef = useRef(1)
    const panRef = useRef({ x: 0, y: 0 })
    // Tracks whether we've applied the initial canvas-center offset
    const didCenterRef = useRef(false)

    const rawId = useId()
    const gridPatternId = `grid${rawId.replace(/:/g, '')}`

    // Keep refs current so wheel/drag handlers don't capture stale state
    useEffect(() => { zoomRef.current = zoom }, [zoom])
    useEffect(() => { panRef.current = pan }, [pan])

    // Measure each node's natural HTML dimensions from the hidden off-screen div.
    // Re-runs whenever the node list changes. renderNode is intentionally excluded:
    // callers should memoize it with useCallback.
    useLayoutEffect(() => {
      const next: NodeDims = new Map()
      for (const node of nodes) {
        const el = measureRefs.current[node.id]
        next.set(node.id, {
          width: el?.offsetWidth || DEFAULT_NODE_W,
          height: el?.offsetHeight || DEFAULT_NODE_H,
        })
      }
      setDims(next)
    }, [nodes])

    // Run force layout when dims are ready (only when layout='force')
    useEffect(() => {
      if (layout !== 'force' || dims.size === 0) return

      const layoutNodes = nodes.map((n, i) => ({
        id: n.id,
        // Nodes without explicit coords start on a circle so the layout converges cleanly
        x: n.x ?? Math.cos((2 * Math.PI * i) / nodes.length) * 120,
        y: n.y ?? Math.sin((2 * Math.PI * i) / nodes.length) * 120,
        width: dims.get(n.id)?.width ?? DEFAULT_NODE_W,
        height: dims.get(n.id)?.height ?? DEFAULT_NODE_H,
        pinned: n.x !== undefined && n.y !== undefined,
      }))
      const layoutEdges = (edges ?? []).map(e => ({ source: e.sourceId, target: e.targetId }))
      setComputedPositions(forceLayout(layoutNodes, layoutEdges))
    }, [nodes, edges, dims, layout])

    // Wheel zoom anchored to cursor position
    useEffect(() => {
      const container = containerRef.current
      if (!container) return

      const handleWheel = (e: WheelEvent) => {
        e.preventDefault()
        const rect = container.getBoundingClientRect()
        const cx = e.clientX - rect.left
        const cy = e.clientY - rect.top
        if (!Number.isFinite(cx) || !Number.isFinite(cy)) return
        const delta = e.deltaY > 0 ? -0.1 : 0.1
        const prev = zoomRef.current
        const next = Math.min(2.5, Math.max(0.4, prev + delta))
        const change = next - prev
        const newPan = {
          x: panRef.current.x - (cx / prev) * change,
          y: panRef.current.y - (cy / prev) * change,
        }
        zoomRef.current = next
        panRef.current = newPan
        setZoom(next)
        setPan(newPan)
      }

      container.addEventListener('wheel', handleWheel, { passive: false })
      return () => container.removeEventListener('wheel', handleWheel)
    }, [])

    // Center the coordinate origin on first paint, matching the old graph-stage behavior
    useEffect(() => {
      const container = containerRef.current
      if (!container) return
      const ro = new ResizeObserver(entries => {
        const { width, height } = entries[0].contentRect
        if (!didCenterRef.current && width > 0 && height > 0) {
          didCenterRef.current = true
          const center = { x: width / 2, y: height / 2 }
          setPan(center)
          panRef.current = center
        }
      })
      ro.observe(container)
      return () => ro.disconnect()
    }, [])

    const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target instanceof Element && e.target.closest('.graph-node, [data-no-drag]')) return
      dragRef.current = {
        x: e.clientX,
        y: e.clientY,
        panX: panRef.current.x,
        panY: panRef.current.y,
      }
    }, [])

    const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
      if (!dragRef.current) return
      setPan({
        x: dragRef.current.panX + (e.clientX - dragRef.current.x),
        y: dragRef.current.panY + (e.clientY - dragRef.current.y),
      })
    }, [])

    const handleMouseUp = useCallback(() => { dragRef.current = null }, [])

    const getNodePosition = useCallback((node: GraphNodeData): { x: number; y: number } => {
      if (node.x !== undefined && node.y !== undefined) return { x: node.x, y: node.y }
      return computedPositions.get(node.id) ?? { x: 0, y: 0 }
    }, [computedPositions])

    const getNodeRect = useCallback((id: string) => {
      const node = nodes.find(n => n.id === id)
      if (!node) return null
      const pos = getNodePosition(node)
      const d = dims.get(id) ?? { width: DEFAULT_NODE_W, height: DEFAULT_NODE_H }
      return { x: pos.x, y: pos.y, width: d.width, height: d.height }
    }, [nodes, dims, getNodePosition])

    const resolveNodeContent = useCallback((node: GraphNodeData, selected: boolean): React.ReactNode => {
      if (renderNode) return renderNode(node, selected)
      return (
        <GraphNode
          id={node.id}
          label={node.label}
          kind={node.kind}
          domainColor={node.domainColor}
          selected={selected}
          onSelect={onNodeSelect}
        />
      )
    }, [renderNode, onNodeSelect])

    const contextValue = useMemo(() => ({
      getNodeRect,
      zoom,
      pan,
      selectedNodeId,
    }), [getNodeRect, zoom, pan, selectedNodeId])

    const handleRef = (el: HTMLDivElement | null) => {
      if (typeof ref === 'function') ref(el)
      else if (ref) (ref as React.MutableRefObject<HTMLDivElement | null>).current = el
      ;(containerRef as React.MutableRefObject<HTMLDivElement | null>).current = el
    }

    // Grid dots track pan/zoom via the SVG pattern transform
    const tileSize = 18 * zoom
    const patternX = ((pan.x % tileSize) + tileSize) % tileSize
    const patternY = ((pan.y % tileSize) + tileSize) % tileSize

    return (
      <div
        ref={handleRef}
        role="region"
        aria-label="Graph canvas"
        className={['graph-canvas', className].filter(Boolean).join(' ')}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        {...props}
      >
        {/* Hidden off-screen div — renders node HTML at natural size for measurement */}
        <div className="graph-measure" aria-hidden="true">
          {nodes.map(node => (
            <div
              key={node.id}
              ref={el => { measureRefs.current[node.id] = el }}
              style={{ display: 'inline-block' }}
            >
              {resolveNodeContent(node, false)}
            </div>
          ))}
        </div>

        <svg
          className="graph-svg"
          width="100%"
          height="100%"
          style={{ position: 'absolute', inset: 0, overflow: 'visible' }}
        >
          <defs>
            <pattern
              id={gridPatternId}
              x={patternX}
              y={patternY}
              width={tileSize}
              height={tileSize}
              patternUnits="userSpaceOnUse"
            >
              <circle
                cx="0"
                cy="0"
                r={Math.min(1, 0.5 * zoom)}
                className="graph-grid-dot"
              />
            </pattern>
          </defs>

          {/* Grid fills the full SVG surface */}
          <rect width="100%" height="100%" fill={`url(#${gridPatternId})`} className="graph-grid" />

          <GraphCanvasContext.Provider value={contextValue}>
            {/* Single viewport transform — edges and nodes share this coordinate space */}
            <g
              className="graph-viewport"
              data-testid="graph-viewport"
              transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}
            >
              <g className="graph-edges">
                {edges?.map(edge => (
                  <GraphEdgeInternal
                    key={edge.id}
                    id={edge.id}
                    sourceId={edge.sourceId}
                    targetId={edge.targetId}
                    label={edge.label}
                    variant={edge.variant}
                  />
                ))}
              </g>

              <g className="graph-nodes">
                {nodes.map(node => {
                  const pos = getNodePosition(node)
                  const d = dims.get(node.id) ?? { width: DEFAULT_NODE_W, height: DEFAULT_NODE_H }
                  const selected = node.id === selectedNodeId
                  return (
                    <g
                      key={node.id}
                      transform={`translate(${pos.x} ${pos.y})`}
                      data-node-id={node.id}
                      data-testid={`graph-node-${node.id}`}
                      data-domain={node.domainColor}
                      className={selected ? 'selected' : undefined}
                    >
                      <foreignObject
                        x={-d.width / 2}
                        y={-d.height / 2}
                        width={d.width}
                        height={d.height}
                        overflow="visible"
                      >
                        {resolveNodeContent(node, selected)}
                      </foreignObject>
                    </g>
                  )
                })}
              </g>
            </g>
          </GraphCanvasContext.Provider>
        </svg>
      </div>
    )
  }
)

GraphCanvas.displayName = 'GraphCanvas'

export default GraphCanvas
