---
name: heimdall-data-display
description: Heimdall component guide for Data Display: StatTile, StatGrid, Table, KVGrid, InspectorPanel, ResultCard, AssetCard, AssetGrid, MapCanvas
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## StatTile

KPI tile with a colored left bar, optional delta, sparkline, icon and meta line.

```tsx
import { StatTile } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `label` | `string` | `''` | Monospace eyebrow label, rendered uppercase |
| `value` | `string \| number` | `''` | Primary metric value |
| `color` | `'emerald' \| 'amber' \| 'rose' \| 'cyan' \| 'violet' \| 'neutral'` | `'cyan'` | Left bar and sparkline color (`StatusColor`) |
| `delta` | `{ value: number; label?: string; direction?: 'up' \| 'down' }` | — | Trend line under the value |
| `icon` | `IconName` | — | 14px icon in the header, right of the label |
| `sparkData` | `number[]` | — | Sparkline data points (88×28) |
| `meta` | `ReactNode` | — | Secondary text in the footer |
| `metaIcon` | `IconName` | — | 12px icon before `meta` |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<StatTile label="UPTIME" value="99.9%" />
```

```tsx
<StatTile
  label="LATENCY"
  value="42 ms"
  color="violet"
  icon="clock"
  delta={{ value: 3, label: 'vs yesterday', direction: 'down' }}
  sparkData={[55, 48, 52, 44, 42, 45, 42]}
  meta="p95, last 30 days"
  metaIcon="clock"
/>
```

### Gotchas

- `delta.direction` decides both the sign and the color: `'up'` (the default) renders `+` in emerald, `'down'` renders `−` in rose. The sign of `delta.value` is ignored (`Math.abs`). There is no "down is good" option, so a falling latency still reads rose.
- `aria-label` defaults to `` `${label}: ${value}` ``; pass `aria-label` to override.
- The footer only renders when `delta` or `meta` is set; `metaIcon` without `meta` renders nothing.
- The sparkline uses the tile's `color`; it cannot be colored separately.

---

## StatGrid

Responsive grid for a row of `StatTile`s (14px gap).

```tsx
import { StatGrid } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `columns` | `number` | `4` | Column count at full width (1–6) |
| `children` | `ReactNode` | required | `StatTile` elements |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<StatGrid>
  <StatTile label="CPU" value="42%" color="cyan" />
  <StatTile label="MEMORY" value="62%" color="violet" />
  <StatTile label="REQUESTS" value="1.2M" color="emerald" />
  <StatTile label="ERRORS" value="3" color="rose" />
</StatGrid>
```

```tsx
<StatGrid columns={2}>
  <StatTile label="STORAGE_USED" value="4.2 TB" color="emerald" />
  <StatTile label="STORAGE_FREE" value="8.1 TB" color="cyan" />
</StatGrid>
```

### Gotchas

- Only `columns` 1–6 have CSS (`stat-grid--cols-N`); any other value leaves the grid without `grid-template-columns`, so tiles stack in one column.
- Columns collapse responsively: at ≤1400px 4/5/6 become 3/4/5; at ≤1024px 3–6 become 2; at ≤640px everything is 1 column.

---

## Table

Generic data table with sortable headers, checkbox selection, clickable rows and custom cell rendering.

```tsx
import { Table, type Column } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `columns` | `Column<T>[]` | required | Column definitions |
| `data` | `T[]` | required | Row objects |
| `rowKey` | `keyof T \| ((row: T, index: number) => string \| number)` | required | Field or function giving a unique row key |
| `selectable` | `boolean` | `false` | Adds a checkbox column and select-all header |
| `selectedRows` | `(string \| number)[]` | `[]` | Selected row keys (controlled) |
| `onSelectRows` | `(rowKeys: (string \| number)[]) => void` | — | Called with the next selected keys |
| `onRowClick` | `(row: T, rowKey: string \| number) => void` | — | Makes rows clickable and focusable |
| `onSort` | `(key: string, direction: 'asc' \| 'desc' \| null) => void` | — | Called when a sortable header is activated |
| `emptyState` | `ReactNode` | — | Single full-width row shown when `data` is empty |
| `className` | `string` | `''` | Extra class on the `<table>` |

### Data types

`Column<T>` (exported):

| Field | Type | Description |
| ----- | ---- | ----------- |
| `key` | `keyof T` | Field read from each row |
| `label` | `string` | Header text, rendered uppercase mono |
| `sortable` | `boolean` | Header becomes clickable and focusable |
| `width` | `string` | CSS width for the header cell |
| `render` | `(value: T[keyof T], row: T, index: number) => ReactNode` | Custom cell content |

### Usage

```tsx
type Host = { id: string; name: string; status: string; cpu: string }

const hosts: Host[] = [
  { id: 'svc_ingest', name: 'nyx-01', status: 'running', cpu: '34%' },
  { id: 'svc_query', name: 'helios-01', status: 'stopped', cpu: '0%' },
]

<Table
  columns={[
    { key: 'name', label: 'Host' },
    { key: 'status', label: 'Status' },
  ]}
  data={hosts}
  rowKey="id"
/>
```

```tsx
const STATUS_COLOR: Record<string, 'emerald' | 'amber' | 'neutral'> = {
  running: 'emerald',
  degraded: 'amber',
  stopped: 'neutral',
}

const columns: Column<Host>[] = [
  {
    key: 'name',
    label: 'Host',
    sortable: true,
    render: (v) => <span className="font-mono">{String(v)}</span>,
  },
  {
    key: 'status',
    label: 'Status',
    render: (v) => <Chip variant={STATUS_COLOR[String(v)] ?? 'neutral'}>{String(v)}</Chip>,
  },
  { key: 'cpu', label: 'CPU', sortable: true, width: '96px' },
]

function HostTable() {
  const [selected, setSelected] = useState<(string | number)[]>([])
  const [sort, setSort] = useState<{ key: keyof Host; dir: 'asc' | 'desc' } | null>(null)

  const rows = sort
    ? [...hosts].sort((a, b) => {
        const cmp = String(a[sort.key]).localeCompare(String(b[sort.key]))
        return sort.dir === 'asc' ? cmp : -cmp
      })
    : hosts

  return (
    <Table
      columns={columns}
      data={rows}
      rowKey="id"
      selectable
      selectedRows={selected}
      onSelectRows={setSelected}
      onRowClick={(row) => console.log(row.id)}
      onSort={(key, dir) => setSort(dir ? { key: key as keyof Host, dir } : null)}
      emptyState="No hosts match these filters."
    />
  )
}
```

### Gotchas

- **The table never sorts `data`.** It only tracks which header is active and draws the arrow; sort the array yourself in `onSort`. Clicking the same header cycles asc → desc → none (`direction: null`).
- Selection is fully controlled: without `onSelectRows`, checkboxes do not change. Select-all goes indeterminate when some rows are selected, and selects every row in `data` (keys from `rowKey`).
- With `onRowClick`, rows get `tabIndex={0}` and Enter/Space trigger the click. Clicking a checkbox does not fire `onRowClick`.
- When `data` is empty and `emptyState` is unset, the body renders nothing — no placeholder row.
- `className` is the only DOM prop accepted; `TableProps` does not extend table attributes. A `ref` is forwarded to the `<table>`.
- The table has `overflow: hidden` and `width: 100%`; wrap it in a scroll container for wide data.

---

## KVGrid

Two-column key/value list for entity metadata, rendered as `<dl>`/`<dt>`/`<dd>`.

```tsx
import { KVGrid, type KVGridRow } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `rows` | `KVGridRow[]` | `[]` | Key/value pairs |
| `keyWidth` | `number \| string` | `130px` (CSS) | Key column width; number is px |
| `...dlProps` | | | Remaining props spread onto the root `<dl>` |

### Data types

`KVGridRow`:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `key` | `string` | Key label; also the React key, so must be unique |
| `value` | `ReactNode` | Value content |

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
<KVGrid
  keyWidth="30%"
  rows={[
    { key: 'class_id', value: <code>cls_4f3a</code> },
    { key: 'status', value: <Chip variant="emerald">running</Chip> },
  ]}
/>
```

### Gotchas

- Keys render uppercase mono via CSS; pass lowercase snake_case.
- `keyWidth` sets `grid-template-columns` inline and is merged over any `style` you pass; `keyWidth={0}` is treated as unset.
- Duplicate `key` strings produce duplicate React keys.

---

## InspectorPanel

Full-height details panel for one entity: eyebrow, title, id, version pill, header actions, and a scrolling body of sections.

```tsx
import { InspectorPanel } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | required | Primary heading |
| `id` | `string` | required | Entity identifier shown under the title |
| `eyebrow` | `string` | `''` | Uppercase mono label above the title |
| `version` | `number` | — | Shown in an amber `VersionPill` next to `id` |
| `actions` | `ReactNode` | — | Header action buttons |
| `children` | `ReactNode` | — | `InspectorPanel.Section` / `InspectorPanel.PropertySection` |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<InspectorPanel eyebrow="CLASS" title="Organism" id="cls_4f3a">
  <InspectorPanel.Section title="Properties">
    <KVGrid rows={[{ key: 'domain', value: 'life' }]} />
  </InspectorPanel.Section>
</InspectorPanel>
```

```tsx
<div style={{ height: 480 }}>
  <InspectorPanel
    eyebrow="SCHEMA"
    title="cls_organism"
    id="cls_4f3a"
    version={2}
    actions={
      <Button variant="ghost" size="sm" icon aria-label="Edit class">
        <Icon name="edit" size={14} />
      </Button>
    }
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
</div>
```

### Compound subcomponents

#### InspectorPanel.Section

Generic titled section; the title line shows `· count` when `count` is set.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | required | Section heading |
| `count` | `number` | — | Shown after the title as `· N` |
| `actions` | `ReactNode` | — | Right-aligned header actions |
| `children` | `ReactNode` | — | Section content |
| `...divProps` | | | Remaining props spread onto the section `<div>` |

#### InspectorPanel.PropertySection

Section that renders `rows` as key / value / usage lines, with an optional icon button in the header.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | required | Section heading |
| `rows` | `PropertyRow[]` | required | Rows to list |
| `count` | `number` | — | Count shown after the title |
| `actionIcon` | `ReactNode` | — | Content of the header button |
| `actionLabel` | `string` | — | `aria-label` of the header button |
| `onAction` | `() => void` | — | Header button handler; button renders only when set |
| `...divProps` | | | Remaining props spread onto the section `<div>` |

### Data types

`PropertyRow` (exported):

| Field | Type | Description |
| ----- | ---- | ----------- |
| `key` | `string` | Property name; also the React key |
| `value` | `string` | Property value or type |
| `usageCount` | `number` | Renders `used N` when set |

### Gotchas

- `InspectorPanel.Section` and `InspectorPanel.PropertySection` throw if rendered outside an `<InspectorPanel>`.
- `id` is display text only — it is consumed by the component and **not** set as the DOM `id` attribute.
- The root is `height: 100%` with a scrolling body; give the parent a definite height (e.g. a `SplitPane` pane or fixed-height wrapper) or the body will not scroll.
- `version` renders only when defined, so `version={0}` still shows a pill. The pill shows the number as-is, with no `v` prefix.
- `Section` omits its content wrapper when `children` is falsy; `PropertySection` omits the row list when `rows` is empty.
- Give the `PropertySection` button an `actionLabel` — it is icon-only and that is its only accessible name.

---

## ResultCard

Search or retrieval result: source, version, relevance score bar, snippet, provenance and row actions.

```tsx
import { ResultCard, type ResultCardProvenance } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `domain` | `string` | required | Drives the left bar and dot color; not displayed |
| `source` | `string` | required | Source identifier in the header |
| `snippet` | `ReactNode` | required | Matched content preview |
| `version` | `string` | — | Shown in a `VersionPill` after the source |
| `score` | `number` | — | Relevance 0–1; shows value and bar |
| `provenance` | `ResultCardProvenance` | — | Collection / document / section footer |
| `actions` | `Array<{ label: string; icon?: IconName; onClick: () => void }>` | — | Ghost buttons in the footer |
| `onOpen` | `() => void` | — | Makes the card clickable and focusable |
| `selected` | `boolean` | `false` | Amber border and raised background |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

`ResultCardProvenance` (exported):

| Field | Type | Description |
| ----- | ---- | ----------- |
| `collection` | `string` | Shown as "Collection" |
| `document` | `string` | Shown as "Document" |
| `section` | `string` | Shown as "Section" |

### Usage

```tsx
<ResultCard
  domain="software"
  source="repo/heimdall-ui"
  snippet="export function useWorkspaceContext() { ... }"
/>
```

```tsx
function ResultList() {
  const [selectedId, setSelectedId] = useState<string>('res_01')
  const results = [
    { id: 'res_01', domain: 'life', source: 'pubmed/reference_genome', version: '2.5.0', score: 0.87, snippet: 'GRCh38 represents the consensus sequence of 3.2 billion base pairs.' },
    { id: 'res_02', domain: 'climate', source: 'noaa/climate_db', score: 0.76, snippet: 'Global mean temperature anomaly 2024: +1.31 °C.' },
  ]

  return (
    <div className="flex flex-col gap-3">
      {results.map((r) => (
        <ResultCard
          key={r.id}
          domain={r.domain}
          source={r.source}
          version={r.version}
          snippet={r.snippet}
          score={r.score}
          provenance={{ collection: 'publications', document: 'genome_assembly_2024.pdf', section: 'Methods' }}
          selected={selectedId === r.id}
          onOpen={() => setSelectedId(r.id)}
          actions={[
            { label: 'Copy', icon: 'copy', onClick: () => copySnippet(r.id) },
            { label: 'Share', icon: 'share', onClick: () => shareResult(r.id) },
          ]}
        />
      ))}
    </div>
  )
}
```

### Gotchas

- `domain` is never shown as text. `life`, `climate`, `software`, `data` and `infrastructure` map to the `--dom-*` tokens for the left bar; any other value falls back to amber. The header dot color is a hash of the string, so it does not match the bar.
- `score` is expected in 0–1: the label is `score.toFixed(2)` and the bar is `score * 100` percent.
- `version` is rendered verbatim — pass `'2.5.0'`, not a number. The `aria-label` becomes `` `${source} v${version}` ``.
- With `onOpen`, the whole card is clickable, gets `tabIndex={0}`, and Enter/Space trigger it. Action buttons stop propagation, so they never trigger `onOpen`.
- An action with `icon` renders an icon-only button (`label` becomes its `title`); without `icon` the `label` text is shown.
- The provenance footer renders only when at least one provenance field is defined.
- Passing `style` replaces the inline `--domain-color` variable and drops the domain bar color; use `className` for styling.

---

## AssetCard

Thumbnail card for a document, image or cover asset, with title, subtitle, meta and an optional corner badge.

```tsx
import { AssetCard, type AssetThumb } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `thumb` | `AssetThumb` | required | Thumbnail descriptor (doc, cover or image) |
| `title` | `string` | required | Asset name, clamped to two lines |
| `subtitle` | `string` | — | Secondary line |
| `meta` | `ReactNode` | — | Footer text (size, updated time) |
| `badge` | `string` | — | Label over the thumbnail corner |
| `selected` | `boolean` | `false` | Amber border; also sets `aria-selected` |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

`AssetThumb` (exported) is a union on `kind`:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `kind: 'doc'` | `{ kind: 'doc'; ext: string }` | Page glyph with an extension tab |
| `kind: 'cover'` | `{ kind: 'cover'; gradient: string; glyph: IconName }` | CSS gradient background with a 32px icon |
| `kind: 'image'` | `{ kind: 'image'; src: string; fallbackGlyph?: IconName }` | Image fill; icon shown if loading fails |

### Usage

```tsx
<AssetCard thumb={{ kind: 'doc', ext: 'pdf' }} title="architecture_guide.pdf" meta="5.2 MB" />
```

```tsx
<AssetCard
  thumb={{ kind: 'image', src: '/assets/ds_ingest_preview.png', fallbackGlyph: 'image' }}
  title="ds_ingest_preview"
  subtitle="Pipeline snapshot"
  meta="Updated 2 hours ago"
  badge="Latest"
  selected={selectedId === 'ast_01'}
  onClick={() => setSelectedId('ast_01')}
/>
```

### Gotchas

- Not interactive by itself: `onClick` works via the spread, but the card has no `tabIndex`, role or key handler. Add `tabIndex={0}`, an `onKeyDown`, and a role that supports `aria-selected` (e.g. `role="option"` inside a `role="listbox"` container) for keyboard selection.
- Doc tab colors exist for `pdf`, `doc`/`docx`, `xls`/`xlsx`, `ppt`/`pptx` and `txt` (case-insensitive); other extensions get a neutral tab. The tab shows `ext` uppercased.
- `cover.gradient` is any CSS `background` value (e.g. `'linear-gradient(135deg, #667eea, #764ba2)'`).
- Image fallback only shows when `fallbackGlyph` is set and the image errors (or `src` is empty); without it a broken image stays. Changing `src` resets the error state.
- The thumbnail is square (`aspect-ratio: 1`) and fills the card width; constrain width with a grid or wrapper.

---

## AssetGrid

Responsive grid container for `AssetCard`s.

```tsx
import { AssetGrid } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `columns` | `number` | `3` | Column count at full width |
| `gap` | `number` | `14` | Gap in px |
| `children` | `ReactNode` | required | `AssetCard` elements |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<AssetGrid>
  <AssetCard thumb={{ kind: 'doc', ext: 'pdf' }} title="architecture_guide.pdf" />
  <AssetCard thumb={{ kind: 'doc', ext: 'xlsx' }} title="q2_roadmap.xlsx" />
  <AssetCard thumb={{ kind: 'cover', gradient: 'linear-gradient(135deg, #667eea, #764ba2)', glyph: 'sparkles' }} title="design_tokens" />
</AssetGrid>
```

```tsx
<AssetGrid columns={4} gap={12} role="listbox" aria-label="Assets">
  {assets.map((a) => (
    <AssetCard
      key={a.id}
      role="option"
      tabIndex={0}
      thumb={a.thumb}
      title={a.title}
      meta={a.meta}
      selected={selectedId === a.id}
      onClick={() => setSelectedId(a.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') setSelectedId(a.id)
      }}
    />
  ))}
</AssetGrid>
```

### Gotchas

- Columns collapse responsively regardless of `columns`: at ≤1400px to `max(2, columns − 1)`, at ≤1024px to 2, at ≤640px to 1.
- `columns` and `gap` are applied as inline CSS variables; passing `style` replaces them and the grid loses its column count. Use `className` instead.

---

## MapCanvas

Pan/zoom Web Mercator map that renders pins, a track polyline, or a heatmap, over a grid or optional raster tiles.

```tsx
import { MapCanvas, type MapPin, type MapTrackPoint, type HeatmapDataPoint, type LatLng } from '@tinkermonkey/heimdall-ui'
```

### Props

`MapCanvasProps` is a union discriminated by `mode`; each mode requires its own data prop and types the others as `never`.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `mode` | `'pins' \| 'track' \| 'heatmap'` | required | Which layer to render |
| `pins` | `MapPin[]` | `[]` | Markers; required when `mode="pins"` |
| `selectedPinId` | `string` | — | Highlighted pin (pins mode only) |
| `onSelectPin` | `(pinId: string \| null) => void` | — | Pin clicked, or `null` on Escape |
| `trackPoints` | `MapTrackPoint[]` | `[]` | Polyline points; required when `mode="track"` |
| `heatmapData` | `HeatmapDataPoint[]` | `[]` | Weighted points; required when `mode="heatmap"` |
| `heatmapColor` | `string` | `'#10b981'` | Heatmap base color (hex, `rgb()` or `hsl()`) |
| `tileUrl` | `string \| ((x: number, y: number, z: number) => string)` | — | Raster tiles; grid pattern when unset |
| `bounds` | `[LatLng, LatLng]` | — | Initial area to frame; defaults to data extent |
| `scaleBar` | `boolean` | `false` | Shows a `Zoom: N.N` readout |
| `minZoom` | `number` | `0` | Minimum pan/zoom scale |
| `maxZoom` | `number` | `18` | Maximum pan/zoom scale |
| `onViewportChange` | `(viewport: { center: { lat: number; lng: number }; zoom: number }) => void` | — | Called on pan or zoom |
| `onModeChange` | `(mode: 'pins' \| 'track' \| 'heatmap') => void` | — | Shows a built-in Pins/Track/Heatmap switch |
| `...divProps` | | | Remaining props spread onto the root `<div>` (`onSelect` omitted) |

### Data types

`LatLng`:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `lat` | `number` | Latitude, decimal degrees |
| `lng` | `number` | Longitude, decimal degrees |

`MapPin`:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | `string` | Unique id; used by `selectedPinId` |
| `lat` | `number` | Latitude |
| `lng` | `number` | Longitude |
| `label` | `string` | Text on the marker and popover title |
| `detail` | `ReactNode` | Popover body |
| `timestamp` | `string` | Popover line and part of the aria-label |

`MapTrackPoint`:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `lat` | `number` | Latitude |
| `lng` | `number` | Longitude |
| `timestamp` | `string` | Accepted but not rendered |

`HeatmapDataPoint`:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `lat` | `number` | Latitude |
| `lng` | `number` | Longitude |
| `value` | `number` | Intensity; normalized min–max across the data set |

### Usage

```tsx
const pins: MapPin[] = [
  { id: 'site_nyc', lat: 40.7128, lng: -74.006, label: 'site_nyc' },
  { id: 'site_lon', lat: 51.5074, lng: -0.1278, label: 'site_lon' },
]

<div style={{ height: 480 }}>
  <MapCanvas mode="pins" pins={pins} />
</div>
```

```tsx
type MapMode = 'pins' | 'track' | 'heatmap'

function SiteMap({ pins, track, density }: { pins: MapPin[]; track: MapTrackPoint[]; density: HeatmapDataPoint[] }) {
  const [mode, setMode] = useState<MapMode>('pins')
  const [selectedPinId, setSelectedPinId] = useState<string | null>(null)

  const common = {
    scaleBar: true,
    onModeChange: setMode,
    tileUrl: 'https://tiles.example.internal/{z}/{x}/{y}.png',
  }

  return (
    <div style={{ height: 520 }}>
      {mode === 'pins' && (
        <MapCanvas
          {...common}
          mode="pins"
          pins={pins}
          selectedPinId={selectedPinId ?? undefined}
          onSelectPin={setSelectedPinId}
        />
      )}
      {mode === 'track' && <MapCanvas {...common} mode="track" trackPoints={track} />}
      {mode === 'heatmap' && <MapCanvas {...common} mode="heatmap" heatmapData={density} heatmapColor="#22d3ee" />}
    </div>
  )
}
```

### Gotchas

- Because of the discriminated union, switch modes by rendering a separate `<MapCanvas>` per mode (as above); passing `pins` together with `mode="track"` is a type error.
- The root is `width: 100%; height: 100%; min-height: 360px`. Give the parent a height.
- The initial view is fitted once, from `bounds` or else from the data extent, after the container is first measured: the data is framed with 60px padding (less in small containers) and centred. A single point opens at zoom level 12, and the fit never zooms in past level 16; with no data and no `bounds` the whole world is shown. Later changes to `bounds` or data do not re-fit.
- `minZoom`, `maxZoom` and the `zoom` passed to `onViewportChange` are the pan/zoom scale factor (1 = the fitted initial view), not slippy-map zoom levels. `center` is the map point under the middle of the view. The tile `z` sent to `tileUrl` is the integer slippy-map level nearest the zoom on screen, clamped to 0–28.
- A string `tileUrl` substitutes the first `{x}`, `{y}` and `{z}`. There is no default tile server; without `tileUrl` a grid pattern renders.
- Pin popovers open only from a click on a pin. Setting `selectedPinId` from outside highlights the pin but shows no popover. Escape closes the popover and calls `onSelectPin(null)`; clicking the map background does not deselect.
- The popover shows `label`, `timestamp` and `detail`, and traps focus while open.
- The map is focusable (`role="application"`): `+`/`-` zoom in or out by a factor of 1.2 about the view centre, arrow keys pan 20px. Wheel and pinch zoom anchor on the pointer. Passing `onKeyDown` or `onPointerDown` through the spread replaces the built-in keyboard and drag handling.
- `children` are not rendered; overlay your own controls from a positioned parent instead.
- The track line is always cyan. The heatmap draws 8–12px circles, alpha 0.12–1 by value, with a "Density" legend; the track mode shows a "Track" legend.
