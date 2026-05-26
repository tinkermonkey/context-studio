export interface LayoutNode {
  id: string
  x: number
  y: number
  width: number
  height: number
  pinned?: boolean
}

export interface LayoutEdge {
  source: string
  target: string
}

export interface ForceLayoutOptions {
  iterations?: number
  springLength?: number
  springStrength?: number
  repulsion?: number
  damping?: number
  centerStrength?: number
}

export function forceLayout(
  nodes: readonly LayoutNode[],
  edges: readonly LayoutEdge[],
  options: ForceLayoutOptions = {}
): Map<string, { x: number; y: number }> {
  const {
    iterations = 300,
    springLength = 160,
    springStrength = 0.04,
    repulsion = 8000,
    damping = 0.85,
    centerStrength = 0.005,
  } = options

  if (nodes.length === 0) return new Map()

  const vx = new Map<string, number>(nodes.map(n => [n.id, 0]))
  const vy = new Map<string, number>(nodes.map(n => [n.id, 0]))
  const pos = new Map<string, { x: number; y: number }>(
    nodes.map(n => [n.id, { x: n.x, y: n.y }])
  )
  const nodeMap = new Map(nodes.map(n => [n.id, n]))

  for (let iter = 0; iter < iterations; iter++) {
    // Repulsion between all node pairs
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i]
        const b = nodes[j]
        if (a.pinned && b.pinned) continue
        const pa = pos.get(a.id)!
        const pb = pos.get(b.id)!
        const dx = pb.x - pa.x || 0.1
        const dy = pb.y - pa.y || 0.1
        const dist = Math.max(Math.hypot(dx, dy), 1)
        const force = repulsion / (dist * dist)
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        if (!a.pinned) { vx.set(a.id, vx.get(a.id)! - fx); vy.set(a.id, vy.get(a.id)! - fy) }
        if (!b.pinned) { vx.set(b.id, vx.get(b.id)! + fx); vy.set(b.id, vy.get(b.id)! + fy) }
      }
    }

    // Spring forces along edges
    for (const edge of edges) {
      const src = nodeMap.get(edge.source)
      const tgt = nodeMap.get(edge.target)
      if (!src || !tgt || (src.pinned && tgt.pinned)) continue
      const ps = pos.get(src.id)!
      const pt = pos.get(tgt.id)!
      const dx = pt.x - ps.x || 0.1
      const dy = pt.y - ps.y || 0.1
      const dist = Math.max(Math.hypot(dx, dy), 1)
      const force = springStrength * (dist - springLength)
      const fx = (dx / dist) * force
      const fy = (dy / dist) * force
      if (!src.pinned) { vx.set(src.id, vx.get(src.id)! + fx); vy.set(src.id, vy.get(src.id)! + fy) }
      if (!tgt.pinned) { vx.set(tgt.id, vx.get(tgt.id)! - fx); vy.set(tgt.id, vy.get(tgt.id)! - fy) }
    }

    // Center gravity + damping + position update
    for (const node of nodes) {
      if (node.pinned) continue
      const p = pos.get(node.id)!
      const nvx = (vx.get(node.id)! - p.x * centerStrength) * damping
      const nvy = (vy.get(node.id)! - p.y * centerStrength) * damping
      vx.set(node.id, nvx)
      vy.set(node.id, nvy)
      pos.set(node.id, { x: p.x + nvx, y: p.y + nvy })
    }
  }

  return pos
}
