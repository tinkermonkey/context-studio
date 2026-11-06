---
name: heimdall-graph
description: Heimdall component guide for Graph: GraphCanvas (layout modes, popovers, tooltips, custom node and edge renderers), GraphNode, GraphEdge, GraphEdgeShape, GraphToolbar, GraphCollapseControl, GraphInspector, GraphEdgeInspector, DetailDrawer, TopologyNode, HierarchyRow, HierarchyTree, plus useGraphCanvas, usePanZoom, the headless layout engines and the edge geometry utilities
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## GraphCanvas

Pan/zoom canvas for interactive node-edge graphs. Measures each node, runs the chosen layout engine, and draws edges between the measured boxes. Provides the context read by `GraphEdge`, `GraphToolbar` and `useGraphCanvas`.

```tsx
import { GraphCanvas, type GraphNodeData, type GraphEdgeData } from '@tinkermonkey/heimdall-ui'
```

The edge data type is declared as `GraphEdge` in `GraphCanvas.tsx` but exported as `GraphEdgeData`, because `GraphEdge` is the edge component.

### Props

**Core**

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `nodes` | `GraphNodeData[]` | required | Nodes to render |
| `edges` | `GraphEdgeData[]` | `[]` | Edges to render |
| `layout` | `'manual' \| 'force' \| 'organic' \| 'orthogonal' \| 'galaxy' \| 'force-clustered' \| 'radial-tree' \| 'ux-navigation'` | `'manual'` | Layout engine. See [Choosing a layout](#choosing-a-layout) |
| `selectedNodeId` | `string` | — | Controlled selected node ID |
| `onNodeSelect` | `(nodeId: string) => void` | — | Called when a node is clicked or activated with Enter/Space |
| `selectedEdgeId` | `string` | — | Controlled selected edge ID; drawn in the accent color |
| `onEdgeSelect` | `(edgeId: string) => void` | — | Makes edge lines and labels clickable and focusable |
| `onNodeHover` | `(nodeId: string \| undefined) => void` | — | Pointer enter (id) and leave (`undefined`) on a node |
| `onEdgeHover` | `(edgeId: string \| undefined) => void` | — | Pointer enter (id) and leave (`undefined`) on an edge |
| `onBackgroundClick` | `() => void` | — | Click on empty canvas, not after a pan drag. Clear selection here |
| `renderNode` | `(node, selected, hierarchy?, props?) => ReactNode` | — | Custom node content. See [Custom node renderers](#custom-node-renderers) |
| `renderEdge` | `(edge, geometry: EdgeGeometry) => ReactNode` | — | Custom SVG for an edge. See [Custom edge renderers](#custom-edge-renderers) |
| `fitView` | `boolean` | `false` | Fit the whole graph in view on first layout, including any cluster boundaries and hierarchy rings shown |
| `fitPadding` | `number` | `40` | Padding (px) around the fitted bounding box |
| `centerOnSelect` | `boolean` | `false` | Pan (keeping zoom) to center `selectedNodeId` when it changes. Use when selection can come from outside the canvas |
| `minZoom` | `number` | `0.05` | Lower zoom bound |
| `maxZoom` | `number` | `8` | Upper zoom bound |
| `draggable` | `boolean` | `true` | Nodes can be dragged. The position persists locally until the node list changes |
| `onNodeDragEnd` | `(nodeId, position: { x, y }) => void` | — | Fires after a real drag (past a 3 px threshold), not a click |
| `showToolbar` | `boolean` | `true` | Built-in zoom / fit / lock / fullscreen toolbar |
| `toolbarPosition` | `GraphToolbarPosition` | `'bottom-right'` | Any corner or edge center |
| `fullscreenContainerRef` | `RefObject<HTMLElement \| null>` | — | Ancestor to fullscreen instead of the canvas root. Must contain the canvas |
| `onLayoutStateChange` | `(state: GraphLayoutState) => void` | — | `'computing'` while an engine layout runs, `'simulating'` while galaxy live simulation moves nodes, `'idle'` otherwise. Fires on changes only; also on the root as `data-layout-state`. An inline callback is fine |
| `showLayoutIndicator` | `boolean` | `true` | "Laying out…" status chip (`role="status"`) while computing or simulating for longer than 150 ms. Top-right, or bottom-right when the toolbar is along the top. Set `false` to show your own |
| `...divProps` | | | Remaining props spread onto the root `<div>` (after the canvas's own handlers) |

**Layout and hierarchy** (the Read by column says which layouts use each prop)

| Prop | Type | Default | Read by | Description |
| ---- | ---- | ------- | ------- | ----------- |
| `isStructuralEdge` | `(edge) => boolean` | — | all | `true` = parent/child edge (source is the parent). Builds the hierarchy for `galaxy`, `radial-tree`, `ux-navigation`, `orthogonal` rows, and collapse. When set, non-structural edges are hidden under every layout until an endpoint is hovered or selected |
| `showAllRelations` | `boolean` | `false` | all | With `isStructuralEdge` set, draw every non-structural edge instead of hiding it |
| `structuralEdgeCurvature` | `number` | `0.22` | all | Curvature of structural edges without their own `curvature`. `0` = straight |
| `collapsedNodeIds` | `ReadonlySet<string>` | — | all | Nodes whose structural descendants are hidden. Controlled |
| `onToggleCollapse` | `(nodeId) => void` | — | all | Called when a node's collapse toggle is activated. Update `collapsedNodeIds` here; without it no toggle appears |
| `nodeMargin` | `number` | per engine | `force`, `force-clustered`, `organic`, `galaxy` | Extra clear space around each node. See each layout below |
| `showClusterBoundaries` | `boolean` | `true` (`false` for `galaxy`) | `galaxy`, `force-clustered`, `radial-tree` | Circle around each top-level group |
| `showHierarchyRings` | `boolean` | `false` | `radial-tree` | Ring per occupied depth around each trunk. Visual only |
| `isPageNode` | `(node) => boolean` | — | `ux-navigation`, `orthogonal` | `true` = page, `false` = view. Omitted = every node is a page |
| `isNavigationRoute` | `(edge) => boolean` | — | `ux-navigation`, `orthogonal` | Marks user-flow route edges. Omitted = no routes |

**Interaction overlays**

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `nodeTooltip` | `(node) => ReactNode` | — | Content shown near a hovered (or clicked) node |
| `nodeTooltipTrigger` | `'hover' \| 'click'` | `'hover'` | `'click'` renders the content in a `Popover` (`role="dialog"`), so it can hold buttons and links |
| `edgeTooltip` | `(edge) => ReactNode` | — | Same, at the edge path's midpoint |
| `edgeTooltipTrigger` | `'hover' \| 'click'` | `'hover'` | Same as `nodeTooltipTrigger`, for edges |
| `nodePopover` | `(node) => ReactNode` | — | Interactive `role="dialog"` popover on node click or Enter/Space |
| `edgePopover` | `(edge) => ReactNode` | — | Same, anchored at the edge midpoint |

**Viewport history** (see [Viewport history](#viewport-history))

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `onViewportDwell` | `(viewport: GraphViewportSnapshot) => void` | — | The viewport has been still for `dwellMs` after the last user pan/zoom (drag after its inertia stops, wheel, pinch, keyboard, toolbar zoom in/out). Once per rest, never mid-gesture |
| `dwellMs` | `number` | `1500` | Stillness needed before `onViewportDwell` fires |
| `onViewportNavigate` | `(viewport: GraphViewportSnapshot, cause: GraphViewportCause) => void` | — | The canvas or the app moved the viewport (mount fit, `centerOnSelect`, toolbar fit, fullscreen fit, galaxy resize re-frame, context/handle calls). Fires once the move has rendered |
| `initialViewport` | `GraphViewport` | — | `{ center, zoom }` applied after the first layout instead of `fitView`/centring and instead of centring the node selected at mount. Read once. Reports nothing |
| `viewportRef` | `Ref<GraphViewportHandle>` | — | Receives `{ setViewport, getViewport }` for restoring a viewport from outside the canvas. The forwarded `ref` stays the root `<div>` |

### Data types

`GraphNodeData`:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | `string` | Unique node ID |
| `label` | `string` | Display text |
| `kind` | `string` | Type badge on the default node (e.g. `'C'`) |
| `domainColor` | `string` | Domain color key (`'life'`, `'climate'`, `'software'`, `'default'`) |
| `x`, `y` | `number` | Required for `layout="manual"`. Pins the node under every other layout |
| `weight` | `number` | `layout="galaxy"` only: body area grows with weight. Ignored elsewhere |

`GraphEdgeData`:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | `string` | Unique edge ID |
| `sourceId`, `targetId` | `string` | Endpoint node IDs |
| `label` | `string` | Label pill, nudged along the path to clear nearby nodes |
| `variant` | `'default' \| 'hot' \| 'irrelevant'` | Neutral gray; amber accent, thicker; rose dashed |
| `weight` | `number` | 0-100 → 1-8 px stroke width (square-root curve). Unrelated to node weight |
| `opacity` | `number` | 0-1, line and arrow only (not the label) |
| `strokeDash` | `number \| [number, number]` | `4` → `"4 4"`, `[6, 2]` → `"6 2"`. Overrides variant dashing |
| `sourceAnchor`, `targetAnchor` | `'auto' \| 'left' \| 'right' \| 'top' \| 'bottom'` | Pin an endpoint to a side. Any fixed side switches to a cubic curve |
| `curvature` | `number` | Overrides the 0.22 default (and `structuralEdgeCurvature`) |

`EdgeGeometry` (second argument of `renderEdge`): `{ path, mid, labelPos, angle, selected, hovered }`. `path` is the SVG `d` string actually drawn (an orthogonal polyline under `layout="orthogonal"`), `mid` the path midpoint, `labelPos` the collision-cleared label center, `angle` the tangent at the midpoint in radians.

`GraphNodeHierarchyMeta` (third argument of `renderNode`): `{ hasChildren, collapsed, hiddenDescendantCount, onToggleCollapse? }`.

Viewport types, all in world coordinates (the space node `x`/`y` live in), so they survive a resize and fit in a URL:

| Type | Shape | Description |
| ---- | ----- | ----------- |
| `GraphViewportSnapshot` | `{ center: { x, y }, zoom, bounds: { minX, minY, maxX, maxY } }` | `center` is the world point at the middle of the canvas, `bounds` the visible world rectangle |
| `GraphViewport` | `{ center: { x, y }, zoom }` | What `initialViewport` and `setViewport` take. A snapshot is assignable to it |
| `GraphViewportCause` | see below | Second argument of `onViewportNavigate` |
| `GraphSetViewportOptions` | `{ animate?: boolean, silent?: boolean }` | `animate` eases over 150ms (a jump under `prefers-reduced-motion`; user input cancels it). `silent` skips `onViewportNavigate` |
| `GraphViewportHandle` | `{ setViewport(viewport, options?), getViewport(): GraphViewportSnapshot \| null }` | What `viewportRef` receives. `getViewport` is `null` before the container is measured |

`GraphViewportCause`:

| Cause | When |
| ----- | ---- |
| `{ kind: 'fit', reason: 'mount' }` | The first framing after layout: the `fitView` fit, or plain centring without it (also galaxy's first aspect-ratio re-layout) |
| `{ kind: 'fit', reason: 'toolbar' }` | The toolbar's zoom-to-fit button |
| `{ kind: 'fit', reason: 'fullscreen' }` | The fit on entering fullscreen |
| `{ kind: 'fit', reason: 'resize' }` | `layout="galaxy"` re-laid out and re-framed after the container's aspect ratio changed |
| `{ kind: 'fit', reason: 'layout' }` | Reserved. Not emitted: the canvas never re-fits after a later layout change |
| `{ kind: 'center-on-select', nodeId }` | `centerOnSelect` panned to the newly selected node |
| `{ kind: 'imperative' }` | The app called `zoomToFit`, `zoomBy`, `setZoom`, `setPan` or `setViewport` on `useGraphCanvas()`, or `setViewport` on `viewportRef` without `silent` |

### Choosing a layout

| `layout` | Data shape | Needs | Status |
| -------- | ---------- | ----- | ------ |
| `manual` | Positions known in advance | `x`/`y` on every node | Stable |
| `force` | Arbitrary graphs | — | Kept for compatibility. Prefer `organic` |
| `organic` | General graphs: meshes, dependency graphs, no single hierarchy | — | Proof of concept |
| `orthogonal` | Sparse, mostly-tree graphs of 15-60 nodes; diagrams with right-angle edges | `isStructuralEdge` recommended | Proof of concept |
| `galaxy` | Weighted hierarchy: budgets, headcount, package sizes | `isStructuralEdge`, `weight` | Stable |
| `force-clustered` | Graphs with real community structure | — | Stable |
| `radial-tree` | Strict trees or forests, up to about 35 nodes per trunk | `isStructuralEdge` | Stable |
| `ux-navigation` | App screen maps: pages, views, navigation routes | `isStructuralEdge`, `isPageNode`, `isNavigationRoute` | Stable |

Every engine layout pins nodes that have both `x` and `y`. Nodes without them are placed by the engine.

#### `manual`

Renders each node at its `x`/`y`. A node without both is drawn at `(0, 0)`. No engine runs.

#### `force`

Spring simulation for arbitrary graphs. Nodes without `x`/`y` start on a circle. `nodeMargin` defaults to each node's own rendered width. Kept for compatibility: `organic` gives lower stress and no overlaps on the same data.

#### `organic`

General graphs: stress majorization with guaranteed zero overlap and a minimum gap. Deterministic. Successor to `force`.

- `nodeMargin` is the guaranteed smallest box-to-box gap. Default 24 px.
- Labelled edges reserve room for their label between the two cards.
- Pinned nodes are held exactly.
- Limits (proof of concept): no clustering option yet. Isolated nodes are gridded in one block beneath the connected components. Strict trees read better as `radial-tree` or `orthogonal`.

#### `orthogonal`

Cell-grid placement with axis-parallel edge routes that never cross a node or share a segment. Successor to `ux-navigation`. The routes replace the bezier paths; an edge touching a node being dragged falls back to a live bezier.

- With `isStructuralEdge`, rows follow the structural forest. Without it, rows come from the BFS layering with the fewest crossings.
- With `isPageNode`, a page's views fan out to its right in the same row. `isNavigationRoute` edges are routed last, around everything else.
- `nodeMargin` has no effect.
- Pass `showAllRelations` when `isStructuralEdge` is set: routing every edge is the point of this layout, and non-structural edges are otherwise hidden until hovered.
- Limits (proof of concept): best on sparse, mostly-tree graphs of 15-60 nodes. No edge bundling or incremental routing; trunk sharing (`busTreeEdges`) is available from `orthogonalLayout()` only.

#### `galaxy`

Weighted hierarchy as orbits: body area grows with weight, children orbit their parent heaviest first, nothing overlaps.

- Needs `isStructuralEdge`. Without it every edge counts as structural.
- `GraphNodeData.weight` sets body area (square-root scaled). A node without a weight weighs the sum of its structural children; when no node has one, each node weighs its subtree leaf count. Weights resolve over the full tree, so collapsing a subtree never resizes its parent.
- Without `renderNode`, nodes draw as round bodies coloured by `domainColor`, labelled inside when the body is large enough and named on hover otherwise. With a custom `renderNode`, nodes keep their card shape.
- `nodeMargin` replaces the default gap (0.6 × median body radius, at least 12 px). `0` means touching.
- `showClusterBoundaries` defaults to `false` here.
- Structural edge labels show only when the edge or one of its nodes is hovered or selected. `structuralEdgeCurvature={0}` draws orbit links straight.
- The toolbar gains a live-simulation toggle: dragging a node then pulls its subtree along elastically. The toggle is internal state with no prop.
- Limits: relational edges can cross bodies.

#### `force-clustered`

Louvain communities laid out as separate bubbles, each rotated to face the clusters it links to. One boundary circle per top-level cluster (`showClusterBoundaries`). `nodeMargin` defaults to each node's width, as in `force`.

- Limits: only as good as the community structure in the data. Flat or single-blob graphs give arbitrary bubbles, and bubbles spread wide on graphs with many cross-community edges.

#### `radial-tree`

One structural tree per trunk, root at the centre and each depth on its own ring. Several trees are packed as separate trunks without overlap.

- Needs `isStructuralEdge`.
- `showClusterBoundaries` (default `true`) draws a circle per trunk. `showHierarchyRings` draws a ring per depth.
- The layout is computed from the fully expanded tree, so collapsing a node hides its descendants without moving any other node.
- Limits: labels stay readable up to about 35 nodes per trunk. Forests get one set of rings per trunk.

#### `ux-navigation`

Page trees top to bottom with view fans to the side; navigation routes appear on hover.

- `isStructuralEdge` is required: under this layout an omitted classifier means no edge is structural, so every node lands in one flat row and every edge is hidden until hovered.
- `isPageNode`: without it every node is a page, so there are no view fans.
- `isNavigationRoute`: route edges stay hidden until a page or view touching them is hovered. Which routes show depends on whether the hovered node is a collapsed page, an expanded page or a view (see `visibleNavigationEdgeIds`).
- Structural and route labels show only when the edge is in focus.

### Hierarchy and collapse

`collapsedNodeIds` + `onToggleCollapse` work under every layout. The hierarchy comes from `isStructuralEdge` (every edge counts as structural when it is omitted, except under `ux-navigation`). Hovering a node with children shows a `GraphCollapseControl` at its right edge; the default `GraphNode` also draws its own toggle and accepts Shift+Enter.

```tsx
const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set())
const toggle = useCallback((id: string) => setCollapsed(prev => {
  const next = new Set(prev)
  next.has(id) ? next.delete(id) : next.add(id)
  return next
}), [])

<GraphCanvas
  nodes={nodes}
  edges={edges}
  layout="radial-tree"
  isStructuralEdge={e => e.label === 'contains'}
  collapsedNodeIds={collapsed}
  onToggleCollapse={toggle}
  fitView
  style={{ width: '100%', height: 540 }}
/>
```

On a flat graph, leave `isStructuralEdge`, `collapsedNodeIds` and `onToggleCollapse` unset: without a classifier every edge is structural, so collapse toggles would hide arbitrary neighbours.

### Tooltips and popovers

- `nodeTooltip` / `edgeTooltip` with the default `'hover'` trigger: a non-interactive `role="tooltip"` overlay after a 200 ms hover delay, linked to its target with `aria-describedby`.
- `nodeTooltipTrigger="click"` / `edgeTooltipTrigger="click"`: the same content opens in a `Popover` on click, so it can hold buttons and links.
- `nodePopover` / `edgePopover`: a `role="dialog"` popover that opens on click, or on Enter/Space when focused, and moves focus to its first focusable element. It tracks pan and zoom, and closes on Escape, background click, or click outside the canvas. Only one popover is open at a time.
- A popover and a hover tooltip can be set on the same node. A content callback that returns `null` or `undefined` opens nothing.
- An edge becomes focusable and clickable when `onEdgeSelect`, `edgePopover`, or `edgeTooltip` with `edgeTooltipTrigger="click"` is set. A hover `edgeTooltip` alone is pointer-only.
- Accessible names use node labels, never ids: a focusable edge is "<edge label>: <source label> to <target label>" (or "<source label> to <target label>" without an edge label), and a popover dialog is "Details for <node label>" or "Details for <edge name>". An endpoint falls back to its id only when its label is empty.

```tsx
<GraphCanvas
  nodes={nodes}
  edges={edges}
  layout="organic"
  nodeTooltip={node => <span className="font-mono">{node.id}</span>}
  nodePopover={node => (
    <div>
      <p>{node.label}</p>
      <Button size="sm" onClick={() => openDetail(node.id)}>Open</Button>
    </div>
  )}
  edgePopover={edge => <span>{edge.label}</span>}
  style={{ width: '100%', height: 500 }}
/>
```

### Custom node renderers

`renderNode(node, selected, hierarchy, props)`:

- `hierarchy: GraphNodeHierarchyMeta` — `{ hasChildren, collapsed, hiddenDescendantCount, onToggleCollapse? }`. Use it to draw your own collapse affordance.
- `props: { nodeId, tooltipId?, onSelect?, onPopoverOpen? }`:
  - `onSelect` is `onNodeSelect`. GraphCanvas does not select a custom node on click; the renderer must call it.
  - `onPopoverOpen(element)` is defined when `nodePopover` is set, or `nodeTooltip` with `nodeTooltipTrigger="click"`. Call it on click and on Enter/Space with the node's element, or the popover and click tooltip never open.
  - `tooltipId` is set while the node's hover tooltip is shown. Put it in the node's `aria-describedby`.

The simplest correct renderer forwards everything to `GraphNode`, which already wires click, keyboard, ARIA and `onPopoverOpen`:

```tsx
const renderNode = useCallback<NonNullable<GraphCanvasProps['renderNode']>>(
  (node, selected, hierarchy, props) => (
    <GraphNode
      id={node.id}
      label={node.label}
      kind={node.kind}
      domainColor={node.domainColor}
      selected={selected}
      onSelect={props?.onSelect}
      onPopoverOpen={props?.onPopoverOpen}
      tooltipId={props?.tooltipId}
      hasChildren={hierarchy?.hasChildren}
      collapsed={hierarchy?.collapsed}
      hiddenDescendantCount={hierarchy?.hiddenDescendantCount}
      onToggleCollapse={hierarchy?.onToggleCollapse}
    />
  ),
  [],
)
```

A fully custom element must do the same wiring itself:

```tsx
(node, selected, _hierarchy, props) => {
  const interactive = !!(props?.onSelect || props?.onPopoverOpen)
  const activate = (el: HTMLElement) => {
    props?.onSelect?.(node.id)
    props?.onPopoverOpen?.(el)
  }
  return (
    <div
      className={selected ? 'my-node my-node--selected' : 'my-node'}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-haspopup={props?.onPopoverOpen ? 'dialog' : undefined}
      aria-describedby={props?.tooltipId}
      onClick={e => { e.stopPropagation(); activate(e.currentTarget) }}
      onKeyDown={e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activate(e.currentTarget) }
      }}
    >
      {node.label}
    </div>
  )
}
```

`renderNode` runs twice per node: once in a hidden measurement pass outside the canvas context, then for real inside it. A component in the renderer that calls `useGraphCanvas()` throws during the measurement pass; see [Graph hooks](#graph-hooks) for the guard.

### Custom edge renderers

`renderEdge(edge, geometry)` returns SVG that replaces the default line, arrow and label. The canvas still wraps it in a `<g class="graph-edge">` with the hit stroke, click, keyboard, hover and ARIA wiring, so the content needs no event handlers. Add `className="graph-edge__line"` to a path to inherit the default stroke, hover and selected styling.

```tsx
const renderEdge = useCallback<NonNullable<GraphCanvasProps['renderEdge']>>(
  (edge, geometry) => (
    <>
      <path d={geometry.path} className="graph-edge__line" />
      <circle cx={geometry.mid.x} cy={geometry.mid.y} r={geometry.hovered ? 4 : 3} fill="rgb(var(--accent-primary))" />
      {edge.label && (
        <text x={geometry.labelPos.x} y={geometry.labelPos.y - 6} textAnchor="middle" className="font-mono" fontSize={10}>
          {edge.label}
        </text>
      )}
    </>
  ),
  [],
)
```

The `edge` passed to `renderEdge` is rebuilt from the `GraphEdgeData` fields only; extra fields on your own edge type are not on it. Look them up by `edge.id`. (Classifiers, `edgeTooltip` and `edgePopover` receive your original objects.)

### Usage

```tsx
// Manual layout with explicit positions
<GraphCanvas
  nodes={[
    { id: 'cls_cell', x: 200, y: 160, label: 'Cell', kind: 'C', domainColor: 'life' },
    { id: 'cls_nucleus', x: 60, y: 50, label: 'Nucleus', kind: 'C', domainColor: 'life' },
  ]}
  edges={[
    { id: 'e1', sourceId: 'cls_cell', targetId: 'cls_nucleus', label: 'contains' },
  ]}
  selectedNodeId={selectedId}
  onNodeSelect={setSelectedId}
  onBackgroundClick={() => setSelectedId(undefined)}
  style={{ width: '100%', height: 500 }}
/>
```

```tsx
// Organic layout for a general graph (omit x/y)
<GraphCanvas
  nodes={nodes}
  edges={edges}
  layout="organic"
  nodeMargin={32}
  fitView
  selectedNodeId={selectedId}
  onNodeSelect={setSelectedId}
  style={{ width: '100%', height: 500 }}
/>
```

```tsx
// Galaxy: weighted hierarchy
<GraphCanvas
  nodes={[
    { id: 'org', label: 'Org', weight: 1200 },
    { id: 'eng', label: 'Engineering', weight: 700, domainColor: 'software' },
    { id: 'ops', label: 'Operations', weight: 300, domainColor: 'climate' },
  ]}
  edges={[
    { id: 'e1', sourceId: 'org', targetId: 'eng' },
    { id: 'e2', sourceId: 'org', targetId: 'ops' },
  ]}
  layout="galaxy"   // every edge is structural, so isStructuralEdge can be omitted
  fitView
  style={{ width: '100%', height: 540 }}
/>
```

```tsx
// UX navigation: pages, views, routes
interface ScreenNode extends GraphNodeData { isPage: boolean }
interface ScreenLink extends GraphEdgeData { role: 'child' | 'route' }

const isChild = (e: GraphEdgeData) => (e as ScreenLink).role === 'child'
const isRoute = (e: GraphEdgeData) => (e as ScreenLink).role === 'route'
const isPage = (n: GraphNodeData) => (n as ScreenNode).isPage

<GraphCanvas
  nodes={screens}
  edges={links}
  layout="ux-navigation"
  isStructuralEdge={isChild}
  isPageNode={isPage}
  isNavigationRoute={isRoute}
  fitView
  style={{ width: '100%', height: 600 }}
/>
```

The classifiers receive the objects you passed in, so extra fields on your own node and edge types are available after a cast. Define them at module scope or memoize them.

```tsx
// Selection-driven detail panel over the canvas, kept visible in fullscreen
const frameRef = useRef<HTMLDivElement>(null)

<div ref={frameRef} style={{ position: 'relative', height: 560 }}>
  <GraphCanvas
    nodes={nodes}
    edges={edges}
    layout="organic"
    fitView
    selectedNodeId={selectedId}
    onNodeSelect={setSelectedId}
    onBackgroundClick={() => setSelectedId(undefined)}
    toolbarPosition="bottom-left"
    fullscreenContainerRef={frameRef}
  />
  <DetailDrawer open={!!selectedNode} width={drawerWidth} onWidthChange={setDrawerWidth}>
    {selectedNode && <GraphInspector node={selectedNode} relationships={relationships} onNodeSelect={setSelectedId} />}
  </DetailDrawer>
</div>
```

### Viewport history

Put the viewport into browser history: replace the current entry when the user settles somewhere, push one when the canvas recentres on its own, and restore silently on back/forward.

```tsx
const viewportRef = useRef<GraphViewportHandle>(null)
const toParam = (v: GraphViewportSnapshot) => `${v.center.x.toFixed(1)},${v.center.y.toFixed(1)},${v.zoom.toFixed(3)}`
const fromParam = (p: string | null): GraphViewport | undefined => {
  const [x, y, zoom] = (p ?? '').split(',').map(Number)
  return [x, y, zoom].every(Number.isFinite) ? { center: { x, y }, zoom } : undefined
}

useEffect(() => {
  const onPop = () => {
    const vp = fromParam(new URLSearchParams(location.search).get('vp'))
    if (vp) viewportRef.current?.setViewport(vp, { silent: true, animate: true })
  }
  window.addEventListener('popstate', onPop)
  return () => window.removeEventListener('popstate', onPop)
}, [])

<GraphCanvas
  nodes={nodes}
  edges={edges}
  fitView
  centerOnSelect
  selectedNodeId={selectedId}
  initialViewport={fromParam(new URLSearchParams(location.search).get('vp'))}
  viewportRef={viewportRef}
  onViewportDwell={(vp) => history.replaceState(null, '', `?vp=${toParam(vp)}`)}
  onViewportNavigate={(vp, cause) => {
    if (cause.kind === 'center-on-select') history.pushState(null, '', `?vp=${toParam(vp)}`)
    else history.replaceState(null, '', `?vp=${toParam(vp)}`)
  }}
/>
```

- `onViewportDwell` is for user moves only, `onViewportNavigate` for everything else; no move reports through both. A programmatic move cancels a dwell still waiting to fire.
- Not reported anywhere: `initialViewport`, a `silent` `setViewport`, and the re-anchor that keeps the same world point centred when the container resizes (the snapshot's `center` and `zoom` don't change; only `bounds` does).
- `setViewport` before the first layout has been framed replaces that framing, like `initialViewport`, instead of being overwritten by it. It works while the canvas is locked, like the other imperative calls.
- Snapshot `center` and `zoom` round-trip exactly through `setViewport`. `zoom` is clamped to `minZoom`/`maxZoom`.

### Gotchas

- **The root fills its parent** (`width: 100%; height: 100%`). Give the parent a definite height, or pass `style={{ width: '100%', height: 500 }}`. In a zero-height parent nothing is visible.
- Engine layouts run one frame after their inputs change, not in the same render, so the busy state and the "Laying out…" chip paint before a slow engine (`orthogonal` can take seconds) blocks the main thread. The previous positions stay on screen until the new layout lands; before the first layout, nodes are hidden rather than stacked at the origin. Wait for `data-layout-state="idle"` before measuring or screenshotting node positions. The engines still run on the main thread, so the page does not respond while one runs.
- Keep `nodes` and `edges` memoized if `onLayoutStateChange` re-renders the parent. New arrays re-run the layout, which reports `'computing'` again, so unmemoized arrays relayout on every report.
- `fitView` (and the default centering) runs once, after the first layout; entering fullscreen fits again. Changing `nodes`, `layout` or `nodeMargin` later does not re-fit; remount with a `key` (e.g. `` key={`${datasetId}-${layout}`} ``) to fit again.
- Memoize `renderNode`, `renderEdge` and the classifier callbacks with `useCallback`. A new `renderNode` re-measures every node; a new classifier re-runs the layout.
- `isStructuralEdge` also hides edges: once set, a non-structural edge is not rendered (not just dimmed) until an endpoint is hovered or selected, under every layout. Pass `showAllRelations` to keep them all visible, or leave `isStructuralEdge` unset on flat graphs.
- `nodeMargin` means something different per engine: a gap added on top of the node footprint for `force`/`force-clustered` (default: node width), a hard minimum gap for `organic` (default 24), and a replacement orbit gap for `galaxy`.
- Dragging holds the dropped position only until the node list changes. Set `draggable={false}` for read-only views, or persist with `onNodeDragEnd`.
- Selection is fully controlled: clicking a node calls `onNodeSelect` but nothing highlights until `selectedNodeId` changes. Clicking an edge does not clear `selectedNodeId`, and vice versa; clear the other one in your handler if only one should be selected.
- GraphCanvas renders no `children`. Overlays such as `DetailDrawer` go in a shared `position: relative` wrapper as siblings; pass that wrapper as `fullscreenContainerRef`, or they disappear in fullscreen.
- `...divProps` spread after the canvas's own `onPointerDown`, `onPointerUp`, `onKeyDown`, `tabIndex` and `role`. Passing any of these replaces the canvas handler and breaks panning, background clicks or keyboard zoom.
- An edge whose `sourceId` or `targetId` is not in `nodes` logs a warning and is not drawn. Edges touching a collapsed-away node are hidden silently.
- Errors thrown by `renderNode` and `renderEdge` are logged and that node or edge renders nothing. A throwing classifier is logged and falls back to its omitted-prop default.
- Input: drag empty canvas to pan (with inertia, disabled under `prefers-reduced-motion`; a drag held still for about 100ms before the release doesn't glide), wheel or pinch to zoom under the cursor. With the canvas focused (`role="region"`, `aria-label="Graph canvas"`), `+`/`-` zoom in or out by a factor of 1.2 about the view centre and the arrow keys pan 20px. The toolbar's lock button freezes all three.

---

## GraphNode

Node card (or round body) drawn by `GraphCanvas` by default, and the usual building block for `renderNode`.

```tsx
import { GraphNode } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `string` | required | Node identifier, passed back to `onSelect` |
| `label` | `string` | required | Display text |
| `kind` | `string` | — | Type badge (e.g. `'C'` for class) |
| `domainColor` | `string` | `'default'` | Domain color key for the swatch |
| `selected` | `boolean` | `false` | Selected state |
| `onSelect` | `(id: string) => void` | — | Makes the node a focusable button |
| `onPopoverOpen` | `(triggeringElement: HTMLElement) => void` | — | Called on click and Enter/Space. Forward `renderNode`'s `props.onPopoverOpen` |
| `tooltipId` | `string` | — | Set as `aria-describedby`. Forward `renderNode`'s `props.tooltipId` |
| `popoverOpen` | `boolean` | `false` | Sets `aria-expanded` when `onPopoverOpen` is set |
| `popoverPanelId` | `string` | — | Sets `aria-controls` when `onPopoverOpen` is set |
| `hasChildren` | `boolean` | `false` | Node has structural children |
| `collapsed` | `boolean` | `false` | Children are collapsed; flips the toggle chevron |
| `hiddenDescendantCount` | `number` | `0` | Badge on the toggle while collapsed |
| `onToggleCollapse` | `() => void` | — | Renders the collapse toggle (with `hasChildren`); Shift+Enter also toggles |
| `onFocus` | `(e: FocusEvent<HTMLDivElement>) => void` | — | Node received focus |
| `onBlur` | `(e: FocusEvent<HTMLDivElement>) => void` | — | Node lost focus |
| `bodyRadius` | `number` | — | Draws a round body of this radius instead of a card (the `galaxy` default) |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
// Inside GraphCanvas renderNode callback
renderNode={(node, selected, hierarchy, props) => (
  <GraphNode
    id={node.id}
    label={node.label}
    kind={node.kind}
    domainColor={node.domainColor}
    selected={selected}
    onSelect={props?.onSelect}
    onPopoverOpen={props?.onPopoverOpen}
    tooltipId={props?.tooltipId}
  />
)}
```

```tsx
// Standalone chips, e.g. a legend
<div style={{ display: 'flex', gap: 8 }}>
  <GraphNode id="cls_organism" label="Organism" kind="C" domainColor="life" />
  <GraphNode id="svc_ingest" label="svc_ingest" kind="svc" domainColor="software" selected />
</div>
```

### Gotchas

- The node is a focusable `role="button"` when `onSelect`, `onPopoverOpen`, or `hasChildren` + `onToggleCollapse` is set. Enter/Space call `onSelect` and `onPopoverOpen`; Shift+Enter toggles collapse. `aria-pressed={selected}` is set only with `onSelect`.
- Without any of those the node is read-only: no role, no tab stop.
- Click stops propagation, so it never starts a canvas pan or fires `onBackgroundClick`.
- The `style` prop is ignored. Size and spacing come from the card CSS; use `className` for overrides. With `bodyRadius`, width and height are set to the diameter.
- A body narrower than 44 px hides its label visually (still announced, and shown as a `title` tooltip).

---

## GraphEdge

SVG edge between two nodes, drawn from the canvas's measured node boxes. Must render inside `GraphCanvas`.

```tsx
import { GraphEdge } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `string` | required | Unique edge identifier |
| `sourceId` | `string` | required | Source node ID |
| `targetId` | `string` | required | Target node ID |
| `sourceLabel` | `string` | `sourceId` | Source node's name in the interactive edge's `aria-label` |
| `targetLabel` | `string` | `targetId` | Target node's name in the interactive edge's `aria-label` |
| `label` | `string` | — | Label pill, placed clear of nearby nodes |
| `variant` | `'default' \| 'hot' \| 'irrelevant'` | `'default'` | Neutral gray, amber accent, or rose dashed |
| `weight` | `number` | — | 0-100 → 1-8 px stroke; unset = variant default |
| `opacity` | `number` | — | 0-1 on line and arrow, not the label |
| `strokeDash` | `number \| [number, number]` | — | Dash pattern; overrides variant dashing |
| `sourceAnchor` | `EdgeAnchor` | `'auto'` | Pin the source endpoint to a side |
| `targetAnchor` | `EdgeAnchor` | `'auto'` | Pin the target endpoint to a side |
| `curvature` | `number` | `0.22` | Curve strength. `0` = straight |
| `selected` | `boolean` | `false` | Accent color. Pair with `onSelect` |
| `onSelect` | `(id: string) => void` | — | Makes line and label clickable; Enter/Space when focused |
| `...gProps` | | | Remaining props spread onto the root SVG `<g>` |

`EdgeAnchor` is `'auto' | 'left' | 'right' | 'top' | 'bottom'`.

### Usage

```tsx
// Preferred: describe edges as data on GraphCanvas
<GraphCanvas
  nodes={nodes}
  edges={[
    { id: 'e1', sourceId: 'svc_gateway', targetId: 'svc_auth', label: 'calls' },
    { id: 'e2', sourceId: 'svc_auth', targetId: 'svc_store', variant: 'hot', label: 'writes', weight: 70 },
    { id: 'e3', sourceId: 'svc_store', targetId: 'svc_legacy', variant: 'irrelevant', label: 'deprecated' },
    { id: 'e4', sourceId: 'svc_gateway', targetId: 'svc_store', strokeDash: [6, 3], opacity: 0.6, sourceAnchor: 'bottom', targetAnchor: 'top' },
  ]}
  style={{ width: '100%', height: 400 }}
/>
```

```tsx
// Component form: only valid inside the canvas SVG, e.g. returned from renderEdge
const renderEdge = useCallback<NonNullable<GraphCanvasProps['renderEdge']>>(
  (edge, geometry) => (
    <GraphEdge
      id={edge.id}
      sourceId={edge.sourceId}
      targetId={edge.targetId}
      label={edge.label}
      variant={geometry.hovered ? 'hot' : edge.variant}
      weight={edge.weight}
    />
  ),
  [],
)
```

### Gotchas

- **Must render inside `GraphCanvas`**: it calls `useGraphCanvas()` and throws outside a canvas. GraphCanvas takes no children, so the component form only works from `renderEdge`. Leave its `onSelect` unset there; the canvas wrapper already handles clicks.
- It computes its own bezier from the node boxes, so it ignores `structuralEdgeCurvature` and orthogonal routes. Draw `geometry.path` instead when the route matters.
- Logs a warning and returns `null` when either endpoint is not a visible node.
- Endpoints sit on the node box edges facing each other, not at the centers.
- Arrow marker IDs derive from `id` (`arrow-<id>`); keep edge IDs unique across every graph on the page.
- With `onSelect`, the `aria-label` is "<label>: <source> to <target>". Pass `sourceLabel` / `targetLabel` whenever ids are opaque (UUIDs), or screen readers announce the ids.

---

## GraphEdgeShape

The line, arrow marker, hit stroke and label pill that every graph edge draws, given a precomputed path. Use it in your own SVG renderer, e.g. with the headless layout functions.

```tsx
import { GraphEdgeShape } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `string` | required | Edge ID; also seeds the marker IDs |
| `d` | `string` | required | SVG path data |
| `mid` | `{ x: number; y: number }` | required | Label center |
| `variant` | `'default' \| 'hot' \| 'irrelevant'` | required | Selects the arrow marker color |
| `label` | `string` | — | Label pill text |
| `weight` | `number` | — | 0-100 → 1-8 px stroke; marker scales with it |
| `opacity` | `number` | — | 0-1 on line and arrow |
| `strokeDash` | `number \| [number, number]` | — | Dash pattern |
| `onSelect` | `(id: string) => void` | — | Click handler on the hit stroke and label |
| `detailedTestIds` | `boolean` | `false` | Adds `data-testid`s to line, hit stroke and label |

### Usage

```tsx
const { d, points } = bezierPath({ x: 40, y: 60 }, { x: 320, y: 140 })
const mid = findClearLabelPosition(points, edgeLabelSize('writes'), [])

<svg width={360} height={200}>
  <g className="graph-edge graph-edge--hot">
    <GraphEdgeShape id="e_ingest_store" d={d} mid={mid} label="writes" variant="hot" weight={60} />
  </g>
</svg>
```

### Gotchas

- Renders a fragment (`<defs>`, two paths, label `<g>`), so it must sit inside an `<svg>`.
- Line color, hover, focus and selected styling come from classes on the parent: wrap it in `<g className="graph-edge">`, adding `graph-edge--hot`, `graph-edge--irrelevant` or `selected` as needed. `variant` alone only colors the arrow.
- The hit stroke is 14 px wide and `pointer-events: stroke`, but nothing is keyboard-accessible; put `role`, `tabIndex` and a key handler on your wrapper `<g>` when `onSelect` is set.
- Marker IDs are `arrow-<id>`, `arrow-rose-<id>`, `arrow-cyan-<id>`; IDs must be unique on the page.

---

## GraphToolbar

Floating zoom in / zoom out / zoom to fit / lock / fullscreen controls for a `GraphCanvas`, plus a live-simulation toggle under `layout="galaxy"`. GraphCanvas renders one itself; configure it with `showToolbar` and `toolbarPosition`.

```tsx
import { GraphToolbar, type GraphToolbarPosition } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `position` | `GraphToolbarPosition` | `'bottom-right'` | Corner or edge center; side centers stack vertically |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

`GraphToolbarPosition` is `'top-left' | 'top-center' | 'top-right' | 'right-center' | 'bottom-right' | 'bottom-center' | 'bottom-left' | 'left-center'`.

### Usage

```tsx
// Normal use: the built-in toolbar
<GraphCanvas nodes={nodes} edges={edges} toolbarPosition="top-right" style={{ width: '100%', height: 480 }} />
```

```tsx
// No viewport controls (read-only thumbnail)
<GraphCanvas nodes={nodes} edges={edges} showToolbar={false} draggable={false} fitView style={{ width: 320, height: 200 }} />
```

### Gotchas

- Reads `useGraphCanvas()` and throws outside a canvas. GraphCanvas renders no `children`, so a standalone `GraphToolbar` can only appear in content the canvas renders itself; in practice use `showToolbar`/`toolbarPosition`.
- Zoom buttons step by ×1.3 anchored at the canvas center. Fit uses `fitPadding`.
- Lock freezes wheel zoom, drag-to-pan and keyboard pan/zoom, and pauses automatic viewport moves (`centerOnSelect`, the fit on entering fullscreen). Node dragging, background clicks and the toolbar's own zoom and fit buttons still work.
- Zoom in/out count as user moves (`onViewportDwell` on GraphCanvas); zoom to fit reports `onViewportNavigate` with `{ kind: 'fit', reason: 'toolbar' }`.
- Fullscreen targets `fullscreenContainerRef` (or the canvas root) and is a silent no-op where the Fullscreen API is missing (iOS Safari).
- An open `DetailDrawer` covers the canvas's right edge, including the default bottom-right toolbar. Move it with `toolbarPosition="bottom-left"`.

---

## GraphCollapseControl

Expand/collapse chevron button with a hidden-descendant badge, drawn in SVG world coordinates at a node's right edge. GraphCanvas shows one on hover for any node with structural children when `onToggleCollapse` is set; use it directly only in a custom SVG renderer.

```tsx
import { GraphCollapseControl } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `nodeId` | `string` | required | Used for the `data-testid` |
| `label` | `string` | required | Node label for the `aria-label` ("Expand …" / "Collapse …") |
| `collapsed` | `boolean` | required | Chevron right (collapsed) or down; sets `aria-expanded` |
| `hiddenDescendantCount` | `number` | required | Badge shown while collapsed and above 0 |
| `onToggleCollapse` | `() => void` | required | Click, Enter or Space |
| `x` | `number` | required | Node center x, world space |
| `y` | `number` | required | Node center y, world space |
| `nodeWidth` | `number` | required | Node width; the control sits 4 px past the right edge |

### Usage

```tsx
// Inside your own <svg> world group, next to a node centered at (x, y)
<g transform={transform}>
  <GraphCollapseControl
    nodeId="pkg_core"
    label="pkg_core"
    collapsed={collapsed.has('pkg_core')}
    hiddenDescendantCount={12}
    onToggleCollapse={() => toggle('pkg_core')}
    x={240}
    y={120}
    nodeWidth={140}
  />
</g>
```

### Gotchas

- Renders a 24 × 24 `<foreignObject>`, so it must be inside an `<svg>`.
- It stops `pointerdown` and `click` propagation, so pressing it never starts a pan.
- Collapse state is yours: it only calls `onToggleCollapse`.

---

## GraphInspector

Detail panel for a selected graph node: kind and domain badges, title, ID, description, metadata and relationship links.

```tsx
import { GraphInspector, type GraphNodeMetadata, type RelationshipLink } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `node` | `GraphNodeMetadata \| null` | — | Node to inspect; `null`/omitted shows the empty state |
| `relationships` | `RelationshipLink[]` | `[]` | Incoming and outgoing links |
| `onNodeSelect` | `(nodeId: string) => void` | — | Called when a relationship target is clicked |
| `emptyStateText` | `string` | `'Select a node to inspect.'` | Empty state message |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

```ts
interface GraphNodeMetadata {
  id: string
  title: string
  kind?: string
  domain?: string
  description?: string
  metadata?: Record<string, string | number | boolean | null | undefined>
}

interface RelationshipLink {
  id: string
  target: string        // node ID passed to onNodeSelect
  targetTitle: string
  targetDomain?: string
  predicate: string
  direction: 'in' | 'out'
}
```

### Usage

```tsx
<GraphInspector
  node={selectedNode}
  relationships={relationships}
  onNodeSelect={setSelectedId}
  emptyStateText="No node selected."
/>
```

```tsx
// Full example
const node: GraphNodeMetadata = {
  id: 'cls_organism',
  title: 'Organism',
  kind: 'C',
  domain: 'life',
  description: 'Any individual living entity.',
  metadata: { kind: 'Class', domain: 'life', individuals: 428 },
}

const relationships: RelationshipLink[] = [
  { id: 'r1', predicate: 'contains', target: 'cls_cell', targetTitle: 'Cell', targetDomain: 'life', direction: 'out' },
  { id: 'r2', predicate: 'instanceOf', target: 'cls_eukaryote', targetTitle: 'Eukaryote', direction: 'in' },
]

<GraphInspector node={node} relationships={relationships} onNodeSelect={setSelectedId} />
```

### Gotchas

- Relationships are split into "Outgoing · N" and "Incoming · N" sections by `direction`. An empty list shows "No relationships yet."
- Relationship targets are always rendered as buttons; without `onNodeSelect` they do nothing when clicked.
- Metadata values are rendered with `String()`, so `null` shows as `null`. Filter them out first if that is not wanted.
- No fixed width or border; place it in a `DetailDrawer`, `Panel` or sized container.

---

## GraphEdgeInspector

Detail panel for a selected edge: predicate as title, edge ID, source → target endpoints, weight and metadata. Same visual family as `GraphInspector`; stack them source → edge → target.

```tsx
import { GraphEdgeInspector, type GraphEdgeMetadata } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `edge` | `GraphEdgeMetadata \| null` | — | Edge to inspect; `null`/omitted shows the empty state |
| `onNodeSelect` | `(nodeId: string) => void` | — | Makes the endpoints buttons that navigate to that node |
| `emptyStateText` | `string` | `'Select an edge to inspect.'` | Empty state message |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

```ts
interface GraphEdgeMetadata {
  id: string
  predicate: string     // panel title
  sourceId: string
  sourceTitle: string
  sourceDomain?: string
  targetId: string
  targetTitle: string
  targetDomain?: string
  variant?: 'default' | 'hot' | 'irrelevant'
  weight?: number       // shown as a raw number
  metadata?: Record<string, string | number | boolean | null | undefined>
}
```

### Usage

```tsx
<GraphEdgeInspector edge={selectedEdge} onNodeSelect={setSelectedNodeId} />
```

```tsx
// Built from the selected GraphEdgeData and its endpoint nodes
const edge: GraphEdgeMetadata = {
  id: 'e_gateway_auth',
  predicate: 'callsInto',
  sourceId: 'svc_gateway',
  sourceTitle: 'API Gateway',
  sourceDomain: 'software',
  targetId: 'svc_auth',
  targetTitle: 'Auth Service',
  targetDomain: 'software',
  variant: 'hot',
  weight: 88,
  metadata: { protocol: 'grpc', p99_ms: 41 },
}

<div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
  <GraphInspector node={sourceNode} onNodeSelect={selectNode} />
  <GraphEdgeInspector edge={edge} onNodeSelect={selectNode} />
  <GraphInspector node={targetNode} onNodeSelect={selectNode} />
</div>
```

### Gotchas

- Without `onNodeSelect` the endpoints are plain text, not buttons.
- The variant badge appears only for `'hot'` and `'irrelevant'`. `weight` is listed first in the key-value block, before `metadata`.
- The component does not look anything up: map your `GraphEdgeData` and its endpoint nodes into `GraphEdgeMetadata` yourself.

---

## DetailDrawer

Non-modal translucent panel that slides over the right edge of its nearest positioned ancestor, opening when `open` is true and collapsing to zero width otherwise. Use it for selection-driven detail (a graph node or edge, a list row) without reserving layout space.

```tsx
import { DetailDrawer } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `open` | `boolean` | required | Expanded (animated width) or collapsed to 0 |
| `children` | `ReactNode` | required | Panel content |
| `width` | `number` | `360` | Open width in px. Initial value only when resizable |
| `onWidthChange` | `(width: number) => void` | — | Enables the left-edge resize handle; called while resizing |
| `minWidth` | `number` | `260` | Lower resize bound |
| `maxWidth` | `number` | `640` | Upper resize bound |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<div style={{ position: 'relative', height: 480 }}>
  <MainContent />
  <DetailDrawer open={!!selectedId}>
    <GraphInspector node={selectedNode} />
  </DetailDrawer>
</div>
```

```tsx
// Resizable, width persisted by the caller
const [drawerWidth, setDrawerWidth] = useState(320)

<div style={{ position: 'relative', height: 560 }}>
  <GraphCanvas nodes={nodes} edges={edges} onNodeSelect={setSelectedId} toolbarPosition="bottom-left" />
  <DetailDrawer
    open={!!selectedId}
    width={drawerWidth}
    onWidthChange={setDrawerWidth}
    minWidth={280}
    maxWidth={520}
  >
    <GraphInspector node={selectedNode} relationships={relationships} onNodeSelect={setSelectedId} />
  </DetailDrawer>
</div>
```

### Gotchas

- **The parent must be positioned** (`position: relative`) with a height: the drawer is `position: absolute; top: 0; right: 0; bottom: 0` with `z-index: 2`.
- Not modal: no backdrop, focus trap, Escape handling or scroll lock. Close it yourself (e.g. on `onBackgroundClick`). Use `Drawer` from `heimdall-overlays` for a modal panel.
- Closed content stays mounted at width 0, with `inert` and `aria-hidden`, so it keeps its state and cannot be tabbed into.
- With `onWidthChange` set, later changes to `width` are ignored; the drawer tracks its own width. Without it, `width` is used directly and there is no handle.
- The handle resizes by mouse drag, or with the keyboard when focused: ArrowLeft widens and ArrowRight narrows by 10 px (40 px with Shift). Touch dragging is not supported.
- A `style` prop replaces the inline width style and breaks open/close. Use `className` for overrides.
- Content scrolls inside the drawer. It covers whatever sits on the parent's right edge, such as GraphCanvas's default bottom-right toolbar.

---

## TopologyNode

Infrastructure/service node card with status dot and metric progress bars. Supports absolute positioning for hand-placed diagrams, and works as `renderNode` content in `GraphCanvas`.

```tsx
import { TopologyNode, type TopologyNodeMetric } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | required | Service name |
| `nodeRole` | `string` | `''` | Role label below the title |
| `status` | `'ok' \| 'warning' \| 'error' \| 'idle'` | `'idle'` | Status dot color |
| `metrics` | `TopologyNodeMetric[]` | `[]` | Metric rows with progress bars |
| `selected` | `boolean` | `false` | Amber border ring |
| `x` | `number` | — | Absolute left position (px), with `y` |
| `y` | `number` | — | Absolute top position (px), with `x` |
| `onSelect` | `() => void` | — | Makes the card a focusable button |
| `...divProps` | | | Remaining props (except `role`) spread onto the root `<div>` |

Status → dot color: `ok`=emerald, `warning`=amber, `error`=rose, `idle`=neutral.

### Data types

```ts
interface TopologyNodeMetric {
  label: string
  value: number | string
  unit?: string
  percent: number           // progress bar fill, clamped to 0-100; non-finite = 0
  sparklineData: number[]   // required by the type, not rendered
  color?: StatusColor       // bar color; default amber accent
}
```

### Usage

```tsx
// In a positioned canvas
<div style={{ position: 'relative', height: 400 }}>
  <TopologyNode
    title="svc_api"
    nodeRole="backend"
    status="ok"
    metrics={[
      { label: 'CPU', value: 45, unit: '%', percent: 45, sparklineData: [], color: 'emerald' },
      { label: 'Memory', value: 62, unit: '%', percent: 62, sparklineData: [], color: 'amber' },
    ]}
    x={100}
    y={80}
    selected={selected === 'svc_api'}
    onSelect={() => setSelected('svc_api')}
  />
</div>
```

```tsx
// In a grid, no positioning
<div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
  <TopologyNode title="svc_ingest" nodeRole="worker" status="warning" />
  <TopologyNode title="db_primary" nodeRole="postgres" status="error" />
</div>
```

### Gotchas

- Absolute positioning applies only when both `x` and `y` are set; the parent must be `position: relative`. Your `style` is merged over it.
- Without `onSelect` the card has no role or tab stop. With it, Enter/Space call `onSelect`. `aria-selected` is always set.
- `role` cannot be passed: the prop name `nodeRole` is the visible role label.

---

## HierarchyRow

A single row in a taxonomy/hierarchy list with depth indentation, connector, domain color swatch, kind badge and right-hand description.

```tsx
import { HierarchyRow } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `domain` | `'life' \| 'climate' \| 'software' \| 'default' \| string` | required | Swatch color |
| `kind` | `'taxonomy' \| 'scheme' \| 'class'` | required | Kind badge text |
| `label` | `string` | required | Display text |
| `depth` | `number` | `0` | Indentation level (20 px per level) |
| `meta` | `string` | — | Metadata (e.g. item count) after the label |
| `description` | `string` | — | Secondary text in the right column |
| `selected` | `boolean` | `false` | Selected state |
| `onSelect` | `() => void` | — | Makes the row a focusable button |
| `showKind` | `boolean` | `true` | Show the kind badge |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<HierarchyRow
  depth={0}
  kind="taxonomy"
  label="root_taxonomy"
  domain="life"
  description="Root taxonomy for life sciences"
/>
```

```tsx
// Interactive with selection
<HierarchyRow
  depth={1}
  kind="scheme"
  label="public_scheme"
  domain="life"
  meta="8 classes"
  description="Public classification scheme"
  selected={selected === 'public_scheme'}
  onSelect={() => setSelected('public_scheme')}
/>
```

### Gotchas

- A connector line renders at `depth > 0` only.
- Unknown `domain` strings fall back to `--dom-default`.
- Without `onSelect` the row has no role or tab stop. With it: `role="button"`, `aria-pressed={selected}`, Enter/Space call `onSelect`.
- `kind` is required even with `showKind={false}`.
- A `style` prop replaces the row's depth and domain CSS variables, losing indentation and swatch color. Use `className`.
- The left column is a fixed 220 px grid track; long labels with deep indentation wrap or overflow.

---

## HierarchyTree

Plain container for `HierarchyRow` items.

```tsx
import { HierarchyTree } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `children` | `ReactNode` | required | `HierarchyRow` components |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<HierarchyTree>
  <HierarchyRow depth={0} kind="taxonomy" label="root_taxonomy" domain="life" />
  <HierarchyRow depth={1} kind="scheme" label="public_scheme" domain="life" meta="8 classes" selected={selected === 1} onSelect={() => setSelected(1)} />
  <HierarchyRow depth={2} kind="class" label="cls_organism" domain="life" description="Individual organisms" />
</HierarchyTree>
```

```tsx
// Dynamic with selection
<HierarchyTree>
  {rows.map((row, idx) => (
    <HierarchyRow
      key={row.label}
      {...row}
      selected={selected === idx}
      onSelect={() => setSelected(selected === idx ? null : idx)}
    />
  ))}
</HierarchyTree>
```

### Gotchas

- No built-in selection, expand/collapse, keyboard tree navigation or virtualization. Rows are a flat list ordered and indented by you; manage hierarchy and collapse in the parent.
- No `role="tree"`; add ARIA yourself if the list needs tree semantics.

---

## Graph hooks

### useGraphCanvas

```ts
useGraphCanvas(): GraphCanvasContextValue
```

Reads the enclosing `GraphCanvas`'s state and viewport controls. Throws outside a canvas. Every viewport setter here reports `{ kind: 'imperative' }` to `onViewportNavigate`; the built-in toolbar's buttons don't go through these, so its zoom in/out count as user moves and its fit as `{ kind: 'fit', reason: 'toolbar' }`.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `getNodeRect` | `(id) => GraphNodeRect \| null` | Visible node's box; `x`/`y` are the **center** |
| `nodeRects` | `GraphNodeRect[]` | Every visible node's box |
| `zoom`, `pan` | `number`, `{ x, y }` | Current viewport |
| `zoomToFit` | `(padding?) => void` | Fit all visible nodes |
| `zoomBy` | `(factor) => void` | Zoom anchored at the canvas center |
| `setZoom` | `(zoom) => void` | Zoom without changing pan |
| `setPan` | `(x, y) => void` | Pan without changing zoom |
| `setViewport`, `getViewport` | see `GraphViewportHandle` | Same as the `viewportRef` handle. See [Viewport history](#viewport-history) |
| `locked`, `setLocked` | `boolean`, state setter | Pan/zoom input lock |
| `isFullscreen`, `toggleFullscreen` | `boolean`, `() => void` | Fullscreen state |
| `layout` | `GraphCanvasProps['layout']` | Read-only current layout |
| `liveSimulation`, `setLiveSimulation` | `boolean`, state setter | Galaxy live simulation |
| `selectedNodeId`, `hoveredNodeId`, `hoveredEdgeId` | `string \| undefined` | Current selection and hover |

The only code inside a canvas is what `renderNode` and `renderEdge` return. `renderNode` also runs in a measurement pass outside the context, so guard the call:

```tsx
function FitButton() {
  let canvas: GraphCanvasContextValue | null = null
  try { canvas = useGraphCanvas() } catch { canvas = null }
  if (!canvas) return null
  const { zoomToFit } = canvas
  return <Button size="sm" data-no-drag onClick={() => zoomToFit()}>Fit</Button>
}
```

`data-no-drag` on an element inside the canvas stops a press on it from starting a pan.

### usePanZoom

```ts
usePanZoom(options: UsePanZoomOptions): UsePanZoomReturn
```

The pan/zoom engine behind GraphCanvas, for custom SVG or HTML surfaces. Drag to pan with inertia (none after a drag held still for about 100ms; a glide ends once under half a pixel of travel is left), wheel/pinch zoom anchored at the cursor, and when focused `+`/`-` (×1.2 or ÷1.2 about the container centre) and arrow keys (20px). Any zoom, `zoomTo`, `panTo` or `reset` stops a running inertia glide.

Options: `containerRef` (required; element that receives wheel events), `minZoom` (`0.25`), `maxZoom` (`4`), `bounds?: { minX, maxX, minY, maxY }` (clamps pan), `onViewportChange?: ({ x, y, zoom }) => void`, `locked` (`false`), `onUserGesture?: (phase: 'start' | 'change' | 'end') => void` (user input only, never `zoomTo`/`panTo`/`reset`: `'start'` on a pan press, `'change'` per drag frame, inertia frame, wheel event or key step, `'end'` once that input is at rest, i.e. after a release without inertia, after inertia runs out, or after each wheel/key step).

Returns: `transform` (a `matrix(...)` string), `viewport: { x, y, zoom }`, `bind: { onPointerDown, onKeyDown, tabIndex: 0, role: 'region' }`, `zoomTo(zoom, cx?, cy?)` (anchored at container point when given), `panTo(x, y)`, `reset()`, `getViewport()` (current `{ x, y, zoom }`, up to date before the next render).

```tsx
function FloorPlan() {
  const containerRef = useRef<HTMLDivElement>(null)
  const { transform, bind, reset } = usePanZoom({ containerRef, minZoom: 0.5, maxZoom: 3 })
  return (
    <div
      ref={containerRef}
      {...bind}
      aria-label="Floor plan"
      onDoubleClick={reset}
      style={{ position: 'relative', overflow: 'hidden', height: 400, touchAction: 'none' }}
    >
      <svg width="100%" height="100%">
        <g transform={transform}>
          <rect x={0} y={0} width={600} height={400} fill="none" stroke="currentColor" />
        </g>
      </svg>
    </div>
  )
}
```

- Spread `bind` on the same element as `containerRef`, and render that element unconditionally: the wheel listener attaches on mount.
- `bind.onPointerDown` starts a pan from any press, including on child content. Wrap it and skip presses on interactive children, as GraphCanvas does with `data-no-drag`.
- Memoize `onViewportChange` and `bounds`. `onViewportChange` runs again whenever its identity changes; an inline callback that sets state with a new object re-renders forever.
- Defaults differ from GraphCanvas (`0.25`-`4` here, `0.05`-`8` there). `locked` blocks user input only, not `zoomTo`/`panTo`/`reset`.
- `role: 'region'` needs an `aria-label`.

---

## Headless layout functions

The engines behind GraphCanvas are exported for use outside it: precomputing positions, server-side layout, or a custom renderer. All are deterministic. Positions are node **centers**.

```tsx
import {
  organicLayout,
  orthogonalLayout,
  radialTreeLayout,
  uxNavLayout,
  galaxyLayout,
  forceLayout,
  clusteredForceLayout,
  buildStructuralForest,
} from '@tinkermonkey/heimdall-ui'
```

Nodes are `LayoutNode`: `{ id, x, y, width, height, pinned? }`. `width`/`height` are the rendered box size. Pass `x: NaN, y: NaN` for a node with no position yet (except `forceLayout`, below). `organicLayout`, `orthogonalLayout`, `galaxyLayout`, `forceLayout` and `clusteredForceLayout` hold a node with `pinned: true` and finite `x`/`y`; `radialTreeLayout` and `uxNavLayout` ignore input positions.

| Function | Signature | Returns |
| -------- | --------- | ------- |
| `organicLayout` | `(nodes, edges: { source, target, length?, label? }[], options?: OrganicLayoutOptions)` | `{ positions, stressHistory, stats }` |
| `orthogonalLayout` | `(nodes, edges: { source, target, structural?, navigationRoute? }[], options?: OrthogonalLayoutOptions)` | `{ positions, routes, groups, cell, origin, stats }` |
| `radialTreeLayout` | `(nodes, edges: HierarchyEdge[], dims, forest: StructuralForest, options?: RadialTreeLayoutOptions)` | `{ positions, trunkBoundaries, ringGeometry }` |
| `uxNavLayout` | `(nodes, edges: HierarchyEdge[], dims, isPageNode: (node) => boolean, options?: UxNavLayoutOptions)` | `Map<id, { x, y }>` |
| `galaxyLayout` | `(nodes: GalaxyLayoutNode[], edges: GalaxyLayoutEdge[], options?: GalaxyLayoutOptions)` | `Map<id, { x, y }>` |
| `forceLayout` | `(nodes, edges: { source, target }[], options?: ForceLayoutOptions)` | `Map<id, { x, y }>` |
| `clusteredForceLayout` | `(nodes, edges: { source, target }[], options?: ClusteredLayoutOptions)` | `{ positions, clusterBoundaries }` |

`HierarchyEdge` and `GalaxyLayoutEdge` are `{ source, target, structural: boolean }` (source = parent). `dims` is a `Map<id, { width, height }>`. `GalaxyLayoutNode` is `{ id, width, height, x?, y?, pinned?, weight?, radius? }`, where `radius` is the true radius of a round body; a `LayoutNode` also fits.

Options:

- **`OrganicLayoutOptions`**: `preferredEdgeLength` (160), `minimumNodeDistance` (24), `compactness` 0-1 (0.5), `componentSpacing` (40), `maxIterations` (300), `tolerance` (1e-4), `scope` (`'auto' | 'all' | 'affected'`), `affectedIds`. An edge `label` is the label box `{ width, height, offset? }`, reserved between its endpoints. Re-running on its own output is a no-op; after changing the graph, name the nodes to re-settle in `affectedIds` or pass `scope: 'all'`.
- **`OrthogonalLayoutOptions`**: `clearance` (10), `laneSpacing` (16), `lanes` (4), `bendPenalty`, `crossingPenalty`, `componentGap` (1 cell), `orderingSweeps` (6), `isPageNode: (id) => boolean`, `busTreeEdges` (false), `scope` (`'auto' | 'cold' | 'sketch'`). `routes[i]` is the polyline for `edges[i]`, from source box boundary to target box boundary.
- **`RadialTreeLayoutOptions`**: `ringSpacing` (80), `nodeSeparationGap` (12), `trunkPadding` (6). Build `forest` with `buildStructuralForest(allNodeIds, edges)` over the full node list, so collapsed nodes keep their slots.
- **`UxNavLayoutOptions`**: `rowSpacing` (80), `columnSpacing` (60), `viewFanGap` (40), `viewSpacing` (20), `trunkSpacing` (120), `maxRowWidth` (1024). A view with several parent pages appears once per parent, keyed `viewId:parentId`.
- **`GalaxyLayoutOptions`**: `nodeSpread` (0.6, a multiple of the median body radius, at least 12 px), `nodeMargin` (px; replaces that gap), `startAngle` (π, 9 o'clock), `aspectRatio`, `homeStrength`. `settleCycles`, `separateGroups` and `resolvedAspectScale` are deprecated and ignored.
- **`ForceLayoutOptions`**: `iterations` (300), `springLength` (160), `springStrength` (0.04), `repulsion` (8000), `damping` (0.85), `centerStrength` (0.005), `collisionStrength` (0.3), `nodeMargin` (each node's width). `forceLayout` starts from the given `x`/`y`, which must be finite: seed unpositioned nodes yourself (GraphCanvas uses a circle). `NaN` propagates to the output.
- **`ClusteredLayoutOptions`**: every `ForceLayoutOptions` field, plus `clusterPadding` (number or `(depth) => number`) and `macro` (force options for the cluster-to-cluster pass). Seeds its own positions from a Louvain clustering; `clusterBoundaries` is one `{ x, y, r }` per top-level cluster.

```ts
const { positions, routes } = orthogonalLayout(
  nodes.map(n => ({ id: n.id, x: NaN, y: NaN, width: 140, height: 32 })),
  edges.map(e => ({ source: e.sourceId, target: e.targetId, structural: e.label === 'contains' })),
)

const seeded = nodes.map((n, i) => {
  const a = (2 * Math.PI * i) / nodes.length
  return { id: n.id, x: 300 * Math.cos(a), y: 300 * Math.sin(a), width: 140, height: 32 }
})
const forcePositions = forceLayout(seeded, edges.map(e => ({ source: e.sourceId, target: e.targetId })))
```

---

## Hierarchy and clustering utilities

| Function | Signature | Returns |
| -------- | --------- | ------- |
| `buildStructuralForest` | `(nodeIds: string[], edges: HierarchyEdge[])` | `{ parentOf, childrenOf, roots }` |
| `structuralDescendants` | `(id: string, childrenOf: Map<string, string[]>)` | `Set<string>` of all descendants, excluding `id` |
| `visibleNavigationEdgeIds` | `(edges: GraphEdgeData[], hoveredNodeId, isPageNode: (id) => boolean, isNavigationRoute: (edge) => boolean, forest, collapsedNodeIds?)` | `Set<string>` of route edge IDs to show |
| `louvainCluster` | `(nodeIds: string[], edges: { source, target, weight? }[], options?: { maxLevels?, maxLocalPasses? })` | `ClusterTreeNode` dendrogram |
| `packClusters` | `(tree: ClusterTreeNode, { radiusOf, padding? })` | `Map<id, { x, y, r }>` |
| `boundingCirclesByGroup` | `(nodes: LayoutNode[], positions, leafToGroup: Map<id, groupId>, radiusOf: (id) => number, anchorToHead = false)` | `Map<groupId, { x, y, r }>` |

- `buildStructuralForest` uses only `structural: true` edges. A child with several structural parents keeps the first in edge order; cycles are broken by promoting one node to a root; edges to unknown IDs are skipped.
- `visibleNavigationEdgeIds` applies the `ux-navigation` hover rules: nothing without a hover; a view shows its own routes; an expanded page shows its own; a collapsed page adds its child views' routes. Note `isPageNode` takes a node **ID** here.
- `louvainCluster` is deterministic (defaults `maxLevels` 10, `maxLocalPasses` 100). The root ID is `'cluster-root'`; `root.children` are the top-level clusters and leaves are your node IDs. With no edges, the root's children are the leaves.
- `packClusters` packs that tree into nested circles (d3 pack, `padding` default 6). Leaves are keyed by node ID, clusters by their synthetic ID.
- `boundingCirclesByGroup` draws a simple enclosing circle per group from final positions: centered on the members' centroid, or on the group head's own position with `anchorToHead`. Nodes missing from `leafToGroup` are skipped.

```ts
const forest = buildStructuralForest(
  nodes.map(n => n.id),
  edges.map(e => ({ source: e.sourceId, target: e.targetId, structural: e.label === 'contains' })),
)
const hidden = structuralDescendants('pkg_core', forest.childrenOf)

const tree = louvainCluster(nodes.map(n => n.id), edges.map(e => ({ source: e.sourceId, target: e.targetId })))
const circles = packClusters(tree, { radiusOf: () => 40 })
```

---

## Edge geometry utilities

Pure functions GraphCanvas uses to draw edges. Points are `{ x, y }`; rectangles are given by **center** and size.

| Function | Signature | Returns |
| -------- | --------- | ------- |
| `rectEdgePoint` | `(cx, cy, w, h, tx, ty)` | Point where the line from the box center toward `(tx, ty)` leaves the box |
| `rectEdgeDirection` | `(cx, cy, w, h, tx, ty)` | Outward unit axis vector of that side (`{ x: ±1, y: 0 }` or `{ x: 0, y: ±1 }`) |
| `bezierPath` | `(p1, p2, curvature = 0.22)` | `{ d, mid, angle, points }` for a quadratic curve bowed left of p1→p2 (offset capped at 80 px) |
| `edgeLabelSize` | `(label: string)` | `{ width, height }` of the label pill GraphEdgeShape draws |
| `findClearLabelPosition` | `(points, size, obstacles: { x, y, width, height }[], margin = 6, isPolyline?)` | Label center clear of every obstacle, else the midpoint |

`findClearLabelPosition` samples the curve described by `points` (3 points = quadratic, 4 = cubic, or a polyline with `isPolyline`) from the middle outward and returns the first spot where a label of `size` clears every obstacle box by `margin`.

```tsx
// Custom SVG renderer: organic layout + usePanZoom + the shared edge drawing
const w = 140, h = 32
const { positions } = organicLayout(
  nodes.map(n => ({ id: n.id, x: NaN, y: NaN, width: w, height: h })),
  edges.map(e => ({ source: e.sourceId, target: e.targetId })),
)
const boxes = nodes.map(n => ({ ...positions.get(n.id)!, width: w, height: h }))

<svg width="100%" height="100%">
  <g transform={transform}>
    {edges.map(e => {
      const s = positions.get(e.sourceId)!
      const t = positions.get(e.targetId)!
      const { d, points, mid } = bezierPath(rectEdgePoint(s.x, s.y, w, h, t.x, t.y), rectEdgePoint(t.x, t.y, w, h, s.x, s.y))
      const labelAt = e.label ? findClearLabelPosition(points, edgeLabelSize(e.label), boxes) : mid
      return (
        <g key={e.id} className="graph-edge">
          <GraphEdgeShape id={e.id} d={d} mid={labelAt} label={e.label} variant={e.variant ?? 'default'} />
        </g>
      )
    })}
  </g>
</svg>
```
