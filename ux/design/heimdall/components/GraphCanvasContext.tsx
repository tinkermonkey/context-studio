import { createContext, useContext } from 'react'

export interface GraphNodeRect {
  x: number
  y: number
  width: number
  height: number
}

export interface GraphCanvasContextValue {
  getNodeRect: (id: string) => GraphNodeRect | null
  zoom: number
  pan: { x: number; y: number }
  selectedNodeId?: string
}

export const GraphCanvasContext = createContext<GraphCanvasContextValue | null>(null)

export function useGraphCanvas(): GraphCanvasContextValue {
  const ctx = useContext(GraphCanvasContext)
  if (!ctx) throw new Error('useGraphCanvas must be used within a GraphCanvas')
  return ctx
}
