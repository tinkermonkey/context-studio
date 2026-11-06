---
name: heimdall-layout
description: Heimdall component guide for Layout: Panel, SplitPane, and the useMediaQuery hook
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## Panel

Bordered content card with optional header (title, subtitle, trailing action) and footer.

```tsx
import { Panel } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | — | Header title (not the native `title` attribute) |
| `subtitle` | `string` | — | Secondary line below the title |
| `headerAction` | `ReactNode` | — | Trailing slot in the header row |
| `footer` | `ReactNode` | — | Footer slot with top border |
| `bordered` | `boolean` | `true` | Outer border plus header/footer dividers |
| `noPadding` | `boolean` | `false` | Remove the 16px body padding |
| `children` | `ReactNode` | — | Panel body |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<Panel title="Schema classes">
  <p>Panel body content.</p>
</Panel>
```

```tsx
<Panel
  title="Import data"
  subtitle="428 individuals · last synced 2m ago"
  headerAction={
    <Button variant="ghost" size="sm" aria-label="Reload">
      <Icon name="reload" size={14} />
    </Button>
  }
  footer={
    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
      <Button variant="ghost" size="sm">Cancel</Button>
      <Button variant="primary" size="sm">Import</Button>
    </div>
  }
>
  <Field label="Source">
    <TextInput placeholder="s3://bucket/path" mono />
  </Field>
</Panel>
```

```tsx
// Edge-to-edge list with its own dividers
<Panel title="Recent runs" noPadding>
  {runs.map(run => (
    <div key={run.id} style={{ padding: '10px 16px', borderTop: '1px solid rgb(var(--canvas-border))' }}>
      <code>{run.id}</code>
    </div>
  ))}
</Panel>

// Inside a container that already draws a border
<Panel bordered={false} title="Embedded panel">
  <p>Content.</p>
</Panel>
```

### Gotchas

- The header renders only when `title`, `subtitle` or `headerAction` is set.
- The body renders only when `children` is not `null`/`undefined`. `false` or `0` still render an empty padded body; pass `null` to omit it.
- The footer renders only when `footer` is truthy. It is not a flex row; lay out buttons inside it yourself (as above).
- `bordered={false}` also removes the header bottom border and footer top border.
- The body background (`canvas-bg-2`) differs from the header/footer (`canvas-card`).
- The root has `overflow: hidden`, which clips any Tooltip or Popover inside the panel near its edges.
- `title` replaces the native HTML `title` attribute, so it never shows a browser tooltip.

---

## SplitPane

Resizable two-pane split with a draggable, keyboard-focusable divider. Controlled or uncontrolled.

```tsx
import { SplitPane } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `first` | `ReactNode` | required | Left (horizontal) or top (vertical) pane |
| `second` | `ReactNode` | required | Right or bottom pane |
| `direction` | `'horizontal' \| 'vertical'` | `'horizontal'` | Side-by-side or stacked |
| `initialSplitPercent` | `number` | `50` | First-pane size in percent at mount (uncontrolled) |
| `splitPercent` | `number` | — | Controlled first-pane size in percent |
| `onSplitChange` | `(percent: number) => void` | — | Called on every drag move or arrow key |
| `minSize` | `number` | `200` | Minimum first-pane size in px |
| `maxSize` | `number` | `800` | Maximum first-pane size in px |
| `dividerLabel` | `string` | `'Horizontal divider'` / `'Vertical divider'` | Divider `aria-label` |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<div style={{ height: 400 }}>
  <SplitPane
    initialSplitPercent={40}
    first={<div style={{ padding: 16 }}>Left pane</div>}
    second={<div style={{ padding: 16 }}>Right pane</div>}
  />
</div>
```

```tsx
const [split, setSplit] = useState(65)

<div style={{ height: '100%' }}>
  <SplitPane
    direction="horizontal"
    splitPercent={split}
    onSplitChange={setSplit}
    minSize={320}
    maxSize={1400}
    dividerLabel="Resize graph and inspector"
    first={<GraphCanvas nodes={nodes} edges={edges} />}
    second={
      <SplitPane
        direction="vertical"
        initialSplitPercent={60}
        minSize={120}
        first={<div style={{ padding: 16 }}>Inspector</div>}
        second={<div style={{ padding: 16 }}>Log output</div>}
      />
    }
  />
</div>
```

### Gotchas

- The root is `width: 100%; height: 100%`. The parent needs an explicit height (fixed or resolved through a full-height chain), or the panes collapse.
- Two panes only. For three panes, nest a SplitPane in `first` or `second` (as above).
- `minSize`/`maxSize` are pixels for the first pane, converted against the current container size. The default `maxSize` of 800 stops the first pane at 800px on wide screens; raise it for full-range dragging.
- Clamping applies only to drag and keyboard changes. `initialSplitPercent` and a controlled `splitPercent` are used as given.
- `initialSplitPercent` is read once at mount; later changes are ignored. Use `splitPercent` to set the position programmatically.
- In controlled mode the divider does not move unless `onSplitChange` updates `splitPercent`. The callback fires on every mouse move, so debounce it before persisting.
- Keyboard: focus the divider (it is in the tab order), then Arrow Left/Up shrink and Arrow Right/Down grow the first pane by 2%, 10% with Shift. Both arrow pairs work in either direction.
- Drag uses mouse events only; touch input does not resize.
- Each pane is `overflow: auto` and scrolls independently; content wider than its pane scrolls instead of overflowing. The divider is 1px with a 9px hit area and turns amber on hover and focus.

## Responsive hooks

### useMediaQuery

```ts
function useMediaQuery(query: string): boolean
```

Returns whether `window.matchMedia(query)` currently matches, and re-renders when the match changes. Re-subscribes when `query` changes.

```tsx
import { useMediaQuery } from '@tinkermonkey/heimdall-ui'

function ClassBrowser() {
  const isNarrow = useMediaQuery('(max-width: 1024px)')

  return (
    // key remounts the SplitPane so the new initialSplitPercent applies
    <SplitPane
      key={isNarrow ? 'stacked' : 'side_by_side'}
      direction={isNarrow ? 'vertical' : 'horizontal'}
      initialSplitPercent={isNarrow ? 50 : 35}
      minSize={isNarrow ? 120 : 240}
      first={<div style={{ padding: 16 }}>Class list</div>}
      second={<div style={{ padding: 16 }}>Class detail</div>}
    />
  )
}
```

- Pass a full media query string including parentheses: `'(max-width: 768px)'`, `'(prefers-color-scheme: dark)'`.
- Without `window` (server rendering) it returns `false`, then corrects after mount. On the client the first render already reflects the real match.
- `ShellLayout`, `Topbar` and `Statusbar` use it internally for their `mobileBreakpoint` behavior.
