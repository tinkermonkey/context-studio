---
name: heimdall-graph
description: Heimdall component guide for Graph: GraphCanvas (layout modes, popovers, tooltips, custom node and edge renderers), GraphNode, GraphEdge, GraphEdgeShape, GraphToolbar, GraphCollapseControl, GraphInspector, GraphEdgeInspector, DetailDrawer, TopologyNode, HierarchyRow, HierarchyTree, LayeredGraphContext, LayerStack, AdjacencyMatrix, HivePlot, FollowControl, PredicateLabelControl, PlaneLayoutControl, LinkCategoryFilter, LayerList, LayerPairList, BridgeNodeList, ReachInspector, LayeredGraphExplorer, ViewSwitcher, CameraControls, plus useGraphCanvas, usePanZoom, useLayeredGraph, the headless layout engines, the edge geometry utilities and the layered graph framework
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
| `nodes` | `GraphNodeData[]` | required | Nodes to render. Optional under `layout="layer-lanes"` with a `layeredGraph` prop or a `LayeredGraphContext` |
| `edges` | `GraphEdgeData[]` | `[]` | Edges to render. Under `layer-lanes` with shared state, only adds each link's source edge fields (for `edgeTooltip`, `renderEdge`) |
| `layout` | `'manual' \| 'force' \| 'organic' \| 'orthogonal' \| 'galaxy' \| 'force-clustered' \| 'radial-tree' \| 'ux-navigation' \| 'layer-lanes'` | `'manual'` | Layout engine. See [Choosing a layout](#choosing-a-layout) |
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

**Layered lanes** (`layout="layer-lanes"` only; see [`layer-lanes`](#layer-lanes))

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `layeredGraph` | `LayeredGraphState` | context | Shared state from `useLayeredGraph`. Unset: the enclosing `LayeredGraphContext`, else the canvas builds its own from `nodes`/`edges`/`layering` |
| `layering` | `BuildLayeredIndexOptions` | `{ layerBy: 'kind', missingValue: 'layer' }` | Standalone layering of `nodes`; memoize it. Ignored with `layeredGraph` or a context |
| `layeredGraphOptions` | `Omit<UseLayeredGraphOptions, 'nodes' \| 'edges' \| 'layering'>` | — | Standalone selection, follow, filters, label mode, in-layer layout |
| `laneOptions` | `LaneLayoutOptions` | — | `orientation` (`'horizontal'` default, `'vertical'`), `order` (`NodeOrder`, default coupled position along the lane), `maxRowWidth` (px before a lane wraps; 1120, or 640 as column height when vertical), `intraLinks` (`'arc'` default, `'bundled'`, `'none'`), `skipLayerRouting` (`'direct'` default, `'gutter'`), `nodeLabels` (`LaneNodeLabels`: `'all'` or `'reached'`; default from the layered state's `nodeLabels`, `'all'` when on) |

**Interaction overlays**

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `nodeTooltip` | `(node) => ReactNode` | — | Content shown near a hovered (or clicked) node |
| `nodeTooltipTrigger` | `'hover' \| 'click'` | `'hover'` | `'click'` renders the content in a `Popover` (`role="dialog"`), so it can hold buttons and links |
| `edgeTooltip` | `(edge) => ReactNode` | — | Same, for a hovered (or clicked) edge. A hover tooltip sits beside the edge's label, or its path midpoint if it has no label |
| `edgeTooltipTrigger` | `'hover' \| 'click'` | `'hover'` | Same as `nodeTooltipTrigger`, for edges |
| `tooltipDelay` | `number` | `200` | Hover delay in ms before a `'hover'` `nodeTooltip`/`edgeTooltip` shows |
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
| `attributes` | `Record<string, GraphAttributeValue \| GraphAttributeValue[]>` | Free-form data. GraphCanvas ignores it; the layered graph framework reads one attribute as the node's layer (`layerBy`) and `description` as inspector text |

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
| `attributes` | `Record<string, GraphAttributeValue \| GraphAttributeValue[]>` | Free-form data. GraphCanvas ignores it; the layered graph framework can read a link category from it (`linkCategoryBy`) |

`EdgeGeometry` (second argument of `renderEdge`): `{ path, mid, labelPos, labelHidden?, angle, selected, hovered }`. `path` is the SVG `d` string actually drawn (an orthogonal polyline under `layout="orthogonal"`), `mid` the path midpoint, `labelPos` the collision-cleared label center, `angle` the tangent at the midpoint in radians. `labelHidden` is `true` while the default renderer would not draw the label: it has no spot clear of the nodes and other labels (until the edge or an endpoint is hovered or selected), or a node drag is moving its route.

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
| `layer-lanes` | Layered graphs (a layering attribute on every node): how layers connect | `layering` or a `LayeredGraphContext` | Proof of concept |

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
- Limits: relational edges can cross bodies. Orbits stay evenly spaced (each satellite gets 0.5-1.5× an equal angular share), and that wins over round systems: a parent with many satellites or one dominant branch comes out elongated, up to about 8:1 (GBIF Rodentia root, 102 satellites) and 5.6:1 (Vespertilionidae, 78 satellites).

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


#### `layer-lanes`

A layered graph as swimlanes: one lane per layer (a layer-coloured band with an uppercase title and node count), nodes as monospace boxes packed into rows in the framework's lane order (their position in the coupled in-layer solve, so linked nodes line up and cross-layer links mostly run straight). Links within a layer are arcs above their row; links between layers are curves across the gap. Links take the layered framework's emphasis (category colour and dash, the amber reach ramp around the selection, dimming), with arrowheads and predicate pills per `predicateLabels`, placed along the curves with `placeEdgeLabels` and dropped where they would overlap.

- The drawn graph is the layered index: one node per node instance (`multiValue: 'all'` copies included), one link per bundled link. With shared state it comes from the state, not from `nodes`/`edges`.
- Keyboard (default lane node): the lane nodes are one Tab stop (roving focus), entering at the focused node, else the selection, else the last focused, else the first node. Arrow keys follow the screen: in horizontal lanes Up/Down move to the next lane and Left/Right along the lane (row order); in vertical lanes Left/Right move between lanes and Up/Down along one. A lane move lands on the nearest node linked by a cross-layer link, else the nearest node, preferring the row next to the gap in a wrapped lane; empty lanes are skipped, and a key at the edge does nothing (and doesn't pan). Home/End go to the lane's first and last node, Enter/Space selects, Escape clears. Reading order follows live positions, so a dragged node is read where it sits. A focused node is panned into view (the smallest pan; not while locked). The keys are in each node's `aria-describedby` hint (visually hidden with `heimdall-visually-hidden`). If the focused node's layer is hidden or filtered out, focus moves to the nearest remaining node. A custom `renderNode` keeps its own focus handling; other layouts keep one Tab stop per node.
- Selection is the layered state's: clicking a node (or Enter/Space on it) selects it, again clears; the background or Escape clears. `selectedNodeId` is ignored; `onNodeSelect` still fires. Share the state with `AdjacencyMatrix`, `HivePlot` and the chrome controls through `LayeredGraphContext`.
- Inherits tooltips, popovers, `renderNode`, `renderEdge` (the lane curve as `path`), pan and zoom, fullscreen, drag and the toolbar. Edge callbacks receive one `GraphEdgeData` per link (`label` = its predicates joined with ` · `).
- `laneOptions.orientation: 'vertical'` puts the lanes side by side as columns, for narrow containers.
- `laneOptions.nodeLabels: 'reached'` draws the default node as a 24px chip (compact horizontal lanes) and names only the selection and its reach, in tags beside their chips placed clear of chips, titles, link ends and pills (dropped where none fits), plus the hovered and keyboard-focused node. Unset, it follows the layered state's `nodeLabels`, so `LinkCategoryFilter`'s label toggle and the explorer's apply to lanes; with `fitView` the canvas fits again after a switch. A custom `renderNode` is unaffected (and the explorer hides its toggle on Lanes when `lanesProps` sets `renderNode` or `laneOptions.nodeLabels`).
- `laneOptions.intraLinks: 'bundled'`: links within a layer run from the node to a trunk just above its row (left of its column, vertical), along it and into the target, so every link in a row shares one line that fans out at each node. Links between neighbouring rows share the lower row's trunk, in the gap between the rows, leaving the upper node from its bottom (right) edge, so they never pass behind another node; links two or more rows apart draw as arcs. The selection's reach draws unbundled, as arcs on top. Hovering or keyboard-focusing a node fans its own links out as arcs, with their pills moved onto the arcs (drawn only: placement doesn't re-run); nothing fans out during a drag. Arrowheads and pills sit on the bundled paths, and a drag holds pill placement until release as in every mode. A link on a trunk has no hit path (on a shared line only the topmost would answer), so reach it through selection or a node hover. With `nodeLabels: 'reached'`, name tags keep off the trunks. `laneBundler(boxes, orientation)` gives `trunkFor(a, b)` (null for rows too far apart) and `trunkBoxes`, and `laneBundleCurve(a, b, trunk, orientation)` the bundled path, for custom renderers.
- `laneOptions.skipLayerRouting: 'gutter'`: links whose ends are two or more lanes apart run along the gap next to their lane to a gutter outside the lanes (left or right of horizontal lanes, above or below vertical ones, whichever is nearer), along it, and back in next to the target lane, instead of crossing the lanes between. A node's routes to one gutter share a stub (one gap track, a trunk that fans out into their gutter tracks); otherwise no two routes share a line: gap tracks 3 to 6px apart (a gap widens rather than go under 3px), and gutter tracks 8px apart, tightening to 3px past about 200px. A route that spans another runs outside it, and routes whose spans don't overlap share a gutter track. Pills and arrowheads follow the routes. During a drag, routes keep their tracks and only the dragged node's stubs move; they are routed again on release. `fitView` frames the gutters at mount, but switching `skipLayerRouting` at runtime doesn't refit.
- With a `layeredGraph` prop or a `LayeredGraphContext`, `nodes` and `edges` can be left out.
- While a node is dragged, pills keep their placement and ride their links; they are placed again on release.
- The geometry is exported for custom renderers: `layoutLanes(index, layout, { sizeOf, hiddenLayers, ...LaneLayoutOptions })` returns a `LaneLayout` (node centres, `LaneBand`s, bounds; `LayoutLanesInput` is its input type); `laneLinkCurve(sourceBox, targetBox, cross, orientation)` returns a `LaneLinkCurve` (an `EdgeCurve` plus arrow `tip` and `dir`) between two `LaneNodeBox`es. `LaneOrientation` is `'horizontal' | 'vertical'`. For gutter routing, pass `skipLayerRouting: 'gutter'` and `gutterLinks` (the cross-layer links on drawn layers, before category or pair filters) to `layoutLanes`, so each gap is wide enough for its tracks (`laneGutterGapTracks(links, layerOf, layerIds)` counts them per gap); without them the gaps stay 70px and tracks crowd. `routeLaneGutters(links, boxOf, layerOf, laneLayout)` returns `LaneGutterRoutes`: `curves` by link id for the `LaneGutterLink`s that skip a lane, their `bounds`, and each route's `tracks` (`LaneGutterTrack`). `retraceLaneGutters(tracks, boxOf, orientation)` rebuilds the routes from held tracks and live boxes, so a drag moves only the dragged node's stubs. For `nodeLabels: 'reached'` chips, `laneTagSize(text)` is a name tag's box and `laneTagRoom(text)` the room it takes beside its chip (pass it as `sideRoomOf` for vertical lanes).
- Limits: dense layers (near-cliques) draw many arcs; set `laneOptions={{ intraLinks: 'bundled' }}` to merge them into row trunks, or `intraLinks: 'none'` / `filters.showIntra: false` to read only the cross-layer links. Bundled trunks show that a row's nodes are linked, not which pairs: hover, focus or select a node to see its own links. In a lane wrapped into three or more rows, links between rows two or more apart stay arcs. Links that skip a layer cross the lane between unless `skipLayerRouting: 'gutter'`. With gutters, a stub from a node in an upper row of a wrapped lane passes through the rows below it, a pill can sit over neighbouring tracks, and on a dense graph the lanes grow: at 1,600 links over 13 lanes the gaps widen to about 165px (horizontal lanes about 1.5× taller) and the gutters add about 2,500px of width (horizontal lanes about 1,144 → 3,700px; vertical lanes are about 4,200px wide). Filters don't change the gaps, so toggling a category or picking a layer pair leaves the lanes where they are.

```tsx
import { GraphCanvas, useLayeredGraph, LayeredGraphContext } from '@tinkermonkey/heimdall-ui'

// Standalone
const layering = useMemo(() => ({ layerBy: 'tier', linkCategoryBy: 'category' }), [])
<GraphCanvas layout="layer-lanes" nodes={nodes} edges={edges} layering={layering} fitView />

// Shared with other layered views
const graph = useLayeredGraph({ nodes, edges, layering })
<LayeredGraphContext.Provider value={graph}>
  <GraphCanvas layout="layer-lanes" laneOptions={{ orientation: 'vertical' }} fitView />
  <AdjacencyMatrix />
</LayeredGraphContext.Provider>
```
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

- `nodeTooltip` / `edgeTooltip` with the default `'hover'` trigger: a non-interactive `role="tooltip"` overlay after a hover delay (`tooltipDelay`, default 200 ms), linked to its target with `aria-describedby`. Lengthen `tooltipDelay` when nodes or edges are also click targets, so the card doesn't appear over what the user is aiming at.
- Hover tooltip placement: the card sits 6 px beside its anchor and never covers it. The anchor is the node's box; for an edge, the edge's drawn label (wherever label placement put it), or the path midpoint when the edge has no visible label. It tries above, then below, then right, then left, takes the first side with room inside the visible canvas, and is clamped into it. It follows pan, zoom and drag. Don't measure the edge label yourself to position your own card; pass `edgeTooltip`.
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

Honouring `geometry.labelHidden` is opt-in: a custom renderer draws its label regardless unless it checks the flag, e.g. `visibility={geometry.labelHidden ? 'hidden' : undefined}` on the label element.

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
- Each node's box (layout footprint, `<foreignObject>` size, edge clipping) is the measured margin box of what `renderNode` returns (its root element, margins included): the width rounded up to a whole pixel, the height exact. Host CSS that takes the node out of flow, such as `.graph-node { position: absolute }` or a global rule matching the node's element, collapses the measurement to 0x0; the node then falls back to a 138x30 box and edges land tens of px away from the real outline. Development builds log a `GraphCanvas: node "…" measured 0x0` warning once per node when this happens.
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
| `labelHidden` | `'no-room' \| 'drag'` | — | Hides the label pill. It stays in the DOM with `visibility: hidden` and `data-label-state` set to the reason. GraphCanvas sets `'no-room'` for a label with no clear spot until the edge or an endpoint is in focus, and `'drag'` while a node drag moves its route |
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
  hop?: number          // layered graphs: 1 direct, 2+ followed; >1 shows a +n badge
  via?: { id: string; title: string; predicate: string }  // shown as "via X · predicate"
  layer?: { id: string; label: string; color: string }    // fills the row swatch
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

## Layered graph framework

The shared layer behind the layered views (3D layer stack, lanes, block matrix, hive). It takes the same `GraphNodeData` / `GraphEdgeData` as GraphCanvas and turns one node attribute into layers. Use it to drive the layered views or to build your own view or controls on the same state. Nothing in it is specific to any data source.

```tsx
import {
  useLayeredGraph,
  LayeredGraphContext,
  useLayeredGraphContext,
  buildLayeredIndex,
  computeReach,
  linkEmphasis,
} from '@tinkermonkey/heimdall-ui'

// Memoize `layering`: a new object rebuilds the index.
const layering = useMemo(() => ({
  layerBy: 'tier',                     // attributes.tier, or 'kind' / 'domainColor', or (node) => value
  multiValue: 'first',                 // 'first' | 'last' | 'exclude' | 'all' (one instance per value)
  missingValue: 'exclude',             // or 'layer': collect them on an "Unassigned" layer
  layers: [{ id: 'business', label: 'Business' }, { id: 'application' }],  // order, labels, colors
  linkCategoryBy: 'category',          // edge.attributes.category; falls back to `catalog`, then 'other'
  categoryOrder: ['structural', 'behavioral'],
}), [])

const graph = useLayeredGraph({ nodes, edges, layering, defaultFollow: 1 })

<LayeredGraphContext.Provider value={graph}>
  {/* views and controls read it with useLayeredGraphContext() */}
</LayeredGraphContext.Provider>
```

### Vocabulary

- **Layer**: a distinct value of the `layerBy` attribute, as a string. `layers` sets order, label and color for known values; unlisted values follow in first-appearance order. Colors default to the `--graph-layer-1…12` palette by rank (`layerPaletteColor`, `LAYER_PALETTE_SIZE`).
- **Link**: every edge between the same two node instances in the same direction, bundled. An edge's `label` is its predicate, read source to target. A→B and B→A stay separate links.
- **Cross-layer link**: ends on different layers. `pairKey` names the unordered layer pair (`layerPairKey`).
- **Reach**: what a selection lights up. Hop 1 is every link of the selected node; with `follow` > 0 it continues from nodes reached over cross-layer links, along cross-layer links, into any layer but the selected node's own ("away from the clicked layer").

### useLayeredGraph

`useLayeredGraph(options): LayeredGraphState`. Every piece of state is controlled when its prop is set (with an `on…Change` callback) and otherwise held by the hook, seeded from its `default…` prop.

| Option | Type | Description |
| ------ | ---- | ----------- |
| `nodes`, `edges` | `GraphNodeData[]`, `GraphEdgeData[]` | Same data as GraphCanvas |
| `layering` | `BuildLayeredIndexOptions` | `layerBy` (required), `multiValue`, `missingValue`, `missingLayerLabel`, `layers`, `linkCategoryBy`, `catalog`, `fallbackCategory`, `categoryOrder`, `maxLabelLength` |
| `layout` | `LayerLayoutOptions \| false` | In-layer layout options; `false` skips layout |
| `asyncLayoutMinNodes` | `number \| false` | Opt-in asynchronous layout (`layoutLayersAsync`) from this many nodes. Default `false` (synchronous, as before); `ASYNC_LAYOUT_MIN_NODES` (200) is the recommended value, `0` always. Requires memoized `nodes`, `edges`, `layering` and `layout`, including any `nodeSize`: a `layout` or `nodeSize` rebuilt every render restarts the run forever (dev warning). Without a custom `nodeSize`, an index rebuilt with equal content reuses the landed result (dev warning); with one, only the same index does. `layoutPending` is true while a run is in flight. `layout` is null until the first run lands, then keeps the last landed result while a newer run is pending. On first load the views draw their fallbacks (circles in `LayerStack`, `degree` order in `AdjacencyMatrix` and lanes) and reorder once the layout lands |
| `selectedId` / `defaultSelectedId` / `onSelect` | `string \| null` | Selected node instance: the single-select path. With several selected, the primary (first of `selectedIds`); `onSelect` fires on every `select` and `restore`. The other selection and filter actions (`setSelectedIds`, `toggleSelected`, `toggleLayer`, `setFilters`, …) fire it when they change the visible primary (the first selected node in the graph and not on a hidden layer), with that node. A parent changing a controlled `filters` or `selectedIds` prop is not reported back |
| `selectedIds` / `defaultSelectedIds` / `onSelectedIdsChange` | `string[]` | Multi-select: every selected node, primary first. Wins over `selectedId`. Controlling only `selectedId` keeps the selection to one node |
| `follow` / `defaultFollow` / `onFollowChange` | `number` | Followed hops past the direct links. Default 1 |
| `followCategories` | `string[] \| null` | Follow only links in these categories |
| `filters` / `defaultFilters` / `onFiltersChange` | `LinkFilterState` | Hidden layers, categories, predicates; intra-layer links; layer pair |
| `predicateLabels` / `defaultPredicateLabels` / `onPredicateLabelsChange` | `'off' \| 'highlighted' \| 'all'` | Default `'highlighted'` |
| `focusedLayerId` / `defaultFocusedLayerId` / `onFocusLayer` | `string \| null` | Emphasized layer |
| `planeLayout` / `defaultPlaneLayout` / `onPlaneLayoutChange` | `'independent' \| 'coupled'` | Which in-layer layout the views show |
| `nodeLabels` / `defaultNodeLabels` / `onNodeLabelsChange` | `boolean` | Node labels on (default) or off. `LayerStack` (`all` / `reached`) and `HivePlot` (`axisLabels` 1 / 0) default to it, and `LinkCategoryFilter`'s label toggle writes it |
| `linkStyles` | `Record<string, LinkCategoryStyle>` | Per-category color and dash overrides. Memoize it: a new object recomputes every link's emphasis |

A selected node on a hidden layer (or missing from the graph) reads as not selected, and hiding a layer drops the selected nodes on it. Filter and selection actions compose when called together in one handler. It returns `index`, `layout`, `layoutPending`, `reach`, `hoverReach` (direct links of the hovered node), `pairNodeIds`, the current state values (`selectedId`, `selectedIds`, `nodeLabels`, …), actions (`select`, `setSelectedIds`, `toggleSelected`, `hover`, `setFollow`, `setFilters`, `toggleCategory`, `togglePredicate`, `toggleLayer`, `setShowIntra`, `setLayerPair`, `setPredicateLabels`, `focusLayer`, `setPlaneLayout`, `setNodeLabels`), `linkEmphasis(link)` and `nodeEmphasis(node)` bound to the current state, and a serializable `snapshot` (`LayeredGraphSnapshot`, with `selectedIds` and `nodeLabels`) with `restore(snapshot)`. `restore` applies whichever of `selectedId` / `selectedIds` the caller changed against the current state, so `restore({ ...snapshot, selectedId })` and `restore({ ...snapshot, selectedIds })` both work; if both changed and disagree, `selectedId` wins. It restores filters before the selection and always calls `onSelect` (the given id, or the visible primary of the given ids). The public `setFilters` composes with the other actions in one handler.

**Multi-select is reserved, not finished.** The state, actions and reach are in place: `select(id)` replaces the selection, `toggleSelected(id)` adds or removes one node, `setSelectedIds(ids)` sets them all, and the reach is the union of each node's reach (every selected node is hop 0; others keep their lowest hop). The views still select one node per click (no shift-click yet) and draw the primary's drill-through and inspector; nodes in the selection beyond the primary light up through the reach. Single-select code needs no change: `selectedId` / `onSelect` work as before.

`useControllable(value, defaultValue, onChange)` is the hook's `value` / `default…` / `on…Change` pattern, exported for custom views and chrome: it returns `[current, set]`, controlled when `value` is defined (`null` counts as a value).

## LayeredGraphContext

A React context that shares one `useLayeredGraph` result with every layered view and control below it, so they show the same selection, filters and follow depth.

```tsx
const graph = useLayeredGraph({ nodes, edges, layering })

<LayeredGraphContext.Provider value={graph}>
  <MyFollowControl />
</LayeredGraphContext.Provider>

function MyFollowControl() {
  const { follow, setFollow } = useLayeredGraphContext() // throws outside a provider
  return <SegmentedControl value={follow} onChange={(v) => setFollow(Number(v))} options={[{ value: 0, label: 'Direct' }, { value: 1, label: '+1 layer' }]} />
}
```

| Prop | Type | Description |
| ---- | ---- | ----------- |
| `value` | `LayeredGraphState` | The `useLayeredGraph` result to share |

### Headless functions

| Function | Signature | Returns |
| -------- | --------- | ------- |
| `buildLayeredIndex` | `(nodes, edges, options: BuildLayeredIndexOptions)` | `LayeredIndex`: layers, node instances, bundled links, lookups, `layerPairs`, `categoryCounts`, `categories`, `predicateCodes`, `issues` |
| `readLayerValues` | `(node, layerBy)` | The node's layer values as strings |
| `computeReach` | `(index, origin: string \| string[] \| null, { follow?, followCategories?, filters? })` | `ReachResult`: `originId`, `originIds`, `hopOf`, `linkHop`, `via`, `maxHop`. Several origins reach the union, each node at its lowest hop; one reach per origin, so O(k · reach) |
| `reachPath` | `(reach, nodeId)` | `{ nodeIds, linkIds }` from the origin to the node |
| `isLinkVisible` | `(link, index, filters)` | Whether a view draws the link |
| `isLinkTraversable` | `(link, index, filters)` | Whether reach may cross it (ignores `showIntra` and `layerPair`) |
| `isNodeVisible`, `visiblePredicates`, `layerPairNodeIds` | | Filter helpers. `DEFAULT_LINK_FILTERS` hides nothing |
| `linkEmphasis` | `(link, ctx: EmphasisContext)` | `{ visible, hop, highlighted, color, dash, width, opacity, z, arrow, label }` |
| `nodeEmphasis` | `(node, ctx)` | `{ hop, selected, followed, opacity, tint }` |
| `linkCategoryStyle`, `linkCategoryStyleAt` | `(category, ctx)`, `(i)` | Category color token `--graph-link-<n>` and dash. `LINK_CATEGORY_PALETTE_SIZE` = 6. `HOP_COLORS` holds the reach ramp |
| `layoutLayers` | `(index, { engine?, layoutCategories?, nodeSize?, organic? })` | `{ independent, coupled, scale }`: positions in [-1, 1] per layer (independent) and with cross-layer links pulling linked nodes into line (coupled) |
| `layoutLayersAsync` | `(index, options?, { signal? }: LayoutLayersAsyncOptions)` | `Promise<LayerLayoutResult>`: the same result as `layoutLayers`, one solve at a time with `yieldToPaint` before each (each layer, then the coupled solve), so large graphs don't block for the whole run. `signal` aborts between solves (rejects with an `AbortError`) |
| `mixLayerPositions` | `(layout, mix: 0..1)` | Positions tweened between independent and coupled |
| `orderWithinLayers`, `orderAcrossLayers` | `(index, layout, order?: 'coupled-x' \| 'degree' \| 'cross-degree' \| 'label' \| comparator)` | Node order per layer (lanes) or across layers (matrix rows) |
| `rankWithinLayers` | `(index, by?, groups?)` | Position along a layer axis in [0, 1) (hive); busiest last by default; `groups` ranks within other node groups (hive axes by attribute) |
| `assignPredicateCodes` | `(predicates, catalog?)` | Unique two-letter codes for matrix cells |
| `linkPredicateLabel` | `(link, catalog, predicates?)` | Predicates joined with ` · ` |
| `arrowHeadPoints` | `(tip, ux, uy, length?, halfWidth?)` | SVG `points` for an arrowhead pointing along (ux, uy) |
| `lineCurve`, `quadCurve`, `cubicCurve` | `(a, b)`, `(a, c, b)`, `(a, c1, c2, b)` | `EdgeCurve`: SVG `d` plus `pointAt(t)` and unit `tangentAt(t)`, for drawing an edge and sampling it for labels and arrowheads |
| `placeEdgeLabels` | `(candidates: EdgeLabelCandidate[], { obstacles?, ts?, size?, gapX?, gapY? })` | `PlacedEdgeLabel[]`: greedy pill placement in priority order, each candidate trying `ts` (`DEFAULT_LABEL_TS` = .5, .36, .64, .24, .76) along its own edge; a pill with no clear spot is dropped. `LabelBox` boxes are centered. `defaultPillSize` sizes a 9.5px mono pill |
| `edgeLabelPriority` | `(link, emphasis)` | Placement priority: reached links by hop, then the rest; cross-layer before intra-layer |

Colors are tokens with light and dark canvas values: `--graph-hop-1…3` (reach ramp), `--graph-link-1…6` (categories by position), `--graph-layer-1…12` (layers by rank), `--graph-pill-bg`, `--graph-plane-fill-alpha`. Use them as `rgb(var(--graph-hop-1))`.

## LayerStack

The layered graph as a 3D stack: one translucent plane per layer (with a grid and a clickable title showing node and link counts), nodes as layer-coloured discs sized by degree, intra-layer links on their plane and cross-layer links between planes. Drawn as SVG with a perspective projection, so it stays crisp, accessible and snapshot-testable; tested at the full DR spec (13 layers, 193 nodes, about 900 links).

- **Selection:** click a node (again to clear; click the background to clear). The reach lights in the amber hop ramp with arrowheads and predicate pills (`placeEdgeLabels` over the projected links), and a **drill-through column** (dashed vertical through every plane, a ring on each other plane) shows what sits above and below the node.
- **Labels:** node labels, plane titles and pills are an HTML overlay positioned in percentages: upright and crisp at any angle. Node labels are buttons with roving focus: Left/Right move within a layer, Up/Down move to a linked node (or the first node) on the next layer, Home/End, Enter selects, Escape clears. `nodeLabels` picks which are visible; hidden ones stay focusable. A label whose node sits behind another layer's plane fades to 30% of its emphasis opacity (faded, not hidden, so it does not pop in and out during an orbit; class `layer-stack__label--occluded`). The selection, its reach, the hovered and the keyboard-focused node never fade; planes dimmed by a layer focus fade nothing; top view, the x-ray, fades nothing.
- **Camera:** drag to orbit (pitch clamped; a 4px threshold keeps clicks as clicks), wheel zoom only while the scene has focus, two-finger pinch zoom (same 0.4–3 clamp), presets `stack` / `exploded` / `top` (x-ray; plane titles move to a side rail) / `profile`, a turntable, and the layer gap. Moves tween 600–900 ms ease-in-out and jump under `prefers-reduced-motion`, which also disables the turntable. Each camera field, the gap, each layer's focus and the plane layout tween on their own channels, so a later move replaces only what it names: a focus right after a preset keeps the preset's yaw turning. An orbit, wheel or pinch stops the camera move; the planes still settle. **Tall stacks:** a preset's frame on a stack of more than five layers is fitted when the planes would overflow it (same angles, the zoom that fits, target centred). This applies on mount (a jump, reported once as `fit`), when the data arrives or its layer count changes (a `fit` move toward the preset's destination), and when a preset is picked (its move goes to the fitted frame). The preset stays active. It is skipped with no preset, a controlled `camera`, a `defaultCamera` zoom or target other than the preset's own, a focused layer, or five layers or fewer.
- **Layer focus:** the graph's `focusedLayerId` (plane title click, `LayerList`, or `focusLayer`): planes above and below move apart, the camera tilts toward the plane and the other layers dim. Clicking the title again exits. Switching straight to another layer eases from where the planes are (one layer closes as the other opens).
- **Controlled camera and gap:** `camera` fields and `layerGap` are held. The view shows the props only; an orbit, zoom, preset, focus or turntable reports every frame through `onCameraChange` / `onLayerGapChange` and moves the view only when the parent passes the value back (like `SplitPane`'s `splitPercent`). Pass each report back unchanged: a value the stack never reported (rounded or normalized) counts as a change from outside, which jumps and stops the stack's move on that field. An echo that lands a frame or more late (React batching on a slow device) still counts as the stack's own. The settle report carries the move's last proposal, so a parent that commits only settled reports still gets the gesture.
- **Plane layout:** the graph's `planeLayout` tweens between the independent and coupled in-plane layouts (`mixLayerPositions`).
- **Performance:** camera state lives in refs. React renders the scene's structure (elements, colours, emphasis, events); a frame (tween, orbit, zoom, turntable) only paints, writing the projected geometry and depth order straight into those elements, so the React tree commits only when the data, selection or emphasis change and once when motion starts and settles. Links off the selection's reach are drawn as one SVG path per style (colour, opacity, dash, stroke width rounded to 0.1; class `layer-stack__link-batch`, `data-link-count`; arrowheads `layer-stack__arrow-batch`), so a frame rewrites a few dozen paths, not one per link; links in one batch don't darken each other where they cross. Only the reach keeps a path per link (`layer-stack__link[data-link-id]`) and arrowhead (`layer-stack__arrow`). Uncontrolled, `onCameraChange` fires only when a move settles (drag release, end of a tween, a wheel pause, pinch release, turntable stop). A controlled `camera` reports every frame, so its parent re-renders while the camera moves. For chrome that only shows or remembers the camera, leave `camera` and `layerGap` uncontrolled (`defaultCamera`, `defaultLayerGap`) and listen to the settle callbacks, so the chrome doesn't re-render on orbit. Pills are skipped while dragging and placed again on release.

The math is in `projection.ts`, free of React: `createProjector(camera, options)` maps a world point to screen `{ x, y, scale, depth }`; `stackPlaneY`, `planeCorners`, `planeGridLines` and `ringPoints` build the world model; `depthSort` is the painter's order; `presetLayerGap(name, layerCount)` gives a preset's gap for a stack of that many layers (the preset's own up to `PRESET_GAP_FULL_LAYERS` = 5 layers, closer together beyond, so a 13-layer stack keeps the height of five); `fitZoom`, `clampCamera`, `nearestYaw`, `lerpCamera`, `wrapAngle`, `cameraFromPreset`, `projectPoint`, `svgPoints`, `leftmostPoint`, `screenBounds` and `titleRail` round it out, with the constants `CAMERA_PRESETS`, `CAMERA_PRESET_NAMES`, `PITCH_RANGE`, `ZOOM_RANGE`, `DEFAULT_CAMERA_DISTANCE` and `TOP_VIEW_PITCH`. `useTween(onFrame)` returns `{ start(from, to, { duration, easing, onDone }), cancel, isActive, reducedMotion }` and is shared by any animated view (a new start replaces the whole running tween); `usePrefersReducedMotion`, `easeInOutCubic`, `interpolateValues` and `REDUCED_MOTION_QUERY` come with it.

```tsx
import { LayerStack, useLayeredGraph, LayeredGraphContext, type LayerStackHandle } from '@tinkermonkey/heimdall-ui'

// Standalone:
const layering = useMemo(() => ({ layerBy: 'tier', linkCategoryBy: 'category' }), [])
<LayerStack nodes={nodes} edges={edges} layering={layering} />

// Shared state, app-driven camera:
const graph = useLayeredGraph({ nodes, edges, layering })
const stack = useRef<LayerStackHandle>(null)
const [preset, setPreset] = useState<CameraPresetName | null>('stack')
<LayeredGraphContext.Provider value={graph}>
  <LayerStack
    ref={stack}
    cameraPreset={preset}
    onCameraPresetChange={setPreset}
    onCameraChange={(camera, cause) => setStatus(camera)}
    nodeLabels="reached"
    interactions={{ zoom: false }}
  />
  <Button onClick={() => stack.current?.fit()}>Fit</Button>
</LayeredGraphContext.Provider>
```

Ref handle (`LayerStackHandle`): `applyPreset(name, { animate })`, `setCamera(partial, { animate })`, `getCamera()`, `getLayerGap()`, `zoomBy(factor)`, `fit()`, `setTurntable(on)`, `focusLayer(id | null)`, `select(id | null)`, `setFollow(n)`, `element()`. `onCameraChange` causes (`LayerStackCameraCause`): `orbit`, `zoom`, `preset`, `focus`, `fit`, `turntable`, `api`. `LayerStackInteractions` and `LayerStackNodeLabels` type the props below; `LayerStackMoveOptions` is the `{ animate }` argument.

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `graph` | `LayeredGraphState` | context | State from `useLayeredGraph`. Unset: the enclosing `LayeredGraphContext`, else its own from `nodes`/`edges`/`layering` |
| `nodes` | `GraphNodeData[]` | — | Standalone nodes; ignored with `graph` or a context |
| `edges` | `GraphEdgeData[]` | — | Standalone edges; ignored with `graph` or a context |
| `layering` | `BuildLayeredIndexOptions` | — | Standalone layering (`layerBy`, …); memoize it |
| `graphOptions` | `Omit<UseLayeredGraphOptions, 'nodes' \| 'edges' \| 'layering'>` | — | Standalone selection, follow, filters, focus, plane layout |
| `cameraPreset` | `'stack' \| 'exploded' \| 'top' \| 'profile' \| null` | — | Controlled preset; a new value animates to it. Becomes `null` when the camera is moved by hand |
| `defaultCameraPreset` | `CameraPresetName` | `'stack'` | Initial preset when uncontrolled |
| `onCameraPresetChange` | `(preset: CameraPresetName \| null) => void` | — | Preset applied or cleared |
| `camera` | `Partial<StackCamera>` | — | Controlled `{ yaw, pitch, zoom, targetY }`. The fields set are held: moves only report through `onCameraChange` until the prop changes; a change from outside jumps. Fields left out stay uncontrolled |
| `defaultCamera` | `Partial<StackCamera>` | — | Initial camera fields over the initial preset |
| `onCameraChange` | `(camera: StackCamera, cause: LayerStackCameraCause) => void` | — | Called when a camera move settles, not per frame. With `camera` set, also every frame of a move (the proposed camera) |
| `turntable` | `boolean` | — | Controlled slow yaw. Off under reduced motion; turns off when the user orbits |
| `defaultTurntable` | `boolean` | `false` | Initial turntable when uncontrolled |
| `onTurntableChange` | `(on: boolean) => void` | — | Turntable toggled (including off on orbit) |
| `turntableSpeed` | `number` | `0.27` | Turntable speed, radians per second |
| `layerGap` | `number` | — | Controlled distance between planes, world units; held like `camera` (a preset's gap move only reports) |
| `defaultLayerGap` | `number` | preset's | Initial gap when uncontrolled: the preset's (170 for `stack`), closer together past five layers (`presetLayerGap`) |
| `onLayerGapChange` | `(gap: number) => void` | — | Gap changed by a preset, when its move ends; with `layerGap` set, also every frame |
| `nodeLabels` | `'all' \| 'reached' \| 'none'` | graph state | Which node labels show; the hovered or keyboard-focused node always does. Unset: `all` while the graph's `nodeLabels` is on, `reached` when off |
| `interactions` | `LayerStackInteractions` | all on | `{ select, hover, orbit, zoom, focusLayer }`: turn direct manipulation off per kind (`zoom` covers wheel and pinch) |
| `sceneWidth` | `number` | `1160` | Scene (viewBox) width; with `sceneHeight` sets the aspect ratio |
| `sceneHeight` | `number` | `780` | Scene (viewBox) height |
| `planeSize` | `number` | `300` | Plane half-width in world units; every plane shares it, so the stack reads square |

### Gotchas

- The scene keeps the `sceneWidth / sceneHeight` aspect ratio at 100% width; size it with its container's width.
- Wheel zoom needs focus in the scene (click it, or tab to a node), so it never hijacks page scroll.
- A changed `camera` prop is a jump; use the ref's `setCamera(c, { animate: true })` or a preset to animate (with `camera` set, pass each reported frame back).
- A controlled `camera` or `layerGap` whose parent ignores `onCameraChange` / `onLayerGapChange` freezes those fields: that is the hold, not a bug.
- Pass reports back unchanged; rounding or normalizing the value reads as a change from outside and stops the stack's move.
- Touch: one-finger vertical swipes still scroll the page (`touch-action: pan-y`); with two fingers down on the scene it cancels `touchmove`, so a pinch is not taken as a scroll. Place both fingers together: a second finger added after a one-finger scroll has started cannot pinch, because the browser already owns that touch.

## AdjacencyMatrix

A directed block adjacency matrix of a layered graph. There is one row and one column per node, grouped by layer, and one cell per link (row = source, column = target). Diagonal blocks hold links within a layer; off-diagonal blocks hold links between two layers, with a count in the corner. Every link is visible and nothing crosses, so it stays readable on dense graphs where node-link drawings tangle.

- **Cell colours:** each cell takes its link's category colour. Around the selection, cells take the amber reach ramp instead, including followed hops.
- **Codes:** cells show two-letter predicate codes per `predicateLabels`, with a legend of the codes in view.
- **Selection:** a row header (a focusable button, Enter or Space) or the matching column header selects a node; selecting it again clears it. Clicking a cell selects the link's source, or calls `onCellSelect(link, links)` instead.
- **Keyboard:** the cells are one Tab stop (roving focus). Arrow Left and Right walk every cell in reading order; Up and Down go to the nearest row above or below with a cell, at the closest column; Home and End go to the row's first and last cell; Enter or Space acts as a click. The focused cell shows the hover crosshair and a focus ring.
- **Screen readers:** a visually hidden HTML grid mirrors the drawing and holds the focus: `role="grid"` (named like the matrix, with `aria-rowcount`/`aria-colcount` = nodes + 1 for the header row and column), a header row of `columnheader`s, and one `row` per node with a `rowheader` (`Label, Layer layer`) and a `gridcell` per drawn cell. Rows carry `aria-rowindex` and cells `aria-colindex` (row or column `i` is `i + 2`), so the size and position are announced when virtualized and only the window renders. A cell's name is `Row A, column B, linked: A serves B` (`linked both ways` for a symmetric cell holding both directions, `, selected` for the `selectedLinkId` cell). In a grid, screen readers pass the arrow keys through, so the key model above works for them too. The drawn cells are `aria-hidden` (pointer only, with their tooltip); the row headers remain the SVG buttons in the `Rows` group. Since 0.12.0; before it, cells were `role="button"` in an SVG `role="group"`.
- **Link inspection:** show a clicked cell with `GraphEdgeInspector` and `linkEdgeMetadata(index, link)` (title = predicates; layers, category and edge count as rows), and pass `selectedLinkId` to outline the cell. `LayeredGraphExplorer` does this for you.
- **Cluster order:** `order="cluster"` runs Louvain (`louvainCluster`) within each layer on that layer's own links, and keeps each community, and each nested community, together; bigger first. It is deterministic: it starts from the `degree` order with edges sorted the same way, so input order never changes it, and filters don't either. Over every link at once the communities would just be the layers, hence per layer.
- **Symmetric:** `symmetric` merges `A→B` and `B→A` into one cell above the diagonal, for an undirected reading. A cell holding both directions has a notch in its lower-left corner (the caption says so), its tooltip lists both links, and `onCellSelect` receives both as its second argument. Block counts add both directions.
- **Layer heat map:** `aggregate="layer"` collapses the matrix to one row and column per visible layer, each cell the count of visible links between the two layers, shaded on a neutral ramp. It is the overview when there are many layers. Clicking a cross-layer cell toggles the layer-pair filter (`setLayerPair`), so the other views narrow to that pair; clicking a diagonal cell or a layer header toggles the layer focus (`focusLayer`). Counts ignore the pair filter, so the overview stays whole and the active pair is outlined. Set `onLayerCellSelect` to handle the click yourself; it receives a `LayerMatrixCell` (`rowLayerId`, `colLayerId`, `linkCount`, `pairKey`, which is null on the diagonal). With `symmetric`, both directions add into the upper triangle.

```tsx
import { AdjacencyMatrix, useLayeredGraph, LayeredGraphContext } from '@tinkermonkey/heimdall-ui'

// Standalone: the matrix builds its own layered-graph state.
const layering = useMemo(() => ({ layerBy: 'tier', linkCategoryBy: 'category' }), [])
<AdjacencyMatrix nodes={nodes} edges={edges} layering={layering} />

// Shared with other layered views and controls:
const graph = useLayeredGraph({ nodes, edges, layering })
<LayeredGraphContext.Provider value={graph}>
  <AdjacencyMatrix order="degree" />
</LayeredGraphContext.Provider>
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `graph` | `LayeredGraphState` | context | State from `useLayeredGraph`. Unset: the enclosing `LayeredGraphContext`, else its own from `nodes`/`edges`/`layering` |
| `nodes` | `GraphNodeData[]` | — | Standalone nodes; ignored with `graph` or a context |
| `edges` | `GraphEdgeData[]` | — | Standalone edges; ignored with `graph` or a context |
| `layering` | `BuildLayeredIndexOptions` | — | Standalone layering (`layerBy`, …); memoize it |
| `graphOptions` | `Omit<UseLayeredGraphOptions, 'nodes' \| 'edges' \| 'layering'>` | — | Standalone selection, follow, filters, label mode |
| `order` | `NodeOrder \| 'cluster'` | `'coupled-x'` | Row and column order within each layer (`'degree'` when there is no layout). `cluster`: Louvain communities within each layer |
| `cellSize` | `number \| 'auto'` | `'auto'` | Cell size in px; `auto` fits about 820px, clamped to 10–18. With `aggregate="layer"`, `auto` fits about 560px, clamped to 40–72, and a number is at least 24 |
| `labelWidth` | `number` | `210` | Row-label column width in px |
| `showBlockCounts` | `boolean` | `true` | Link count in each cross-layer block |
| `showCodeLegend` | `boolean` | `true` | Legend of the predicate codes shown |
| `onCellSelect` | `(link: IndexedLink, links: readonly IndexedLink[]) => void` | — | Cell click handler. Unset: selects the link's source. `link` is the drawn link: in a symmetric cell holding both directions, the reached one, else row → column. `links` holds every link in the cell, row → column first |
| `onLinkSelect` | `(link: IndexedLink, links: readonly IndexedLink[]) => void` | — | **Deprecated:** use `onCellSelect` (same arguments). Ignored when `onCellSelect` is set |
| `selectedLinkId` | `string \| null` | — | Outline the cell holding this link, e.g. the one shown in an inspector. Set from outside, its cell scrolls into view |
| `virtualizeAbove` | `number` | `150` | Above this many nodes, only the rows and columns in view render and the labels stick to the edges |
| `symmetric` | `boolean` | `false` | Merge both directions into one cell above the diagonal |
| `aggregate` | `'none' \| 'layer'` | `'none'` | `layer`: a layers-by-layers heat map of link counts |
| `onLayerCellSelect` | `(cell: LayerMatrixCell) => void` | — | Heat-map cell click handler. Unset: a cross-layer cell toggles the layer-pair filter, a diagonal cell the layer focus |

Large graphs scroll inside the component (it renders at natural size, so cells stay crisp). Past `virtualizeAbove` nodes (default 150) the matrix virtualizes: only the rows and columns in view (plus a margin) render, the row and column labels stick to the left and top while the cells scroll, and the scroll area is capped at `--adjacency-matrix-max-height` (default `80vh`). The sticky labels paint `--adjacency-matrix-bg` (default the canvas background); set it when the matrix sits on another surface. Windowing follows only the matrix's own scroll area: with `--adjacency-matrix-max-height: none`, or a page that scrolls instead, every row renders. In a fixed-height `LayeredGraphExplorer` the matrix fills the scene and is its only scroll area. Below the threshold it draws one SVG as before.


## HivePlot

A hive plot of a layered graph: one radial axis per layer at evenly divided angles, nodes placed outward along their axis by rank (degree by default, busiest farthest out), and links drawn as curves between axes. Each axis is doubled (±13° by default) so links within a layer span the gap between the two copies; cross-layer links run between the facing copies of two axes. It compares how the layers connect rather than where nodes sit. Reads well for 3 to about 6 layers; beyond that, prefer `AdjacencyMatrix`.

- **Link colours:** each link takes its category colour and dash. Around the selection, links take the amber reach ramp, with arrowheads and predicate pills per `predicateLabels` (pills are placed with `placeEdgeLabels` and dropped where they would overlap).
- **Labels:** with no selection, the `axisLabels` busiest nodes per axis are labeled; with one, the selection and its reach. A label is dropped when it would overlap another label, a dot or ring that isn't faded, or an arrowhead (the node's tooltip and accessible name still carry it); the selection is always labeled. Hovering a node labels it, on top, without moving other labels.
- **Selection:** click a node (either copy) or press Enter or Space on it to select; again clears; Escape clears. Clicking a link selects its source, or calls `onLinkSelect`.
- **Keyboard:** the nodes are one tab stop. Arrow Up and Down move outward and inward along the axis, Home and End jump to its ends, Arrow Right and Left move to the next and previous axis at the nearest rank.
- **Sizing:** the SVG fills its container's width at a fixed aspect ratio (viewBox fit). Node hit targets stay at least 24 px across at any scale.
- **Axes by any attribute** (`axes={(node) => axisId}`): one axis per distinct value over every node, so the set of axes doesn't change with filters. The default `'layer'` is one axis per layer.
  - **Node instances:** the function receives `IndexedNode` instances. A node on several layers has one instance per layer (`id@layer`), each placed on its own axis, so two can land on one axis; read `node.nodeId` for the source node (`(n) => kindOf.get(n.nodeId)`).
  - **Memoize** `axes`, `axisOrder` and `axisLabel`. An inline function still works: a grouping that comes out the same is reused, so the rest of the plot doesn't recompute.
  - **Order:** layer order, else axis ids sorted by code point (`'10'` sorts before `'9'`; pass a comparator such as `(a, b) => Number(a) - Number(b)` for numbers); `axisOrder` lists ids to put first (the rest follow) or takes a comparator. Angles run clockwise from `startAngle` in that order.
  - **Colour:** layer colour by layer; otherwise `layerPaletteColor(i)` (the `--graph-layer-<n>` tokens, light and dark) by axis order. Node dots take their axis colour.
  - **Titles:** the layer label, else the axis id; `axisLabel(axisId)` overrides.
  - **Filters and emphasis:** layer filters still hide nodes. An axis left with no visible node leaves a gap, and no angle moves. Selection, reach and link styles are unchanged; links within one axis are drawn like intra-layer links (across the split gap, or as loops).
  - **No axis:** a node the function returns `null`, `undefined` or `''` for is not drawn, nor are its links; a dev-mode warning (once per change) names one. A selection on such a node isn't drawn either: its reach is still labeled, without links to it, and the plot's accessible name adds "selection not shown".
  - **Rank:** `rank="cross-degree"` still counts cross-layer links, not cross-axis ones.
  - `hiveAxisGroups(index, axes, axisOrder)` returns the groups (`HiveAxisGroups`: `axes`, `axisOf`, `unassigned`); feed `axes` to `rankWithinLayers(index, by, groups)` and `hiveLayout` (each `HiveAxis.layerId` is then the axis id).
- **Hidden layers** (the graph's `filters.hiddenLayers`, e.g. from `LayerList`): angles are divided among every layer, hidden ones included, so hiding a layer leaves a gap and the other axes and the frame don't move. Adding or removing a layer from the data re-divides the angles.
- **Without split axes** (`splitAxes={false}`), links within a layer leave the single axis as arcs: clockwise when the target sits farther out, so the side reads as direction. Arcs between near neighbours keep a minimum bulge (`HIVE_MIN_LOOP_BULGE`, 36 units) so each arrowhead sits clear of its own loop's start and of the next dot. Node labels take the side of the axis that highlighted loops cross least, and a label is dropped when loop ends cover its start on both sides.

The geometry is exported for custom renderers: `hiveLayout(layers, rank, options)` returns `HiveLayout` (each `HiveAxis` with its angle, copy offsets and label copy, plus every node's radius); `hiveLinkGeometry(layout, source, target)` returns a link's quadratic curve as `HiveLinkGeometry` (feed it to `quadCurve`); `hivePoint`, `hiveAxisAngles`, `clampSplitAngle` and `hiveLabelSide` are the helpers they use. `HiveLayoutOptions` takes the same `innerRadius`, `axisLength`, `splitAxes`, `splitAngle` and `startAngle` as the component, plus `hiddenLayers`: those layers keep their angle slot (listed in `HiveLayout.slots`, for fitting a frame) but get no drawn axis, node radius or link geometry.

```tsx
import { HivePlot, useLayeredGraph, LayeredGraphContext } from '@tinkermonkey/heimdall-ui'

// Standalone: the plot builds its own layered-graph state.
const layering = useMemo(() => ({ layerBy: 'tier', linkCategoryBy: 'category' }), [])
<HivePlot nodes={nodes} edges={edges} layering={layering} />

// Shared with other layered views and controls:
const graph = useLayeredGraph({ nodes, edges, layering, layout: false })
<LayeredGraphContext.Provider value={graph}>
  <HivePlot rank="cross-degree" axisLabels={2} interactions={{ hover: false }} />
</LayeredGraphContext.Provider>
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `graph` | `LayeredGraphState` | context | State from `useLayeredGraph`. Unset: the enclosing `LayeredGraphContext`, else its own from `nodes`/`edges`/`layering` |
| `nodes` | `GraphNodeData[]` | — | Standalone nodes; ignored with `graph` or a context |
| `edges` | `GraphEdgeData[]` | — | Standalone edges; ignored with `graph` or a context |
| `layering` | `BuildLayeredIndexOptions` | — | Standalone layering (`layerBy`, …); memoize it |
| `graphOptions` | `Omit<UseLayeredGraphOptions, 'nodes' \| 'edges' \| 'layering'>` | — | Standalone selection, follow, filters, label mode |
| `axes` | `'layer' \| (node: IndexedNode) => string \| null \| undefined` | `'layer'` | Axis per layer, or per value of any attribute of a node instance (`node.nodeId` is the source node); null, undefined or `''`: not drawn. Memoize it |
| `axisOrder` | `readonly string[] \| (a: string, b: string) => number` | layer order / code point | Axis ids to put first (the rest follow), or a comparator (numbers need one). Memoize it |
| `axisLabel` | `(axisId: string) => string` | layer label / axis id | Axis title. Memoize it |
| `rank` | `NodeOrder` | `'degree'` | Placement outward along each axis (`rankWithinLayers`) |
| `splitAxes` | `boolean` | `true` | Double each axis; off draws intra-layer links as arcs off the single axis |
| `splitAngle` | `number` | `13` | Half the angle between an axis's copies, degrees; clamped to leave room between axes |
| `axisLabels` | `number` | graph state | Nodes labeled per axis with no selection (busiest first). Unset: 1 while the graph's `nodeLabels` is on, 0 when off |
| `innerRadius` | `number` | `64` | Radius of the axes' inner end, viewBox units |
| `axisLength` | `number` | `300` | Axis length, viewBox units (the plot scales to its container) |
| `startAngle` | `number` | `-90` | First axis angle, degrees clockwise from the right (−90 = up) |
| `interactions` | `HivePlotInteractions` | both on | `{ select?: boolean; hover?: boolean }`: node selection (click, Enter, Space, Escape) and hover lift |
| `onLinkSelect` | `(link: IndexedLink) => void` | — | Link click handler. Unset: selects the link's source. Unchanged for now; only `AdjacencyMatrix.onLinkSelect` is deprecated (for `onCellSelect`) |

## FollowControl

Segmented control for how far the selection's reach follows cross-layer links: Direct / +1 layer / +2 layers. Writes `follow` on the shared `useLayeredGraph` state. Like every layered chrome control, it reads the `graph` prop, else the enclosing `LayeredGraphContext`, and throws a clear error with neither (`useLayeredGraphProp(graph, name)` is the same lookup for your own chrome). `followOptionLabel(n)` gives the default segment text.

```tsx
import { FollowControl, LayeredGraphContext, useLayeredGraph } from '@tinkermonkey/heimdall-ui'

const graph = useLayeredGraph({ nodes, edges, layering })
<LayeredGraphContext.Provider value={graph}>
  <FollowControl options={[0, 1, 2, 3]} />
</LayeredGraphContext.Provider>
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `graph` | `LayeredGraphState` | context | State from `useLayeredGraph`; unset uses the enclosing `LayeredGraphContext` |
| `options` | `readonly number[]` | `[0, 1, 2]` | Follow depths offered (hops past the direct links) |
| `formatOption` | `(follow: number) => ReactNode` | `followOptionLabel` | Segment text per depth: `Direct`, `+1 layer`, `+2 layers` |
| `label` | `ReactNode` | `'Follow'` | Mono eyebrow before the control; `null` hides it |
| `disabled` | `boolean` | `false` | Disables every segment |
| `surface` | `ChromeSurface` | `'canvas'` | `'shell'` reads the `--shell-*` tokens: dark in both canvas themes, for a shell bar |

## PredicateLabelControl

Segmented control for which links show predicate labels: Off / Highlighted (reached links and the active layer pair) / All. Writes `predicateLabels`.

```tsx
<PredicateLabelControl optionLabels={{ highlighted: 'Reached' }} />
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `graph` | `LayeredGraphState` | context | State from `useLayeredGraph`; unset uses the enclosing `LayeredGraphContext` |
| `options` | `readonly PredicateLabelMode[]` | `['off', 'highlighted', 'all']` | Modes offered, in order |
| `optionLabels` | `Partial<Record<PredicateLabelMode, ReactNode>>` | — | Segment text per mode; default `Off`, `Highlighted`, `All` |
| `label` | `ReactNode` | `'Predicates'` | Mono eyebrow before the control; `null` hides it |
| `disabled` | `boolean` | `false` | Disables every segment |
| `surface` | `ChromeSurface` | `'canvas'` | `'shell'` reads the `--shell-*` tokens: dark in both canvas themes, for a shell bar |

## PlaneLayoutControl

Segmented control for Independent (each layer laid out on its own) or Coupled (cross-layer neighbours aligned). Writes `planeLayout`; views that position nodes per layer read it.

```tsx
<PlaneLayoutControl />
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `graph` | `LayeredGraphState` | context | State from `useLayeredGraph`; unset uses the enclosing `LayeredGraphContext` |
| `optionLabels` | `Partial<Record<PlaneLayoutMode, ReactNode>>` | — | Segment text per mode; default `Independent`, `Coupled` |
| `label` | `ReactNode` | `'Plane layout'` | Mono eyebrow before the control; `null` hides it |
| `disabled` | `boolean` | `false` | Disables both segments |
| `surface` | `ChromeSurface` | `'canvas'` | `'shell'` reads the `--shell-*` tokens: dark in both canvas themes, for a shell bar |

## LinkCategoryFilter

The link bar: one toggle button per link category, each with its dash sample (from `linkCategoryStyle`) and link count, then optional intra-layer and node-label toggles. Category and intra toggles write `filters`; the node-label toggle writes the graph's `nodeLabels` (or calls `onNodeLabelsChange` with a controlled `nodeLabels`). `children` render after a divider at the end of the bar. Each divider is glued to what follows it and hidden when that starts a wrapped line, so no line of the bar starts or ends with a divider (the bar measures itself after render and on resize). `categoryDisplayLabel(c)` gives the default label (sentence case).

```tsx
<LinkCategoryFilter categoryLabels={{ structural: 'Structure' }} showLabelToggle>
  <PredicateLabelControl />
</LinkCategoryFilter>

// On a shell strip: pass the same surface to the children
<LinkCategoryFilter surface="shell" showLabelToggle>
  <PredicateLabelControl surface="shell" />
</LinkCategoryFilter>
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `graph` | `LayeredGraphState` | context | State from `useLayeredGraph`; unset uses the enclosing `LayeredGraphContext` |
| `categories` | `readonly string[]` | all in the index | Categories offered, in order |
| `categoryLabels` | `Readonly<Record<string, ReactNode>>` | — | Display text per category; unset uses `categoryDisplayLabel` |
| `showCounts` | `boolean` | `true` | Link count per category (bundled links by primary category) |
| `label` | `ReactNode` | `'Links'` | Mono eyebrow before the toggles; `null` hides it |
| `showIntraToggle` | `boolean` | `true` | Toggle for `filters.showIntra` |
| `intraLabel` | `ReactNode` | `'Intra-layer links'` | Intra toggle text |
| `showLabelToggle` | `boolean` | set when `onNodeLabelsChange` is | Toggle for node labels |
| `nodeLabels` | `boolean` | graph state | Node labels on or off (controlled). Unset: the graph's `nodeLabels`, which the toggle writes |
| `onNodeLabelsChange` | `(on: boolean) => void` | — | Called by the node-label toggle |
| `labelToggleLabel` | `ReactNode` | `'Labels'` | Node-label toggle text |
| `surface` | `ChromeSurface` | `'canvas'` | `'shell'` reads the `--shell-*` tokens (eyebrow, toggles, divider): dark in both canvas themes. Unpressed toggles use shell-fg-2 for contrast; pressed ones sit on shell-surface |
| `children` | `ReactNode` | — | Rendered after a divider at the end of the bar; empty children (`false`, `null`) render no divider |

## LayerList

One row per layer: colour swatch, name, and `nodes · links within` counts. The row is a button that focuses the layer (again to clear); the eye button hides or shows it.

```tsx
<LayerList hideable={false} />
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `graph` | `LayeredGraphState` | context | State from `useLayeredGraph`; unset uses the enclosing `LayeredGraphContext` |
| `label` | `ReactNode` | `'Layers'` | Eyebrow; `null` hides it |
| `focusable` | `boolean` | `true` | Rows are buttons that focus the layer; false renders plain rows |
| `hideable` | `boolean` | `true` | Eye button per row that hides or shows the layer |
| `showCounts` | `boolean` | `true` | Node and intra-layer link counts per row |

## LayerPairList

One row per layer pair with cross-layer links: both swatches, the names and the link count. A row toggles layer-pair focus (only that pair's cross-layer links show) and by default clears the selection.

```tsx
<LayerPairList sort="count" limit={8} />
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `graph` | `LayeredGraphState` | context | State from `useLayeredGraph`; unset uses the enclosing `LayeredGraphContext` |
| `label` | `ReactNode` | `'Cross-layer links'` | Eyebrow; `null` hides it |
| `showEmptyPairs` | `boolean` | `false` | List pairs with no cross-layer links |
| `sort` | `'rank' \| 'count'` | `'rank'` | Row order: layer rank, or link count (most first) |
| `limit` | `number` | — | At most this many rows |
| `clearSelection` | `boolean` | `true` | Picking a pair clears the selection |
| `emptyText` | `ReactNode` | `'No cross-layer links.'` | Shown when no pair qualifies |

## BridgeNodeList

The nodes with the most cross-layer links (ties by total degree), skipping hidden layers. A row selects the node.

```tsx
<BridgeNodeList limit={10} />
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `graph` | `LayeredGraphState` | context | State from `useLayeredGraph`; unset uses the enclosing `LayeredGraphContext` |
| `label` | `ReactNode` | `'Bridge nodes · most cross-layer links'` | Eyebrow; `null` hides it |
| `limit` | `number` | `6` | Number of nodes listed |
| `emptyText` | `ReactNode` | `'No cross-layer links.'` | Shown when no node has a cross-layer link |

## ReachInspector

Inspector for the layered views' selection:

- **Head:** layer eyebrow in the layer colour, clear button, name, identifier and description.
- **Stats:** `StatTile`s for cross-layer and within-layer link counts.
- **Across layers / Within layer:** the direct relationships, each with a direction icon, predicate and (across) the other node's layer dot, then a mono reach line (`reach 13 nodes across 3 layers · follow +1 layer`).
- **Followed across layers:** nodes at hop 2+, with the node and predicate they were reached through and a `+n` hop badge.

Rows are buttons that select their node. Only links the filters leave traversable are listed. `reachRelationships(graph)` returns the same data as `RelationshipLink`s (with `hop`, `via`, `layer`), usable with `GraphInspector`; `reachSummaryText(rels, follow)` gives the reach line.

```tsx
<ReachInspector
  empty={<><LayerList /><LayerPairList /><BridgeNodeList /></>}
/>

// Or feed GraphInspector from the same state:
const rels = reachRelationships(graph)
<GraphInspector node={…} relationships={rels ? [...rels.cross, ...rels.intra, ...rels.followed] : []} />
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `graph` | `LayeredGraphState` | context | State from `useLayeredGraph`; unset uses the enclosing `LayeredGraphContext` |
| `emptyText` | `ReactNode` | `'No node selected.'` | Shown with no selection |
| `empty` | `ReactNode` | — | Replaces the empty text with no selection |
| `showClear` | `boolean` | `true` | Clear-selection button beside the layer eyebrow |
| `showDescription` | `boolean` | `true` | The node's description |
| `showStats` | `boolean` | `true` | Across-layers and within-layer stat tiles |
| `showFollowed` | `boolean` | `true` | The "Followed across layers" list |
| `showReachSummary` | `boolean` | `true` | The mono reach line |
| `onNodeSelect` | `(nodeId: string) => void` | — | Row handler; unset selects the row's node |

## LayeredGraphExplorer

The ready-made layered graph explorer: every layered view and its chrome in one component.

- **Header** (shell surface): optional `eyebrow` and `title`, a `ViewSwitcher` (3D stack / Lanes / Matrix / Hive, hidden with one view) and `FollowControl`.
- **Scene:** the chosen view: `LayerStack`, `GraphCanvas layout="layer-lanes"`, `AdjacencyMatrix` or `HivePlot`. Above the stack: `CameraControls` and `PlaneLayoutControl`.
- **Link bar:** `LinkCategoryFilter` with `PredicateLabelControl` inside, and a node-label toggle for the stack (`all` / `reached` labels) and the hive (busiest-node labels on / off).
- **Inspector panel:** `ReachInspector`, showing `LayerList`, `LayerPairList` and `BridgeNodeList` with no selection. In the matrix view, a cell click shows its link above it in a "Link details" panel (`GraphEdgeInspector`) and outlines the cell, instead of selecting the source. Endpoints select their node; a symmetric cell holding both directions has a Reverse button; the close button or Escape closes it and returns focus to the matrix cell that was clicked (the matrix's Tab-stop cell, which is always rendered, unlike a virtualized row header). The panel drops itself when a filter hides its links or the view changes. If `matrixProps` passes `onCellSelect` (or the deprecated `onLinkSelect`), that handler runs instead of the panel, as in 0.10.0; with `controls.inspector` off, a cell click selects the source. It sits on the right and stacks below the scene when the explorer is narrower than `stackBelow`.
- **Status line** (mono, shell surface): `statusLabel`, node / link / cross-layer / layer counts, the view and follow depth, and for the stack the camera (`stack · yaw -36° pitch 29° zoom 1.00 · gap 170`).

Selection, follow, filters, label mode, layer focus and plane layout are one `useLayeredGraph` state shared by every view, so they survive view switches; the explorer provides it as `LayeredGraphContext` to everything inside. The 3D camera (preset, yaw / pitch / zoom, gap, turntable) is remembered when you switch away and restored when you switch back. Turn chrome on or off with `controls`; every field defaults to true (`LayeredGraphExplorerControls`: `viewSwitcher`, `follow`, `predicateLabels`, `linkFilter`, `nodeLabels`, `camera`, `planeLayout`, `inspector`, `layers`, `layerPairs`, `bridgeNodes`, `status`).

**Snapshot (URL and history round-trip).** `LayeredGraphExplorerSnapshot` is the whole explorer as plain JSON: the graph state (`LayeredGraphSnapshot`: selection, follow, filters, predicate labels, layer focus, plane layout) plus `view`, `nodeLabels` and `stack` (`LayeredGraphExplorerCamera`: `preset`, `camera`, `layerGap`, kept while another view shows). `defaultSnapshot` seeds a fresh explorer from one (read once, on mount), `onSnapshotChange` reports every change (not on mount; a camera move once it settles), and the `explorerRef` handle (`LayeredGraphExplorerHandle`) has `getSnapshot()` (live camera and gap when the stack shows), `restore(snapshot)` (any subset, `LayeredGraphExplorerSnapshotInput`; a camera jumps) and `stack()`. With a `graph` prop or context, seed that state with `layeredGraphSnapshotDefaults(snapshot)`, which turns snapshot fields into `useLayeredGraph` `default…` options.

Snapshots from a URL are untrusted, so every entry point sanitizes them: `sanitizeLayeredGraphExplorerSnapshot(input, views?)` (used by `defaultSnapshot` and `restore`) and `sanitizeLayeredGraphSnapshot(input)` (the graph fields, `LayeredGraphSnapshotFields`; used by `layeredGraphSnapshotDefaults`) drop malformed fields. That covers an unknown preset or view, non-finite camera numbers, a non-positive gap or one above `MAX_LAYER_GAP` (5000), wrong types and ids that are not strings. They also merge a partial `filters` onto `DEFAULT_LINK_FILTERS`. A restored camera is clamped like the stack's own and stops the turntable. A preset is active exactly when the stored camera and gap are the preset's own: picking one stores its camera and gap at once, so a preset click reports once, already settled. A `stackProps` camera or gap override, or a snapshot with a preset plus other camera fields, keeps that camera and gap with no preset. `useLayeredGraph`'s own `restore` does not check its input: pass a URL snapshot through `sanitizeLayeredGraphSnapshot` first. `restore` remounts the stack only when the camera actually changes; re-read `stack()` after one that does.

```tsx
const saved = useMemo(() => {
  const raw = new URLSearchParams(location.search).get('state')
  return raw ? (JSON.parse(raw) as LayeredGraphExplorerSnapshotInput) : undefined
}, [])
const explorer = useRef<LayeredGraphExplorerHandle>(null)
<LayeredGraphExplorer
  nodes={nodes}
  edges={edges}
  layering={layering}
  defaultSnapshot={saved}
  onSnapshotChange={(s) => history.replaceState(null, '', `?state=${encodeURIComponent(JSON.stringify(s))}`)}
  explorerRef={explorer}
/>
// later, e.g. on popstate: explorer.current?.restore(previous)
```

`ViewSwitcher` and `CameraControls` are exported for custom layouts. `ViewSwitcher` is a plain controlled segmented control over `LayeredGraphView` values (`LAYERED_GRAPH_VIEWS` lists them; `LAYERED_GRAPH_VIEW_LABELS` gives the default text). `CameraControls` drives a `LayerStack` through its ref: preset segmented control, zoom out / in, optional fit and a turntable toggle.

```tsx
import { LayeredGraphExplorer, CameraControls, ViewSwitcher, LayerStack, type LayerStackHandle, type CameraPresetName } from '@tinkermonkey/heimdall-ui'

const layering = useMemo(() => ({ layerBy: 'tier', linkCategoryBy: 'category' }), [])
<LayeredGraphExplorer
  nodes={nodes}
  edges={edges}
  layering={layering}
  views={['stack', 'matrix']}
  controls={{ bridgeNodes: false, status: false }}
  title="Architecture model"
  statusLabel="arch model v3"
  height={720}
/>

// The pieces in your own layout:
const stack = useRef<LayerStackHandle>(null)
const [preset, setPreset] = useState<CameraPresetName | null>('stack')
const [turntable, setTurntable] = useState(false)
<CameraControls stack={stack} preset={preset} turntable={turntable} onTurntableChange={setTurntable} showFit />
<LayerStack ref={stack} cameraPreset={preset} onCameraPresetChange={setPreset} turntable={turntable} onTurntableChange={setTurntable} />
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `graph` | `LayeredGraphState` | context | External state from `useLayeredGraph`. Unset: the enclosing `LayeredGraphContext`, else its own from `nodes`/`edges`/`layering` |
| `nodes` | `GraphNodeData[]` | — | Standalone nodes; also passed to the lanes canvas |
| `edges` | `GraphEdgeData[]` | — | Standalone edges; also passed to the lanes canvas |
| `layering` | `BuildLayeredIndexOptions` | — | Standalone layering (`layerBy`, …); memoize it |
| `graphOptions` | `Omit<UseLayeredGraphOptions, 'nodes' \| 'edges' \| 'layering'>` | — | Standalone selection, follow, filters, label mode, focus, plane layout (controlled or default) |
| `views` | `readonly LayeredGraphView[]` | all four | Views offered, in switcher order (`'stack' \| 'lanes' \| 'matrix' \| 'hive'`); one view hides the switcher |
| `viewLabels` | `Partial<Record<LayeredGraphView, ReactNode>>` | — | Switcher text per view; default `3D stack`, `Lanes`, `Matrix`, `Hive` |
| `view` | `LayeredGraphView` | — | Controlled view |
| `defaultView` | `LayeredGraphView` | first of `views` | Initial view when uncontrolled |
| `onViewChange` | `(view: LayeredGraphView) => void` | — | Called by the switcher |
| `explorerRef` | `Ref<LayeredGraphExplorerHandle>` | — | Handle: `getSnapshot()`, `restore(snapshot)`, `stack()` (`ref` is the root element) |
| `defaultSnapshot` | `LayeredGraphExplorerSnapshotInput` | — | Initial state from a snapshot (view, node labels, 3D camera, and the explorer's own graph state); read once |
| `onSnapshotChange` | `(snapshot: LayeredGraphExplorerSnapshot) => void` | — | Called when the snapshot changes, not on mount; camera moves report once settled |
| `controls` | `LayeredGraphExplorerControls` | all on | Which chrome renders: `{ viewSwitcher, follow, predicateLabels, linkFilter, nodeLabels, camera, planeLayout, inspector, layers, layerPairs, bridgeNodes, status }` |
| `followOptions` | `readonly number[]` | `[0, 1, 2]` | Follow depths offered by `FollowControl` |
| `title` | `ReactNode` | — | Heading in the header |
| `eyebrow` | `ReactNode` | — | Mono eyebrow above the title |
| `statusLabel` | `ReactNode` | — | Dataset label at the start of the status line |
| `chromeSurface` | `ChromeSurface` | `'shell'` | Header and status line on the shell surface or the canvas. On `'shell'` they read the `--shell-*` tokens and the header's `ViewSwitcher` and `FollowControl` get `surface="shell"` |
| `nodeLabels` | `boolean` | graph state | Controlled node labels (stack and hive), over the graph's `nodeLabels` |
| `defaultNodeLabels` | `boolean` | `true` | Initial node labels: seeds the explorer's own graph state (kept apart from a `graph` prop or context) |
| `onNodeLabelsChange` | `(on: boolean) => void` | — | Called by the node-label toggle |
| `stackProps` | `Partial<LayerStackProps>` | — | Passed to `LayerStack`; camera callbacks are chained, preset and turntable are explorer-owned |
| `lanesProps` | `Partial<GraphCanvasProps>` | — | Passed to the lanes `GraphCanvas` (`laneOptions`, `style`, …) |
| `matrixProps` | `Partial<AdjacencyMatrixProps>` | — | Passed to `AdjacencyMatrix` |
| `hiveProps` | `Partial<HivePlotProps>` | — | Passed to `HivePlot` |
| `height` | `number \| string` | — | Fixed height: the scene fills the room left and the panels scroll. Unset: grows with its content |
| `stackBelow` | `number` | `960` | Below this width (px) the inspector panel stacks under the scene |
| `asideWidth` | `number` | `340` | Inspector panel width in px |

## ViewSwitcher

Segmented control for the explorer's view (3D stack, Lanes, Matrix, Hive). Use it to build your own explorer layout; `LAYERED_GRAPH_VIEWS` and `LAYERED_GRAPH_VIEW_LABELS` list the views and their default labels.

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `views` | `readonly LayeredGraphView[]` | `LAYERED_GRAPH_VIEWS` | Views offered, in order |
| `value` | `LayeredGraphView` | — | The active view |
| `onChange` | `(view: LayeredGraphView) => void` | — | Called with the picked view |
| `viewLabels` | `Partial<Record<LayeredGraphView, ReactNode>>` | — | Segment text per view; default from `LAYERED_GRAPH_VIEW_LABELS` |
| `label` | `ReactNode` | `'View'` | Mono eyebrow; `null` hides it |
| `disabled` | `boolean` | `false` | Disables every segment |
| `surface` | `ChromeSurface` | `'canvas'` | `'shell'` reads the `--shell-*` tokens: dark in both canvas themes, for a shell bar |

## CameraControls

Camera chrome for `LayerStack`: preset segmented control, zoom in and out, fit and the turntable toggle, driven by a LayerStack ref or controlled props.

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `stack` | `RefObject<LayerStackHandle \| null>` | — | The `LayerStack` to drive (presets, zoom, fit, turntable) |
| `preset` | `CameraPresetName \| null` | `null` | Preset shown as active; wire to the stack's `cameraPreset` / `onCameraPresetChange` |
| `onPresetChange` | `(preset: CameraPresetName) => void` | — | Called with a picked preset (the handle applies it as well) |
| `presets` | `readonly CameraPresetName[]` | all four | Presets offered; empty hides the control |
| `presetLabels` | `Partial<Record<CameraPresetName, ReactNode>>` | — | Segment text per preset; default `Stack`, `Exploded`, `Top`, `Profile` |
| `turntable` | `boolean` | `false` | Turntable state shown on the toggle |
| `onTurntableChange` | `(on: boolean) => void` | — | Called by the toggle; unset calls the handle's `setTurntable` |
| `showZoom` | `boolean` | `true` | Zoom out / in buttons |
| `showFit` | `boolean` | `false` | Fit button |
| `showTurntable` | `boolean` | `true` | Turntable toggle |
| `zoomStep` | `number` | `1.2` | Zoom factor per press |
| `label` | `ReactNode` | `null` | Mono eyebrow before the presets |
| `disabled` | `boolean` | `false` | Disables every control |
