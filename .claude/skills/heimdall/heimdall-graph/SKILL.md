---
name: heimdall-graph
description: Heimdall component guide for Graph: GraphCanvas, GraphNode, GraphEdge, GraphInspector, TopologyNode, HierarchyRow, HierarchyTree
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## GraphCanvas

Pan/zoom canvas for rendering interactive node-edge graphs. Provides context consumed by `GraphEdge`.

```tsx
import { GraphCanvas } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `nodes` | `GraphNodeData[]` | required | Nodes to render |
| `edges` | `GraphEdge[]` | `[]` | Edges to render |
| `selectedNodeId` | `string` | — | Controlled selected node ID |
| `onNodeSelect` | `(nodeId: string) => void` | — | Called when a node is clicked |
| `renderNode` | `(node: GraphNodeData, selected: boolean) => ReactNode` | — | Custom node renderer |
| `layout` | `'manual' \| 'force'` | `'manual'` | Layout algorithm |
| `...HTMLAttributes` | | | Standard div attributes |

```ts
interface GraphNodeData {
  id: string
  label: string
  kind?: string
  domainColor?: string
  x?: number      // required for layout='manual' (pins node in layout='force')
  y?: number
}

interface GraphEdge {
  id: string
  sourceId: string
  targetId: string
  label?: string
  variant?: 'default' | 'hot' | 'irrelevant'
}
```

### Usage

```tsx
// Manual layout with custom node renderer
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
  renderNode={(node, selected) => (
    <GraphNode
      id={node.id}
      label={node.label}
      kind={node.kind}
      domainColor={node.domainColor}
      selected={selected}
      onSelect={setSelectedId}
    />
  )}
  style={{ width: '100%', height: '500px' }}
/>
```

```tsx
// Force layout (omit x/y for auto-positioning)
<GraphCanvas
  nodes={nodes}
  edges={edges}
  layout="force"
  onNodeSelect={setSelectedId}
  renderNode={(node, selected) => (
    <GraphNode id={node.id} label={node.label} selected={selected} onSelect={setSelectedId} />
  )}
  style={{ width: '100%', height: '500px' }}
/>
```

### Gotchas

- **Canvas requires explicit dimensions** — set `style={{ width: '100%', height: '500px' }}` or similar on the container
- In `layout='manual'`, nodes without `x`/`y` are placed at the canvas origin
- In `layout='force'`, nodes with explicit `x`/`y` are pinned; nodes without are auto-positioned on a circle initially
- `renderNode` should be memoized with `useCallback` to avoid unnecessary re-measurements
- Pan via mouse drag on empty areas; zoom via mouse wheel (0.4×–2.5×)

---

## GraphNode

Node card for use inside `GraphCanvas` via the `renderNode` prop.

```tsx
import { GraphNode } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `string` | required | Node identifier |
| `label` | `string` | required | Display text |
| `kind` | `string` | — | Type badge (e.g. `'C'` for class) |
| `domainColor` | `string` | `'default'` | Domain color key |
| `selected` | `boolean` | `false` | Selected state |
| `onSelect` | `(id: string) => void` | — | Makes node keyboard-focusable when provided |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
// Inside GraphCanvas renderNode callback
renderNode={(node, selected) => (
  <GraphNode
    id={node.id}
    label={node.label}
    kind={node.kind}
    domainColor={node.domainColor}
    selected={selected}
    onSelect={setSelectedId}
  />
)}
```

### Gotchas

- When `onSelect` is provided: sets `role="button"`, `tabIndex={0}`, `aria-pressed={selected}`; Enter/Space trigger selection
- Click handler stops propagation so canvas pan is not triggered
- When used without `onSelect`, the node is read-only with no keyboard interaction

---

## GraphEdge

SVG bezier edge between two nodes. Must be used inside `GraphCanvas` (requires its context).

```tsx
import { GraphEdge } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `string` | required | Unique edge identifier |
| `sourceId` | `string` | required | Source node ID |
| `targetId` | `string` | required | Target node ID |
| `label` | `string` | — | Text label at path midpoint |
| `variant` | `'default' \| 'hot' \| 'irrelevant'` | `'default'` | Visual style |
| `...SVGAttributes` | | | Standard SVG `<g>` attributes |

Variants: `default`=neutral gray, `hot`=cyan (active/highlighted), `irrelevant`=rose (deprecated).

### Usage

```tsx
// Passed via GraphCanvas edges prop (preferred)
<GraphCanvas
  edges={[
    { id: 'e1', sourceId: 'node_a', targetId: 'node_b', label: 'contains' },
    { id: 'e2', sourceId: 'node_c', targetId: 'node_d', variant: 'hot', label: 'encodes' },
    { id: 'e3', sourceId: 'node_e', targetId: 'node_f', variant: 'irrelevant', label: 'deprecated' },
  ]}
  ...
/>
```

### Gotchas

- **Must be used inside `GraphCanvas`** — `GraphEdge` calls `useGraphCanvas()` internally and will throw if used outside a canvas
- Returns `null` silently if either the source or target node rect is not yet available (e.g. during initial layout)
- Bezier curves connect the edges of node rectangles, not center points

---

## GraphInspector

Structured detail panel for a selected graph node with relationship links.

```tsx
import { GraphInspector } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `node` | `GraphNodeMetadata \| null` | — | Node to inspect; `null` shows empty state |
| `relationships` | `RelationshipLink[]` | `[]` | Incoming and outgoing links |
| `onNodeSelect` | `(nodeId: string) => void` | — | Called when a relationship target is clicked |
| `emptyStateText` | `string` | `'Select a node to inspect.'` | Empty state message |
| `...HTMLAttributes` | | | Standard div attributes |

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
  target: string
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
  emptyStateText="Click a node to inspect it."
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

- Relationships are split into incoming (`direction='in'`) and outgoing (`direction='out'`) sections by the component
- Relationship target labels are clickable buttons that call `onNodeSelect`

---

## TopologyNode

Infrastructure/service node card with status indicator and metric progress bars. Supports absolute positioning for canvas layouts.

```tsx
import { TopologyNode } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | required | Service name |
| `nodeRole` | `string` | `''` | Role label below title |
| `status` | `'ok' \| 'warning' \| 'error' \| 'idle'` | `'idle'` | Status dot color |
| `metrics` | `TopologyNodeMetric[]` | `[]` | Metric rows with progress bars |
| `selected` | `boolean` | `false` | Amber border ring |
| `x` | `number` | — | Absolute left position (px) |
| `y` | `number` | — | Absolute top position (px) |
| `onSelect` | `() => void` | — | Makes node keyboard-focusable when provided |
| `...HTMLAttributes` | | | Standard div attributes |

```ts
interface TopologyNodeMetric {
  label: string
  value: number | string
  unit?: string
  percent: number           // progress bar fill 0–100 (clamped)
  sparklineData: number[]   // reserved, not currently rendered
  color?: StatusColor
}
```

Status → dot color: `ok`=emerald, `warning`=amber, `error`=rose, `idle`=neutral.

### Usage

```tsx
// In a positioned canvas
<div style={{ position: 'relative', height: 400 }}>
  <TopologyNode
    title="API Server"
    nodeRole="backend"
    status="ok"
    metrics={[
      { label: 'CPU', value: '45%', percent: 45, sparklineData: [], color: 'emerald' },
      { label: 'Memory', value: '62%', percent: 62, sparklineData: [], color: 'amber' },
    ]}
    x={100}
    y={80}
    selected={selected === 'api'}
    onSelect={() => setSelected('api')}
  />
</div>
```

### Gotchas

- When `x` and `y` are provided, the component uses `position: absolute` — the parent must be `position: relative`
- `percent` is clamped to `[0, 100]`
- When `onSelect` is not provided, the node is non-interactive (no `role`, no `tabIndex`)

---

## HierarchyRow

A single row in a taxonomy/hierarchy tree with depth indentation, domain color swatch, and kind badge.

```tsx
import { HierarchyRow } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `domain` | `'life' \| 'climate' \| 'software' \| 'default' \| string` | required | Controls swatch color |
| `kind` | `'taxonomy' \| 'scheme' \| 'class'` | required | Type badge |
| `label` | `string` | required | Display text |
| `depth` | `number` | `0` | Indentation level |
| `meta` | `string` | — | Metadata (e.g. item count) |
| `description` | `string` | — | Secondary text on the right |
| `selected` | `boolean` | `false` | Selected state |
| `onSelect` | `() => void` | — | Makes row keyboard-interactive when provided |
| `showKind` | `boolean` | `true` | Show the kind badge |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
// Inside HierarchyTree
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

- A connector line renders at `depth > 0` only — depth-0 rows have no left connector
- Domain color falls back to `--dom-default` for unknown domain strings
- When `onSelect` is not provided, the row is non-interactive (no `role`, no `tabIndex`)

---

## HierarchyTree

Semantic container for `HierarchyRow` items.

```tsx
import { HierarchyTree } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `children` | `ReactNode` | required | `HierarchyRow` components |
| `...HTMLAttributes` | | | Standard div attributes |

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
      key={idx}
      {...row}
      selected={selected === idx}
      onSelect={() => setSelected(selected === idx ? null : idx)}
    />
  ))}
</HierarchyTree>
```

### Gotchas

- `HierarchyTree` is a simple container with no built-in selection, expand/collapse, or virtualization logic — manage these in the parent
