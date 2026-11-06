---
name: heimdall-page-patterns
description: Heimdall component guide for Page Patterns: PageHeader, FilterBar, ActivityTimeline, AlertStrip, QuickAccessGrid, QuickAccessTile, ConfigTile, PipelineCard, FormCallout, RowMenu
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

Version history and diff views (`VersionTimeline`, `DiffViewer`) are documented in the `heimdall-observability` skill.

## PageHeader

Page title block: `<h1>` title with optional eyebrow row, identifier chip, subtitle, and right-aligned action slot.

```tsx
import { PageHeader } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | required | Text of the `<h1>` |
| `eyebrow` | `ReactNode` | — | Context row above title; strings render uppercase mono |
| `idChip` | `string` | — | Identifier chip rendered inside the `<h1>` |
| `subtitle` | `string` | — | Secondary line below title |
| `actions` | `ReactNode` | — | Right-aligned actions, bottom-aligned to text block |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<PageHeader eyebrow="CONFIG" title="Settings" />
```

```tsx
<PageHeader
  eyebrow={
    <>
      <Chip variant="amber">workspace · default</Chip>
      <span>last sync 8m ago</span>
    </>
  }
  title="Entity browser"
  idChip="db_main"
  subtitle="Browse and manage data entities"
  actions={
    <Button variant="primary" size="sm">
      <Icon name="plus" size={14} /> Create entity
    </Button>
  }
/>
```

### Gotchas

- The root has `role="banner"`. A page that also renders `Titlebar` (also `role="banner"` by default) gets two banner landmarks; pass `role="region"` and an `aria-label` to override.
- A plain-string `eyebrow` is uppercased and letter-spaced by CSS. Element children (chips, spans) keep their own casing, so mixed eyebrows can be passed as a fragment; items are laid out in a row with a 10px gap.
- `idChip` renders inside the `<h1>`, so its text is part of the heading's accessible name.
- No responsive stacking: title and actions stay side by side; the text block shrinks (`min-width: 0`) while actions never shrink.

---

## FilterBar

Search input with optional inline controls, a "Showing X of Y" caption, and a row of removable filter chips.

```tsx
import { FilterBar } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `filters` | `FilterChip[]` | `[]` | Active filter chips |
| `value` | `string` | — | Controlled search value |
| `defaultValue` | `string` | `''` | Initial uncontrolled search value |
| `onSearchChange` | `(query: string) => void` | — | Called on every keystroke |
| `onFilterRemove` | `(filterId: string) => void` | — | Called when a chip's × is clicked |
| `onClearAll` | `() => void` | — | Called when "Clear all" is clicked |
| `searchPlaceholder` | `string` | `'Search...'` | Search input placeholder |
| `children` | `ReactNode` | — | Inline controls beside the search input |
| `showingCount` | `number` | — | Shown count for caption (needs `totalCount`) |
| `totalCount` | `number` | — | Total count for caption (needs `showingCount`) |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

```ts
interface FilterChip {
  id: string
  label: string
}
```

### Usage

```tsx
<FilterBar searchPlaceholder="Search entities..." onSearchChange={setQuery} />
```

```tsx
const [query, setQuery] = useState('')
const [view, setView] = useState<string | number>('all')
const [filters, setFilters] = useState<FilterChip[]>([
  { id: 'active', label: 'status: active' },
  { id: 'domain', label: 'domain: life' },
])

<FilterBar
  value={query}
  onSearchChange={setQuery}
  filters={filters}
  onFilterRemove={id => setFilters(f => f.filter(c => c.id !== id))}
  onClearAll={() => {
    setFilters([])
    setQuery('')
  }}
  searchPlaceholder="Search entities..."
  showingCount={12}
  totalCount={340}
>
  <SegmentedControl
    value={view}
    onChange={setView}
    options={[
      { value: 'all', label: 'All' },
      { value: 'mine', label: 'Mine' },
    ]}
  />
</FilterBar>
```

### Gotchas

- The search is controlled when `value` is defined, uncontrolled otherwise. "Clear all" resets the internal search text only in uncontrolled mode; in controlled mode clear `value` yourself in `onClearAll`.
- The chip row (and with it "Clear all") renders only when `filters` is non-empty. "Clear all" additionally requires `onClearAll`.
- Each chip's × button always renders; without `onFilterRemove` it does nothing.
- The caption renders only when both `showingCount` and `totalCount` are set.
- Filtering is not built in: `onSearchChange` fires on every keystroke and the parent filters (and debounces, if needed) the data.
- The input's accessible name is fixed to "Search".

---

## ActivityTimeline

Vertical feed of timestamped events with type-colored dots, optional kind tags, meta lines, and clickable rows.

```tsx
import { ActivityTimeline } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `events` | `ActivityEvent[]` | `[]` | Events to render, in the given order |
| `emptyState` | `string` | `'No activity recorded'` | Message when `events` is empty |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

```ts
type ActivityEventType = 'create' | 'update' | 'delete' | 'run'

interface ActivityEvent {
  id: string
  type: ActivityEventType
  subject: string
  timestamp: Date | string
  kind?: string                // monospace tag before the subject
  kindLabel?: string           // display text for the tag (defaults to kind)
  dotColor?: StatusColor       // overrides the type color
  headline?: ReactNode         // rendered instead of subject
  meta?: string                // secondary line below the subject
  onClick?: (event: ActivityEvent) => void
}
```

Type → dot color: `create`=emerald, `update`=cyan, `delete`=rose, `run`=amber. `StatusColor` is `'emerald' | 'amber' | 'rose' | 'cyan' | 'violet' | 'neutral'`.

### Usage

```tsx
<ActivityTimeline events={[]} emptyState="No activity recorded yet." />
```

```tsx
<ActivityTimeline
  events={[
    {
      id: 'evt_01',
      type: 'create',
      subject: 'Created entity cls_organism',
      headline: <>Created entity <code>cls_organism</code></>,
      timestamp: new Date(Date.now() - 5 * 60000),
      kind: 'schema',
      onClick: ev => openEvent(ev.id),
    },
    {
      id: 'evt_02',
      type: 'update',
      subject: 'Updated schema for life',
      timestamp: '2026-10-25T14:02:00Z',
      kind: 'data',
      kindLabel: 'data import',
      dotColor: 'violet',
      meta: 'user: admin · source: api',
    },
  ]}
/>
```

### Gotchas

- Timestamps render as relative labels: "just now" (<1 min), "5m ago", "2h ago", "3d ago", then `toLocaleDateString()` from 7 days on. An unparseable string renders an empty label. Labels are computed at render time and do not tick.
- `subject` is plain text: backticks are not parsed (unlike `FormCallout`). For inline code or emphasis pass `headline`, which replaces `subject` in the row; `subject` is still required.
- `kindLabel` is ignored unless `kind` is set. `kind` is also written to the row as `data-kind`.
- An event with `onClick` gets `role="button"`, `tabIndex={0}`, and fires on Enter or Space. Rows without it are not focusable.
- Events are not sorted; pass them newest-first.

---

## AlertStrip

Stacked list of compact severity alerts, each with a colored dot, message, and optional dismiss button.

```tsx
import { AlertStrip } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `alerts` | `Alert[]` | `[]` | Alerts to display |
| `onDismiss` | `(alertId: string) => void` | — | Called on ×; dismiss buttons hidden without it |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

```ts
type AlertSeverity = 'error' | 'warn' | 'info' | 'success'

interface Alert {
  id: string
  severity: AlertSeverity
  message: string
}
```

Severity → dot color: `error`=rose, `warn`=amber, `info`=cyan, `success`=emerald.

### Usage

```tsx
<AlertStrip alerts={[{ id: 'alt_01', severity: 'info', message: 'Index rebuild scheduled for 02:00 UTC' }]} />
```

```tsx
const [alerts, setAlerts] = useState<Alert[]>([
  { id: 'alt_db', severity: 'error', message: 'Database connection lost' },
  { id: 'alt_mem', severity: 'warn', message: 'Memory usage above 85% on svc_ingest' },
])

<AlertStrip
  alerts={alerts}
  onDismiss={id => setAlerts(a => a.filter(x => x.id !== id))}
/>
```

### Gotchas

- Returns `null` when `alerts` is empty: no container is rendered and a forwarded `ref` stays `null`.
- Dismissal is not stored internally; remove the alert from `alerts` in `onDismiss`.
- Alerts carry no ARIA live role. Add `role="status"` or `aria-live` on the strip if new alerts must be announced.
- `message` is a plain string; no links or inline code.

---

## QuickAccessGrid

Grid of `QuickAccessTile` buttons driven by a data array, for landing-page shortcuts.

```tsx
import { QuickAccessGrid } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `tiles` | `QuickAccessGridItem[]` | required | Tile definitions |
| `onAction` | `(tileId: string) => void` | — | Called with the clicked tile's `id` |
| `columns` | `number` | `4` | Fixed grid column count |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

```ts
interface QuickAccessGridItem {
  id: string
  icon: IconName
  title: string
  description: string
}
```

### Usage

```tsx
<QuickAccessGrid
  tiles={[
    { id: 'create', icon: 'plus', title: 'Create entity', description: 'Add a new entity to the schema' },
    { id: 'schema', icon: 'schema', title: 'View schema', description: 'Browse the full schema graph' },
  ]}
  onAction={id => navigate(`/${id}`)}
  columns={2}
/>
```

```tsx
const isNarrow = useMediaQuery('(max-width: 1024px)')

<QuickAccessGrid
  tiles={[
    { id: 'create', icon: 'plus', title: 'Create entity', description: 'Add a new entity to the schema' },
    { id: 'schema', icon: 'schema', title: 'View schema', description: 'Browse the full schema graph' },
    { id: 'export', icon: 'data', title: 'Export data', description: 'Download a filtered data export' },
    { id: 'pipeline', icon: 'pipeline', title: 'Run pipeline', description: 'Execute a processing task' },
  ]}
  onAction={setLastAction}
  columns={isNarrow ? 2 : 4}
/>
```

### Gotchas

- `columns` is fixed (`repeat(columns, 1fr)`); there are no responsive breakpoints. Switch the value with `useMediaQuery` for narrow canvases.
- `description` is required on grid items (it is optional on a standalone `QuickAccessTile`).
- Tiles cannot be disabled or given individual handlers through the grid; render `QuickAccessTile` directly for that.

---

## QuickAccessTile

Single shortcut button with an icon tile, title, optional description, and trailing chevron.

```tsx
import { QuickAccessTile } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `icon` | `IconName` | required | Icon shown in the leading tile |
| `title` | `string` | required | Primary label |
| `description` | `string` | — | Secondary line below title |
| `...buttonProps` | | | Remaining props (`onClick`, `disabled`, …) spread onto the root `<button>` |

### Usage

```tsx
<QuickAccessTile icon="plus" title="Create new" onClick={() => openCreate()} />
```

```tsx
<div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
  <QuickAccessTile icon="schema" title="View schema" description="Browse the full schema graph" onClick={() => navigate('/schema')} />
  <QuickAccessTile icon="data" title="Export data" description="Download a filtered data export" onClick={() => navigate('/export')} />
  <QuickAccessTile icon="lock" title="Access policies" description="Requires admin role" disabled />
</div>
```

### Gotchas

- Renders a native `<button type="button">`; do not wrap it in another button or link. For navigation, call the router in `onClick`.
- The trailing chevron is always rendered and cannot be removed.

---

## ConfigTile

Settings-page tile button with a 24px icon, title, description, a key/value summary grid, and trailing chevron.

```tsx
import { ConfigTile } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `icon` | `IconName` | required | Leading icon (24px) |
| `title` | `string` | required | Primary label |
| `description` | `string` | — | Secondary line below title |
| `summary` | `ConfigTileSummaryItem[]` | `[]` | Key/value pairs of current configuration |
| `onClick` | `() => void` | — | Click handler (no event argument) |
| `...buttonProps` | | | Remaining props (`disabled`, `type`, …) spread onto the root `<button>`; `type` defaults to `'button'` |

### Data types

```ts
interface ConfigTileSummaryItem {
  label: string
  value: string
}
```

### Usage

```tsx
<ConfigTile icon="schema" title="Schema settings" onClick={() => navigate('/settings/schema')} />
```

```tsx
<ConfigTile
  icon="data"
  title="Database"
  description="PostgreSQL connection and pool settings"
  summary={[
    { label: 'host', value: 'db.internal' },
    { label: 'port', value: '5432' },
    { label: 'pool', value: '20' },
  ]}
  onClick={() => navigate('/settings/db')}
/>

<ConfigTile
  icon="lock"
  title="Retention"
  summary={[{ label: 'env', value: 'production' }]}
  disabled
/>
```

### Gotchas

- `onClick` is typed `() => void`; the mouse event is not exposed through the prop type.
- `summary` values are strings; convert numbers before passing. The summary grid is omitted when the array is empty.
- `disabled` both disables the button and applies the dimmed `config-tile--disabled` style.

---

## PipelineCard

Pipeline status card: name, id, status/target/tag chips, run controls, a stage flow strip, and a recent-stats footer.

```tsx
import { PipelineCard } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `pipeline` | `Pipeline` | required | Pipeline data |
| `onRun` | `() => void` | — | Shows a Run button when status is not `running` |
| `onCancel` | `() => void` | — | Shows a Cancel button while `running` |
| `onOptions` | `() => void` | — | Shows a kebab button that calls this |
| `compact` | `boolean` | `false` | Tighter padding in head, flow, and footer |
| `selected` | `boolean` | `false` | Amber border and 1px amber ring |
| `headerAction` | `ReactNode` | — | Extra element before the Run/Cancel buttons |
| `footerContent` | `ReactNode` | — | Replaces the default stats row |
| `flowLayout` | `'fill' \| 'auto'` | `'fill'` | `fill`: equal-width stages; `auto`: content-sized, left-packed |
| `...divProps` | | | Remaining props (`onClick`, `style`, …) spread onto the root `<div>` |

### Data types

```ts
interface Pipeline {
  id: string
  name: string
  description?: string
  status: 'running' | 'success' | 'idle' | 'failed'
  target?: string
  flow: FlowNode[]
  recent: {
    ingested: number | string
    created: number | string
    updated: number | string
    errors: number
  }
  tags?: string[]
  lastRun?: string
}

interface FlowNode {
  id: string
  name: string
  label?: string
  icon: IconName | React.ReactElement
  color?: StatusColor   // stage tint; amber accent when omitted
}
```

Status → chip color: `running`=cyan, `success`=emerald, `idle`=neutral, `failed`=rose.

### Usage

```tsx
<PipelineCard
  pipeline={{
    id: 'pl_nightly_export',
    name: 'nightly_export',
    status: 'idle',
    flow: [
      { id: 'read', name: 'read', icon: 'data' },
      { id: 'write', name: 'write', icon: 'upload' },
    ],
    recent: { ingested: 0, created: 0, updated: 0, errors: 0 },
  }}
  onRun={() => runPipeline('pl_nightly_export')}
/>
```

```tsx
<PipelineCard
  pipeline={{
    id: 'pl_gbif_ingest',
    name: 'gbif_ingest',
    description: 'Ingests occurrence records and writes resolved entities to the graph.',
    status: 'running',
    target: 'graph.entities',
    flow: [
      { id: 'src', name: 'Source', label: 'GBIF API', icon: 'schema', color: 'cyan' },
      { id: 'ext', name: 'Extract', label: '12 fields', icon: 'download', color: 'violet' },
      { id: 'res', name: 'Resolve', label: 'match by name', icon: 'lock', color: 'amber' },
      { id: 'out', name: 'Write', label: 'graph.entities', icon: 'data', color: 'emerald' },
    ],
    recent: { ingested: '15.2k', created: 1204, updated: 388, errors: 3 },
    tags: ['nightly'],
    lastRun: '30s ago',
  }}
  onRun={() => runPipeline('pl_gbif_ingest')}
  onCancel={() => cancelPipeline('pl_gbif_ingest')}
  headerAction={
    <RowMenu
      placement="bottom-end"
      actions={[
        { id: 'edit', label: 'Edit', icon: 'edit' },
        { type: 'separator' },
        { id: 'delete', label: 'Delete', icon: 'trash', danger: true },
      ]}
      onAction={handlePipelineAction}
      triggerLabel="Pipeline actions"
    />
  }
  selected={selectedId === 'pl_gbif_ingest'}
  onClick={() => setSelectedId('pl_gbif_ingest')}
  style={{ cursor: 'pointer' }}
/>
```

### Gotchas

- Run and Cancel are mutually exclusive on `status`: Run only when not `running`, Cancel only when `running`. Each also needs its handler.
- `onOptions` only renders a kebab button and calls back; no menu is built in. For an actual menu, pass a `RowMenu` through `headerAction`. The card root has `overflow: hidden`, so open the menu downward (`bottom-*`) and keep the card tall enough, or the panel is clipped.
- `selected` is visual only. Selection needs an `onClick` on the card, and clicks on Run, Cancel, kebab, or `headerAction` bubble to that handler; call `e.stopPropagation()` inside custom header elements if needed.
- `pipeline.name` and `pipeline.id` both render (name above id, both mono); use a readable `name` and the raw identifier as `id` to avoid showing the same string twice.
- The flow strip scrolls horizontally when stages overflow. With `flowLayout="fill"` stage text truncates instead; use `'auto'` for many or long-named stages.
- `FlowNode.icon` accepts an `IconName` (rendered at 16px) or any element. `color` tints the stage border and icon tile.
- The errors column turns red when `Number(recent.errors) > 0`. `lastRun` falls back to `—`. `footerContent` replaces the entire stats row.

---

## FormCallout

Inline info, warning, or error block inside forms, with backtick-delimited code rendered as `<code>`.

```tsx
import { FormCallout } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `variant` | `'info' \| 'warn' \| 'error'` | `'info'` | Color and default ARIA role |
| `icon` | `IconName` | — | Leading icon; none rendered when omitted |
| `children` | `ReactNode` | required | Callout body |
| `...divProps` | | | Remaining props spread onto the root `<div>` (`role` overrides the default) |

### Usage

```tsx
<FormCallout>Schema changes take effect on the next pipeline run.</FormCallout>
```

```tsx
<FormCallout variant="error" icon="alert">
  Validation failed: `target` must be a fully-qualified table name.
</FormCallout>

<FormCallout variant="warn" icon="alert">
  Changing `pool_size` restarts every connection to `svc_ingest`.
</FormCallout>
```

### Gotchas

- Backtick parsing applies only when `children` is a single string. JSX with interpolation (`Field {name} is required`) produces an array of children and is rendered as-is; build a template string first (`` {`Field \`${name}\` is required`} ``) or write `<code>` elements yourself.
- Default role: `error` and `warn` → `role="alert"` (announced immediately), `info` → `role="note"`. Pass `role` to override, e.g. `role="note"` for a static warning that should not interrupt screen readers.
- No icon is inferred from `variant`; pass `icon` explicitly.

---

## RowMenu

Kebab trigger that opens a dropdown of row actions, with separators, danger and disabled items, and full keyboard navigation.

```tsx
import { RowMenu } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `actions` | `RowMenuAction[]` | required | Menu items and separators |
| `onAction` | `(actionId: string) => void` | required | Called with the selected item's `id` |
| `trigger` | `ReactNode` | — | Custom content inside the trigger button |
| `triggerIcon` | `IconName` | `'moreVertical'` | Icon for the default trigger |
| `triggerLabel` | `string` | `'Menu'` | `aria-label` for trigger and menu |
| `placement` | `DropdownPlacement` | `'bottom-start'` | Panel side and edge alignment |
| `...divProps` | | | Remaining props (except `onChange`) spread onto the root `<div>` |

### Data types

```ts
type RowMenuAction =
  | { id: string; label: string; icon?: IconName; danger?: boolean; disabled?: boolean }
  | { type: 'separator' }

type DropdownPlacement = 'bottom-start' | 'bottom-end' | 'top-start' | 'top-end'
```

`bottom-*` opens below the trigger, `top-*` above; `*-start` aligns the panel's left edge with the trigger, `*-end` its right edge.

### Usage

```tsx
<RowMenu
  actions={[
    { id: 'view', label: 'View details', icon: 'eye' },
    { id: 'export', label: 'Export', icon: 'download' },
  ]}
  onAction={setLastAction}
/>
```

```tsx
<RowMenu
  placement="bottom-end"
  triggerLabel="Actions for cls_organism"
  actions={[
    { id: 'edit', label: 'Edit', icon: 'edit' },
    { id: 'duplicate', label: 'Duplicate', icon: 'copy' },
    { type: 'separator' },
    { id: 'archive', label: 'Archive', icon: 'download', disabled: true },
    { id: 'delete', label: 'Delete', icon: 'trash', danger: true },
  ]}
  onAction={id => handleRowAction('cls_organism', id)}
/>
```

### Gotchas

- Use `placement="bottom-end"` for a kebab in the last table column so the panel opens leftward into the table instead of past the right edge.
- The panel is absolutely positioned inside the RowMenu root (`z-index: 1000`, max height 320px, scrolls beyond). Ancestors with `overflow: hidden` or a scroll container clip it; use `top-*` placements near the bottom of a scroll area.
- `trigger` is rendered inside the component's own `<button>`; pass an icon or text, never a `Button` (nested buttons are invalid). `triggerLabel` stays the accessible name even with a custom trigger.
- The menu closes after any selection, on outside mousedown, and on Escape; focus returns to the trigger on close.
- Opening focuses the first enabled item. ArrowUp/ArrowDown wrap, Tab/Shift+Tab cycle items, Home/End jump; Enter/Space activates the focused item. Disabled items are skipped by keys and hover, and cannot be clicked.
- Inside a clickable table row, the trigger click bubbles to the row; wrap the menu in an element with `onClick={e => e.stopPropagation()}` if the row handler must not fire.
