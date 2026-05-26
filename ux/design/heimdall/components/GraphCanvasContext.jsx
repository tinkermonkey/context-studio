
interface GraphNodeRect {
  x: number
  y: number
  width: number
  height: number
}

interface GraphCanvasContextValue {
  getNodeRect: (id: string) => GraphNodeRect | null
  zoom: number
  pan: { x: number; y: number }
  selectedNodeId?: string
}

const GraphCanvasContext = createContext<GraphCanvasContextValue | null>(null)

function useGraphCanvas(): GraphCanvasContextValue {
  const ctx = useContext(GraphCanvasContext)
  if (!ctx) throw new Error('useGraphCanvas must be used within a GraphCanvas')
  return ctx
}


// --- Babel-standalone: expose runtime values to window ---
window.GraphCanvasContext = GraphCanvasContext;
window.useGraphCanvas = useGraphCanvas;
