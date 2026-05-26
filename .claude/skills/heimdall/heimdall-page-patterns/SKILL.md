---
name: heimdall-page-patterns
description: Heimdall component guide for Page Patterns: PageHeader, FilterBar, ActivityTimeline, AlertStrip, QuickAccessGrid, QuickAccessTile, ConfigTile, PipelineCard, FormCallout, RowMenu
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## PageHeader

Semantic `<h1>` page heading with optional eyebrow label, identifier chip, subtitle, and action slot.

```tsx
import { PageHeader } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | required | Primary heading |
| `eyebrow` | `string` | — | Monospace uppercase label above title |
| `idChip` | `string` | — | Identifier shown as monospace chip beside title |
| `subtitle` | `string` | — | Secondary description below title |
| `actions` | `ReactNode` | — | Right-aligned action slot |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
<PageHeader title="Entity Browser" />
```

```tsx
<PageHeader
  eyebrow="DATABASE"
  title="Entity Browser"
  idChip="db_main"
  subtitle="Browse and manage your data entities"
  actions={
    <Button variant="primary" size="sm">
      <Icon name="plus" size={14} /> Create Entity
    </Button>
  }
/>
```

---

## FilterBar

Search input with active filter chips, count summary, and optional inline controls slot.

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
| `onFilterRemove` | `(filterId: string) => void` | — | Called when chip × is clicked |
| `onClearAll` | `() => void` | — | Called when "Clear all" is clicked |
| `searchPlaceholder` | `string` | `'Search...'` | Search input placeholder |
| `showingCount` | `number` | — | Shown count for "Showing X of Y" (requires `totalCount`) |
| `totalCount` | `number` | — | Total count (requires `showingCount`) |
| `children` | `ReactNode` | — | Inline controls (e.g. SegmentedControl, FilterDropdown) |

```ts
interface FilterChip {
  id: string
  label: string
}
```

### Usage

```tsx
<FilterBar
  filters={filters}
  onSearchChange={setQuery}
  onFilterRemove={id => setFilters(f => f.filter(c => c.id !== id))}
  onClearAll={() => setFilters([])}
  searchPlaceholder="Search entities..."
  showingCount={12}
  totalCount={340}
>
  <SegmentedControl value={view} onChange={setView} options={viewOptions} />
</FilterBar>
```

### Gotchas

- "Clear all" button only renders when `filters` is non-empty AND `onClearAll` is provided
- Result count caption only renders when both `showingCount` and `totalCount` are provided
- `onSearchChange` fires on every keystroke — debounce in the parent if needed

---

## ActivityTimeline

Vertical list of timestamped events with type-colored dots, kind tags, and optional click interaction.

```tsx
import { ActivityTimeline } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `events` | `ActivityEvent[]` | `[]` | Events to render |
| `emptyState` | `string` | `'No activity recorded'` | Message when events is empty |
| `...HTMLAttributes` | | | Standard div attributes |

```ts
interface ActivityEvent {
  id: string
  type: 'create' | 'update' | 'delete' | 'run'
  subject: string
  timestamp: Date | string
  kind?: string
  kindLabel?: string
  headline?: ReactNode
  dotColor?: StatusColor          // overrides type default
  meta?: string
  onClick?: (event: ActivityEvent) => void
}
```

Type → dot color: `create`=emerald, `update`=cyan, `delete`=rose, `run`=amber.

### Usage

```tsx
<ActivityTimeline events={[]} emptyState="No activity yet." />
```

```tsx
<ActivityTimeline
  events={[
    {
      id: '1',
      type: 'create',
      subject: 'Created entity `cls_organism`',
      timestamp: new Date(Date.now() - 5 * 60000),
      kind: 'schema',
      onClick: ev => navigate(`/events/${ev.id}`),
    },
    {
      id: '2',
      type: 'update',
      subject: 'Updated schema for `life`',
      timestamp: new Date(Date.now() - 2 * 3600000),
      meta: 'user: admin · source: api',
    },
  ]}
/>
```

### Gotchas

- Timestamps are automatically formatted as relative labels ("5m ago", "2h ago", "3d ago", full date if >7 days)
- When `onClick` is provided on an event, the row becomes keyboard-interactive (Enter/Space)
- `dotColor` overrides the type-based color when provided

---

## AlertStrip

Horizontal strip of dismissible severity alerts. Returns `null` when the alerts array is empty.

```tsx
import { AlertStrip } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `alerts` | `Alert[]` | `[]` | Alerts to display |
| `onDismiss` | `(alertId: string) => void` | — | Called when × is clicked; dismiss button hidden when not provided |
| `...HTMLAttributes` | | | Standard div attributes |

```ts
interface Alert {
  id: string
  severity: 'error' | 'warn' | 'info' | 'success'
  message: string
}
```

Severity → color: `error`=rose, `warn`=amber, `info`=cyan, `success`=emerald.

### Usage

```tsx
const [alerts, setAlerts] = useState<Alert[]>([
  { id: '1', severity: 'error', message: 'Database connection lost' },
  { id: '2', severity: 'warn', message: 'High memory usage detected' },
])

<AlertStrip
  alerts={alerts}
  onDismiss={id => setAlerts(a => a.filter(x => x.id !== id))}
/>
```

### Gotchas

- Returns `null` (renders nothing) when `alerts` is empty — no empty container in the DOM
- Dismiss buttons only appear when `onDismiss` is provided

---

## QuickAccessGrid

Grid of icon-button tiles for primary action shortcuts.

```tsx
import { QuickAccessGrid } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `tiles` | `QuickAccessGridItem[]` | required | Tile definitions |
| `onAction` | `(tileId: string) => void` | — | Called with tile id on click |
| `columns` | `number` | `4` | Grid column count |
| `...HTMLAttributes` | | | Standard div attributes |

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
    { id: 'create', icon: 'plus', title: 'Create Entity', description: 'Add a new entity to the schema' },
    { id: 'schema', icon: 'schema', title: 'View Schema', description: 'Browse the full schema graph' },
    { id: 'export', icon: 'data', title: 'Export Data', description: 'Download a filtered data export' },
    { id: 'pipeline', icon: 'pipeline', title: 'Run Pipeline', description: 'Execute a processing task' },
  ]}
  onAction={setLastAction}
  columns={4}
/>
```

---

## QuickAccessTile

Single icon-button tile for primary action shortcuts.

```tsx
import { QuickAccessTile } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `icon` | `IconName` | required | Icon to display |
| `title` | `string` | required | Primary label |
| `description` | `string` | — | Secondary description |
| `...ButtonHTMLAttributes` | | | Standard button attributes (`disabled`, `onClick`, etc.) |

### Usage

```tsx
<QuickAccessTile
  icon="plus"
  title="Create New"
  description="Start a new project or workflow"
  onClick={() => setLastClicked('create')}
/>
```

---

## ConfigTile

Configuration card button with icon, summary key/value pairs, and optional disabled state.

```tsx
import { ConfigTile } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `icon` | `IconName` | required | Icon (24px) |
| `title` | `string` | required | Primary label |
| `description` | `string` | — | Secondary description |
| `summary` | `ConfigTileSummaryItem[]` | `[]` | Key/value configuration pairs |
| `onClick` | `() => void` | — | Click handler |
| `...ButtonHTMLAttributes` | | | Standard button attributes (`disabled`, etc.) |

```ts
interface ConfigTileSummaryItem {
  label: string
  value: string
}
```

### Usage

```tsx
<ConfigTile
  icon="schema"
  title="Database Config"
  description="PostgreSQL connection and settings"
  summary={[
    { label: 'host', value: 'localhost' },
    { label: 'port', value: '5432' },
  ]}
  onClick={() => navigate('/settings/db')}
/>
```

```tsx
// Disabled
<ConfigTile
  icon="lock"
  title="Read-only Config"
  summary={[{ label: 'env', value: 'production' }]}
  disabled
/>
```

---

## PipelineCard

Pipeline status card with stage flow visualization, run/cancel controls, recent stats, and selection state.

```tsx
import { PipelineCard } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `pipeline` | `Pipeline` | required | Pipeline data object |
| `onRun` | `() => void` | — | Run button handler (shown when not running) |
| `onCancel` | `() => void` | — | Cancel button handler (shown while running) |
| `onOptions` | `() => void` | — | When provided, renders a kebab menu button |
| `compact` | `boolean` | `false` | Reduces padding throughout the card |
| `selected` | `boolean` | `false` | Amber border + glow ring |
| `headerAction` | `ReactNode` | — | Element injected into header action row |
| `footerContent` | `ReactNode` | — | Replaces default stats grid |

```ts
interface Pipeline {
  id: string
  name: string
  description?: string
  status: 'running' | 'success' | 'idle' | 'failed'
  target?: string
  flow: FlowNode[]
  recent: { ingested: number | string; created: number | string; updated: number | string; errors: number }
  tags?: string[]
  lastRun?: string
}

interface FlowNode {
  id: string
  name: string
  label?: string
  icon: IconName | React.ReactElement
}
```

Status → chip color: `running`=cyan, `success`=emerald, `idle`=neutral, `failed`=rose.

### Usage

```tsx
<PipelineCard
  pipeline={{
    id: 'data_migration_v2',
    name: 'data_migration_v2',
    description: 'Ingests raw data and persists to store',
    status: 'running',
    target: 'analytics.events',
    flow: [
      { id: '1', name: 'validate', label: 'Validate', icon: 'check' },
      { id: '2', name: 'transform', label: 'Transform', icon: 'data' },
      { id: '3', name: 'load', label: 'Load', icon: 'upload' },
    ],
    recent: { ingested: 15000, created: 15000, updated: 0, errors: 0 },
    lastRun: '30s ago',
    tags: ['nightly'],
  }}
  onRun={() => runPipeline()}
  onCancel={() => cancelPipeline()}
  onOptions={() => showMenu()}
  selected={selectedId === 'data_migration_v2'}
/>
```

### Gotchas

- While `status='running'`, the Run button is hidden and Cancel button is shown (if handlers provided)
- `FlowNode.icon` can be an `IconName` string or a custom `React.ReactElement`
- `footerContent` completely replaces the default stats grid when provided

---

## FormCallout

Contextual callout block for forms — info, warning, or error messaging with auto-parsed inline code.

```tsx
import { FormCallout } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `variant` | `'info' \| 'warn' \| 'error'` | `'info'` | Controls color and ARIA role |
| `icon` | `IconName` | — | Icon at left edge |
| `children` | `ReactNode` | required | Callout body |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
<FormCallout variant="info" icon="info">
  This field is required before the pipeline can be submitted.
</FormCallout>
```

```tsx
<FormCallout variant="error" icon="alert">
  Validation failed: `target` must be a fully-qualified table name.
</FormCallout>

<FormCallout variant="warn">
  Changing this value will reset all downstream configurations.
</FormCallout>
```

### Gotchas

- String children are automatically parsed: backtick-wrapped text (e.g. `` `some_code` ``) is rendered as `<code>` elements
- ARIA role is auto-determined: `error`/`warn` → `role="alert"`, `info` → `role="note"` (can be overridden)

---

## RowMenu

Kebab-style context menu for table rows with keyboard navigation and danger/disabled item support.

```tsx
import { RowMenu } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `actions` | `RowMenuAction[]` | required | Menu items and separators |
| `onAction` | `(actionId: string) => void` | required | Called with action id on selection |
| `trigger` | `ReactNode` | — | Custom trigger element |
| `triggerIcon` | `IconName` | `'moreVertical'` | Icon for default trigger button |
| `triggerLabel` | `string` | `'Menu'` | Accessible label for trigger and menu |
| `...HTMLAttributes` | | | Standard div attributes |

```ts
type RowMenuAction =
  | { id: string; label: string; icon?: IconName; danger?: boolean; disabled?: boolean }
  | { type: 'separator' }
```

### Usage

```tsx
<RowMenu
  actions={[
    { id: 'edit', label: 'Edit', icon: 'edit' },
    { id: 'duplicate', label: 'Duplicate', icon: 'copy' },
    { type: 'separator' },
    { id: 'archive', label: 'Archive', icon: 'download', disabled: true },
    { id: 'delete', label: 'Delete', icon: 'trash', danger: true },
  ]}
  onAction={setLastAction}
  triggerLabel="Row actions"
/>
```

### Gotchas

- Disabled items are excluded from keyboard navigation entirely (arrow keys skip them)
- Arrow keys, Home, End navigate the menu; Enter/Space selects; Escape closes and returns focus to trigger
- First enabled item auto-focuses when the menu opens
