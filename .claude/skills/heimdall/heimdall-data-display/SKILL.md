---
name: heimdall-data-display
description: Heimdall component guide for Data Display: StatTile, StatGrid, Table, KVGrid, InspectorPanel
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## StatTile

KPI metric tile with colored left bar, optional delta trend, sparkline, icon, and meta text.

```tsx
import { StatTile } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `label` | `string` | `''` | Monospace eyebrow label (e.g. `'UPTIME'`) |
| `value` | `string \| number` | `''` | Primary metric value |
| `color` | `'emerald' \| 'amber' \| 'rose' \| 'cyan' \| 'violet' \| 'neutral'` | `'cyan'` | Left bar and sparkline color |
| `delta` | `{ value: number; label?: string; direction?: 'up' \| 'down' }` | — | Trend indicator below value |
| `icon` | `IconName` | — | Icon displayed in tile |
| `sparkData` | `number[]` | — | Sparkline data points |
| `meta` | `ReactNode` | — | Secondary text below value |
| `metaIcon` | `IconName` | — | Icon before meta text |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
// Minimal
<StatTile label="UPTIME" value="99.9%" />
```

```tsx
// Full-featured
<StatTile
  label="LATENCY"
  value="42 ms"
  color="violet"
  delta={{ value: 3, label: 'vs yesterday', direction: 'down' }}
  sparkData={[55, 48, 52, 44, 42, 45, 42]}
  meta="Last 30 days"
  metaIcon="clock"
/>
```

### Gotchas

- `aria-label` defaults to `"${label}: ${value}"` if not provided
- Sparkline color automatically matches the tile's `color` prop
- Delta `direction` controls both the sign prefix (+/−) and styling

---

## StatGrid

CSS grid wrapper for laying out multiple `StatTile` components.

```tsx
import { StatGrid } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `columns` | `number` | `4` | Number of grid columns |
| `children` | `ReactNode` | required | `StatTile` components |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
<StatGrid>
  <StatTile label="CPU" value="42%" color="cyan" />
  <StatTile label="MEMORY" value="62%" color="amber" />
  <StatTile label="REQUESTS" value="1.2M" color="emerald" />
  <StatTile label="ERRORS" value="3" color="rose" />
</StatGrid>
```

```tsx
// Two-column layout
<StatGrid columns={2}>
  <StatTile label="UPTIME" value="99.9%" />
  <StatTile label="INCIDENTS" value="0" />
</StatGrid>
```

---

## Table

Data table with sorting, row selection, row click, and custom cell rendering.

```tsx
import { Table } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `columns` | `Column<T>[]` | required | Column definitions |
| `data` | `T[]` | required | Row data |
| `rowKey` | `keyof T \| ((row: T, index: number) => string \| number)` | required | Unique row identifier |
| `selectable` | `boolean` | `false` | Show checkbox column |
| `selectedRows` | `(string \| number)[]` | `[]` | Controlled selected row keys |
| `onSelectRows` | `(rowKeys: (string \| number)[]) => void` | — | Called on selection change |
| `onRowClick` | `(row: T, rowKey: string \| number) => void` | — | Called on row click |
| `onSort` | `(key: string, direction: 'asc' \| 'desc' \| null) => void` | — | Called on header click |
| `emptyState` | `ReactNode` | — | Content shown when data is empty |
| `className` | `string` | — | Additional CSS classes |

```ts
interface Column<T> {
  key: keyof T
  label: string
  sortable?: boolean
  width?: string
  render?: (value: T[keyof T], row: T, index: number) => React.ReactNode
}
```

### Usage

```tsx
// Minimal
<Table
  columns={[
    { key: 'name', label: 'NAME' },
    { key: 'status', label: 'STATUS' },
  ]}
  data={rows}
  rowKey="id"
/>
```

```tsx
// Full-featured with sorting, selection, custom render
const columns: Column<Host>[] = [
  {
    key: 'name',
    label: 'HOST',
    sortable: true,
    render: v => <span className="font-mono">{String(v)}</span>,
  },
  {
    key: 'status',
    label: 'STATUS',
    render: v => <Chip variant={statusMap[v as string]}>{String(v)}</Chip>,
  },
  { key: 'cpu', label: 'CPU', sortable: true },
]

<Table
  columns={columns}
  data={hosts}
  rowKey="id"
  selectable
  selectedRows={selected}
  onSelectRows={setSelected}
  onRowClick={(row) => navigate(`/hosts/${row.id}`)}
  onSort={(key, dir) => setSortState({ key, dir })}
  emptyState={<span>No hosts found.</span>}
/>
```

### Gotchas

- Sorting state is managed internally; `onSort` is only for external data re-fetching or side effects — sort clicking cycles asc → desc → null
- When `onRowClick` is provided, rows become keyboard-focusable (Enter or Space triggers click)
- Select-all checkbox shows indeterminate state when some but not all rows are selected
- `render()` receives `(value, row, index)` — use `row` to access other fields for conditional rendering

---

## KVGrid

Key/value metadata grid rendered as a semantic definition list.

```tsx
import { KVGrid } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `rows` | `KVGridRow[]` | `[]` | Array of key/value pairs |
| `keyWidth` | `number \| string` | `130` (via CSS) | Key column width in px or CSS string |
| `...HTMLAttributes` | | | Standard `<dl>` attributes |

```ts
interface KVGridRow {
  key: string
  value: React.ReactNode
}
```

### Usage

```tsx
<KVGrid
  rows={[
    { key: 'hostname', value: 'nyx-01.internal' },
    { key: 'ip_address', value: '192.168.1.100' },
    { key: 'cpu_cores', value: '16' },
  ]}
/>
```

```tsx
// Custom key column width
<KVGrid rows={rows} keyWidth={200} />
<KVGrid rows={rows} keyWidth="30%" />
```

### Gotchas

- Keys render uppercase via CSS — pass lowercase snake_case strings
- Renders as `<dl>`/`<dt>`/`<dd>` for semantic HTML

---

## InspectorPanel

Structured details panel for entity inspection, with optional section and property subcomponents.

```tsx
import { InspectorPanel } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | required | Primary heading |
| `id` | `string` | required | Entity identifier shown below title |
| `eyebrow` | `string` | `''` | Monospace uppercase label above title |
| `version` | `number` | — | Version number shown as amber pill |
| `actions` | `ReactNode` | — | Action buttons in the header |
| `children` | `ReactNode` | — | `InspectorPanel.Section` or `InspectorPanel.PropertySection` |

### Compound Subcomponents

- `InspectorPanel.Section` — generic section with title and optional count/actions
- `InspectorPanel.PropertySection` — specialized section for tabular key/value rows

**InspectorPanel.Section props:**

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | required | Section heading |
| `count` | `number` | — | Count shown after title with `·` separator |
| `actions` | `ReactNode` | — | Action buttons in section header |
| `children` | `ReactNode` | — | Section content |

**InspectorPanel.PropertySection props:**

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | required | Section heading |
| `count` | `number` | — | Count shown inline |
| `actionIcon` | `ReactNode` | — | Icon for action button |
| `actionLabel` | `string` | — | Accessible label for action button |
| `onAction` | `() => void` | — | Action button handler; button only renders when provided |
| `rows` | `PropertyRow[]` | required | Key/value/usage rows |

```ts
interface PropertyRow {
  key: string
  value: string
  usageCount?: number
}
```

### Usage

```tsx
// Minimal
<InspectorPanel title="Organism" id="cls_4f3a" eyebrow="CLASS">
  <InspectorPanel.Section title="Properties">
    <KVGrid rows={[{ key: 'domain', value: 'life' }]} />
  </InspectorPanel.Section>
</InspectorPanel>
```

```tsx
// Full-featured with PropertySection
<InspectorPanel
  eyebrow="SCHEMA"
  title="cls_organism"
  id="cls_4f3a"
  version={2}
  actions={<Button variant="ghost" size="sm"><Icon name="edit" size={14} /></Button>}
>
  <InspectorPanel.PropertySection
    title="Fields"
    count={3}
    actionIcon={<Icon name="plus" size={12} />}
    actionLabel="Add field"
    onAction={() => setAddingField(true)}
    rows={[
      { key: 'name', value: 'string', usageCount: 47 },
      { key: 'status', value: 'enum', usageCount: 47 },
      { key: 'created_at', value: 'datetime', usageCount: 12 },
    ]}
  />
  <InspectorPanel.Section title="Tags" count={2}>
    <div className="flex gap-1">
      <Chip form="id-tag">production</Chip>
      <Chip form="id-tag">critical</Chip>
    </div>
  </InspectorPanel.Section>
</InspectorPanel>
```

### Gotchas

- `InspectorPanel.Section` and `InspectorPanel.PropertySection` must be used inside `<InspectorPanel>` — they depend on its context
- The action button in `PropertySection` only renders when `onAction` is provided
- `version` renders as an amber `VersionPill` only when the prop is defined
