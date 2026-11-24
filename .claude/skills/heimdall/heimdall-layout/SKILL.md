---
name: heimdall-layout
description: Heimdall component guide for Layout: Panel, SplitPane, PaneRail, and the useMediaQuery hook
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

---

## PaneRail

A folded pane as a 40px vertical rail. Top to bottom: an expand button, a map of the pane's items (toned marks at their positions), an amber notch at the selection, an optional position label, the pane's name written up the rail and its key hint. It holds no folding state: render it in place of the pane while the pane is folded.

```tsx
import { PaneRail, type PaneRailMark } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `label` | `string` | required | The pane's name, written up the rail; also names the expand button |
| `onExpand` | `() => void` | required | Called by the expand button and by a click on the rail outside a handled mark |
| `marks` | `PaneRailMark[]` | `[]` | The pane's items: `{ id, position, tone?, label }` (below) |
| `selectedPosition` | `number` | — | Position (0..1) of the amber notch; omit for none |
| `positionLabel` | `string` | — | Short text under the map, e.g. `'5 / 37'`, written up the rail |
| `shortcut` | `string` | — | Key hint shown at the bottom; also the expand button's `aria-keyshortcuts`. The app handles the key |
| `side` | `'left' \| 'right'` | `'left'` | Edge the folded pane sits on: its border and the chevron face the content |
| `expandLabel` | `string` | `` `Expand ${label}` `` | Accessible name of the expand button |
| `mapLabel` | `string` | `` `${label} map` `` | Accessible name of the marks' toolbar (`role="toolbar"`, `aria-orientation="vertical"`) |
| `onMarkClick` | `(id: string) => void` | — | A mark was clicked or activated by keyboard. Without it, a mark click expands the pane |
| `onMarkHover` | `(id: string, anchor: HTMLElement) => void` | — | Mouse enter or focus on a mark, with the mark's element to anchor the app's hover card |
| `onMarkLeave` | `(id: string) => void` | — | Mouse leave or blur on a mark |
| `...divProps` | | | Remaining props spread onto the root `<div>` (`className`, `data-testid`, `aria-*`, ...) |

`PaneRailMark`: `id: string`, `position: number` (0 top, 1 bottom; clamped), `tone?: StatusColor` (`'emerald' | 'amber' | 'rose' | 'cyan' | 'violet' | 'neutral'`, the `Chip` tones; default `'neutral'`), `label: string` (the mark button's accessible name). Ids should be unique; duplicates still render (each mark gets its own React key) and both report the same id to the callbacks.

### Usage

```tsx
// A source pane that folds to a rail; highlights coloured by verdict at their offsets in the text.
const [folded, setFolded] = useState(false)
const marks: PaneRailMark[] = highlights.map(h => ({
  id: h.id,
  position: h.start / text.length,
  tone: h.verdict === 'accepted' ? 'emerald' : h.verdict === 'rejected' ? 'rose' : 'amber',
  label: h.term,
}))

// The app owns the key; the rail only shows it.
useEffect(() => {
  const onKey = (e: KeyboardEvent) => { if (e.key === '[') setFolded(f => !f) }
  window.addEventListener('keydown', onKey)
  return () => window.removeEventListener('keydown', onKey)
}, [])

<div style={{ display: 'flex', height: '100%' }}>
  {folded ? (
    <PaneRail
      label="Source"
      shortcut="["
      marks={marks}
      selectedPosition={selected ? selected.start / text.length : undefined}
      onExpand={() => setFolded(false)}
      onMarkClick={id => { setFolded(false); scrollToHighlight(id) }}
      onMarkHover={(id, anchor) => showHoverCard(id, anchor)}
      onMarkLeave={() => hideHoverCard()}
    />
  ) : (
    <SourcePane onFold={() => setFolded(true)} />
  )}
  <Inspector />
</div>
```

```tsx
// A list pane: one mark per row in list order, with the selection's place in the list.
<PaneRail
  label="Operations"
  shortcut="]"
  marks={rows.map((row, i) => ({ id: row.id, position: i / Math.max(1, rows.length - 1), tone: row.tone, label: row.title }))}
  selectedPosition={selectedIndex / Math.max(1, rows.length - 1)}
  positionLabel={`${selectedIndex + 1} / ${rows.length}`}
  onExpand={() => setListFolded(false)}
/>
```

### Gotchas

- The root is `width: 40px; height: 100%`. Put it in a flex row (or a parent with an explicit height); the map takes whatever height the button, labels and key hint leave.
- The rail does not fold or expand anything and does not listen for its `shortcut`. Show it while the pane is folded and bind the key yourself.
- A click anywhere on the rail that no mark handles calls `onExpand`, the name and key hint included. A root `onClick` runs first; call `e.preventDefault()` in it to stop the expand.
- Marks render in position order whatever order you pass them in. Marks at nearly the same position overlap (the later one is on top).
- Each mark's bar is 16x3, its button 20x7, and an invisible `::after` extends its hit area to 24x24 (the WCAG 2.5.8 minimum) without enlarging the bar. The extensions sit under every bar, so a visible mark always takes the pointer and the extensions only fill the empty space around marks.
- **Dense rails are an exception to the 24px target size.** When marks are closer than 24px (about 10 or more marks on a short rail, and always with hundreds), their extensions overlap and a given point can only belong to one mark, so some marks are hard to hit with the mouse. Every mark stays reachable by keyboard and has an accessible name, which is the equivalent path WCAG 2.5.8 allows; if mouse precision matters, expand the pane.
- The marks are a vertical toolbar (`role="toolbar"`, `aria-orientation="vertical"`) with one tab stop: Tab lands on the mark nearest `selectedPosition`, ArrowUp/ArrowDown move one mark (stopping at the ends) and Home/End jump to the first and last. While focus stays in the toolbar the tab stop follows it; once focus leaves, the next Tab in lands next to the notch again. Focus calls `onMarkHover` and blur calls `onMarkLeave`, as mouse enter and leave do.
- In forced-colors mode (Windows High Contrast) the bars are drawn in `CanvasText`, the centre line in `GrayText` and the notch in `Highlight`; tones are not shown, so put the tone's meaning in each mark's `label` (e.g. `'Rejected: Retry policy'`). Keyboard focus shows as a `Highlight` outline.
- There is no built-in tooltip. Use `onMarkHover`'s `anchor` with your own hover card (for example a `Popover` or `Tooltip` you position yourself).
- The notch line is drawn under the marks so the selected mark stays visible; its arrow sits on the rail's outer edge.
- `selectedPosition` and `position` are clamped to 0..1; a non-finite position is drawn at 0.

## Responsive hooks

### useMediaQuery

```ts
function useMediaQuery(query: string, serverValue?: boolean): boolean
```

Returns whether `window.matchMedia(query)` currently matches, and re-renders when the match changes. Re-subscribes when `query` changes. Server rendering and hydration see `serverValue` (default `false`).

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
- Server rendering and hydration return `serverValue` (default `false`); the client then re-renders with the real match, so server HTML hydrates without a mismatch (it uses `useSyncExternalStore` with a server snapshot). A client-only render (`createRoot`) already reflects the real match on its first render.
- For a layout switch that server HTML should get right before hydration, prefer a CSS `@media` rule; the hook can only correct the layout after hydration.
- `ShellLayout`, `Topbar` and `Statusbar` use it internally for their `mobileBreakpoint` behavior.
