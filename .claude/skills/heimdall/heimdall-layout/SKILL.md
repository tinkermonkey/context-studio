---
name: heimdall-layout
description: Heimdall component guide for Layout: Panel, SplitPane
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## Panel

Bordered content card with optional title, subtitle, header action slot, and footer.

```tsx
import { Panel } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | — | Panel header title |
| `subtitle` | `string` | — | Secondary line in header |
| `headerAction` | `ReactNode` | — | Trailing slot in header row |
| `footer` | `ReactNode` | — | Footer slot with top border |
| `bordered` | `boolean` | `true` | Show 1px outer border |
| `noPadding` | `boolean` | `false` | Remove body padding for edge-to-edge content |
| `children` | `ReactNode` | — | Panel body |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
// Minimal
<Panel title="Schema classes">
  <p>Panel body content.</p>
</Panel>
```

```tsx
// With subtitle, header action, and footer
<Panel
  title="Import data"
  subtitle="428 individuals · last synced 2m ago"
  headerAction={
    <Button variant="ghost" size="sm">
      <Icon name="reload" size={14} />
    </Button>
  }
  footer={
    <div className="flex justify-end gap-2">
      <Button variant="ghost" size="sm">Cancel</Button>
      <Button variant="primary" size="sm">Import</Button>
    </div>
  }
>
  {/* form content */}
</Panel>
```

```tsx
// No padding for lists with their own dividers
<Panel title="Recent runs" noPadding>
  {runs.map(run => (
    <div key={run.id} className="px-4 py-2 border-b border-canvas">
      {run.name}
    </div>
  ))}
</Panel>

// No border (inside another container)
<Panel bordered={false} title="Embedded panel">
  {/* content */}
</Panel>
```

### Gotchas

- Header renders only when at least one of `title`, `subtitle`, or `headerAction` is provided — no empty header div
- Body renders only when `children` is non-null — falsy values like `0` or `false` suppress the body
- `noPadding` affects only the body div; header and footer always have their own padding

---

## SplitPane

Resizable two-pane layout with mouse drag, keyboard navigation, and controlled/uncontrolled modes.

```tsx
import { SplitPane } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `first` | `ReactNode` | required | Content for the first (left/top) pane |
| `second` | `ReactNode` | required | Content for the second (right/bottom) pane |
| `direction` | `'horizontal' \| 'vertical'` | `'horizontal'` | Split orientation |
| `initialSplitPercent` | `number` | `50` | Starting split position 0–100 (uncontrolled only) |
| `splitPercent` | `number` | — | Controlled split position 0–100 |
| `onSplitChange` | `(percent: number) => void` | — | Called when divider moves |
| `minSize` | `number` | `200` | Minimum first-pane size in **pixels** |
| `maxSize` | `number` | `800` | Maximum first-pane size in **pixels** |
| `dividerLabel` | `string` | — | ARIA label for the divider |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
// Uncontrolled horizontal split
<SplitPane
  direction="horizontal"
  initialSplitPercent={40}
  first={<div>Left pane</div>}
  second={<div>Right pane</div>}
/>
```

```tsx
// Controlled with constraints
const [split, setSplit] = useState(65)

<SplitPane
  direction="horizontal"
  splitPercent={split}
  onSplitChange={setSplit}
  minSize={200}
  maxSize={900}
  dividerLabel="Resize graph / inspector"
  first={<GraphCanvas ... />}
  second={<InspectorPanel ... />}
  style={{ height: '100%' }}
/>
```

```tsx
// Vertical split
<SplitPane
  direction="vertical"
  initialSplitPercent={60}
  first={<div>Top pane</div>}
  second={<div>Bottom pane</div>}
  style={{ height: '500px' }}
/>
```

### Gotchas

- **The component requires a parent with explicit dimensions** — it does not set its own height; wrap it in a `height: 100%` or fixed-height container
- `minSize` and `maxSize` are in **pixels**, but are clamped to percentages based on the container's current size at drag time — the effective percentage range changes as the viewport resizes
- `second` pane always gets `100 - splitPercent` percent; you cannot control both panes independently
- Keyboard navigation (Arrow keys, Shift+Arrow for 10% step) only works when the divider has focus
- Mouse events are attached to `document` during drag, so dragging outside the container works correctly
