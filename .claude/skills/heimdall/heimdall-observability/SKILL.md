---
name: heimdall-observability
description: Heimdall component guide for Observability: TraceViewer, LogStream, DiffViewer, HashSetDiff, SideBySideDiff, VersionTimeline, LineageRail — workflow and run-history views (traces, logs, diffs, version history, lineage), plus the fromOTLP / fromXRay trace adapters and trace-model helpers
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## TraceViewer

Distributed-trace waterfall: span tree, service-colored timeline with parent-to-child connectors, summary strip, toolbar, and a fly-out span detail panel. Accepts raw OTLP/JSON or AWS X-Ray documents directly, or a normalized `Trace`.

```tsx
import { TraceViewer, fromOTLP, fromXRay, type Trace } from '@tinkermonkey/heimdall-ui'
```

The common path: take an OTLP export or X-Ray segment(s), convert with the adapter (or let the component do it via `otlp` / `xray`), and render.

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `trace` | `Trace` | `{ spans: [] }` | Normalized trace. Provide one of `trace` / `otlp` / `xray` |
| `otlp` | `OtlpTracesData` | — | Raw OTLP/JSON, adapted with `fromOTLP` |
| `xray` | `XRaySegment \| XRaySegment[] \| unknown` | — | Raw X-Ray document(s), adapted with `fromXRay` |
| `selectedSpanId` | `string \| null` | — | Controlled selected span. `null` closes the panel |
| `defaultSelectedSpanId` | `string \| null` | `null` | Initial selection (uncontrolled) |
| `onSelectSpan` | `(id: string \| null) => void` | — | Selection changed |
| `collapsedSpanIds` | `string[]` | — | Controlled collapsed subtrees |
| `defaultCollapsedSpanIds` | `string[]` | — | Initially collapsed subtrees (uncontrolled) |
| `onToggleSpan` | `(id: string, collapsed: boolean) => void` | — | Twisty toggled; `collapsed` is the new state |
| `showSummary` | `boolean` | `true` | Duration / spans / services / errors strip |
| `showToolbar` | `boolean` | `true` | Expand, error-jump, and zoom toolbar |
| `showDetailPanel` | `boolean` | `true` | Fly-out panel for the selected span |
| `treeWidth` | `number` | `336` | Span tree column width (px) |
| `detailPanelWidth` | `number` | `360` | Detail panel width (px) |
| `rowHeight` | `number` | `30` | Row height (px) |
| `services` | `Record<string, ServiceInfo>` | — | Merged over `trace.services`; prop wins |
| `serviceColor` | `(service: string) => string \| undefined` | — | Color override; `undefined` falls through |
| `deriveStatus` | `(span: TraceSpan) => SpanStatus` | — | Recompute each span's status, e.g. derive `'warn'` |
| `renderAttributes` | `(span: TraceSpan) => React.ReactNode` | — | Replaces the detail panel attributes section |
| `enableZoom` | `boolean` | `true` | Brush-to-zoom on the time axis |
| `virtualizeThreshold` | `number` | `80` | Virtualize at or above this many visible rows |
| `...divProps` | | | Remaining props spread onto the root `<div>` (`onSelect` is omitted) |

### Data types

`Trace` is the contract every input normalizes into. Times are milliseconds; `start` is an offset from the earliest span.

```ts
interface Trace {
  spans: TraceSpan[]
  services?: Record<string, ServiceInfo> // keyed by TraceSpan.service
  meta?: TraceMeta                      // { traceId, name?, rootService?, startedAt?, sampler?, collector? }
}

interface TraceSpan {
  id: string
  parentId: string | null               // null = root
  name: string
  service: string                       // key into services
  kind: SpanKind                        // 'INTERNAL' | 'SERVER' | 'CLIENT' | 'PRODUCER' | 'CONSUMER' | 'UNSPECIFIED'
  start: number                         // ms offset from trace start
  duration: number                      // ms
  status: SpanStatus                    // 'ok' | 'warn' | 'error'
  statusCode?: number | string          // HTTP / gRPC code, shown in the detail panel
  attributes?: Record<string, string | number | boolean>
  exception?: { type?: string; message?: string; stacktrace?: string }
  events?: SpanEvent[]                  // { time, name, attributes? }
}

interface ServiceInfo {
  label?: string                        // display name; falls back to the service key
  color?: string                        // CSS color; falls back to a palette color
  host?: string                         // shown as `host` in the detail panel
  kind?: string                         // accepted but not rendered
}
```

The viewer reads only `meta.traceId` (shown as `trace_id` in the detail panel); the other `TraceMeta` fields are carried for the consumer.

### Usage

```tsx
// Minimal: raw OTLP/JSON straight from a collector export.
// The parent must have a height.
<div style={{ height: 520 }}>
  <TraceViewer otlp={otlpExport} />
</div>
```

```tsx
// Adapt once, refine status, control selection, and override service display.
const deriveStatus = (s: TraceSpan): SpanStatus =>
  Number(s.statusCode) >= 400 && Number(s.statusCode) < 500 ? 'warn' : s.status

function TraceView({ otlpExport }: { otlpExport: OtlpTracesData }) {
  const trace = useMemo(() => fromOTLP(otlpExport), [otlpExport])
  const [selected, setSelected] = useState<string | null>(null)

  return (
    <div style={{ height: 640 }}>
      <TraceViewer
        trace={trace}
        deriveStatus={deriveStatus}
        selectedSpanId={selected}
        onSelectSpan={setSelected}
        services={{
          svc_ingest: { label: 'ingest', color: '#22D3EE', host: 'ingest-0' },
          svc_query: { label: 'query' },
        }}
        defaultCollapsedSpanIds={['a1b2c3d4e5f60718']}
        renderAttributes={(span) => <pre>{JSON.stringify(span.attributes, null, 2)}</pre>}
      />
    </div>
  )
}
```

```tsx
// AWS X-Ray: a segment, an array of segments, or a BatchGetTraces response
<div style={{ height: 520 }}>
  <TraceViewer xray={xraySegments} showSummary={false} />
</div>
```

### Gotchas

- When more than one input is set, `otlp` wins over `xray`, which wins over `trace`.
- The root is `height: 100%` with `min-width: 820px`. Give the parent an explicit height; in narrower containers it overflows horizontally.
- Adaptation and the span model rebuild whenever `trace`, `otlp`, `xray`, or `deriveStatus` change identity. Define `deriveStatus` outside the component (or with `useCallback`) and memoize adapted traces.
- OTLP and X-Ray have no warn status: every adapted span is `'ok'` or `'error'` until `deriveStatus` maps some to `'warn'`.
- Spans whose `parentId` points at a missing span render as extra roots. An empty `spans` array renders "No spans in this trace."
- A `selectedSpanId` that is not in the trace is treated as no selection.
- With `collapsedSpanIds` controlled, the toolbar expand-all / collapse-all buttons do nothing, and keyboard or error navigation does not auto-expand collapsed ancestors. Update `collapsedSpanIds` in `onToggleSpan`.
- Keyboard (span tree focused): Up/Down move selection, Right expands or steps into the first child, Left collapses or steps to the parent, Home/End jump to the ends, Escape clears selection. Escape inside the detail panel closes it and refocuses the row.
- Zoom: drag across the time axis to zoom, double-click the axis or use the toolbar button to reset. The zoom window is internal state and is not reset when the trace changes; remount with a new `key` to reset it.
- Service color precedence: `serviceColor(service)`, then `services[service].color`, then a deterministic color from `DEFAULT_SERVICE_PALETTE`.
- The detail panel shows the exception block only when `status === 'error'` and `exception` is set.

## Trace adapters

Pure functions that convert vendor trace formats into a `Trace`. The `otlp` / `xray` props call them internally; call them yourself to adapt once, inspect spans, or pass adapter options.

```ts
fromOTLP(payload: OtlpTracesData | OtlpResourceSpans[], opts?: FromOtlpOptions): Trace
fromXRay(input: XRaySegment | XRaySegment[] | unknown, opts?: FromXRayOptions): Trace
```

| Option | Adapter | Default | Description |
| ------ | ------- | ------- | ----------- |
| `serviceNameKey` | `fromOTLP` | `'service.name'` | Resource attribute holding the service name |
| `deriveStatus` | both | — | `(span: TraceSpan) => SpanStatus`, applied per span |

`fromOTLP`:
- Accepts an `ExportTraceServiceRequest` (`{ resourceSpans }`) or a bare `resourceSpans[]`. Reads `scopeSpans` and the legacy `instrumentationLibrarySpans`.
- Ids may be hex or base64 and are normalized to lowercase hex. All-zero parent ids become `null`.
- `*UnixNano` strings are parsed with `BigInt`; enums may be integers or `SPAN_KIND_*` / `STATUS_CODE_*` names.
- Status code `2` / `STATUS_CODE_ERROR` becomes `'error'`; everything else `'ok'`. The first `exception` event fills `exception`.
- `statusCode` comes from `http.response.status_code`, `http.status_code`, or `rpc.grpc.status_code`. `services[key].host` comes from `host.name` or `service.instance.id`. A resource without a service name maps to `unknown_service`.

`fromXRay`:
- Accepts one segment document, an array, or a `BatchGetTraces` response (`{ Traces: [{ Segments: [{ Document }] }] }`) whose `Document` may be a JSON string. A response with several traces uses only the first and logs a console warning.
- Epoch-second `start_time` / `end_time` become ms offsets; `in_progress` subsegments without `end_time` run to the trace end. Subsegments are walked recursively.
- The segment `name` is the service. Root segments are `SERVER`, `aws` / `remote` namespaces are `CLIENT`, the rest `INTERNAL`.
- `fault`, `error`, or `throttle` becomes `'error'`; `cause.exceptions[0]` fills `exception` with a synthesized stack trace. `http`, `sql`, `aws`, `annotations`, and `metadata` are flattened into OTel-style attribute keys.

```tsx
const trace: Trace = fromOTLP(otlpExport, { serviceNameKey: 'service.name' })
const xrayTrace: Trace = fromXRay(batchGetTracesResponse, {
  deriveStatus: (s) => (s.statusCode === 429 ? 'warn' : s.status),
})

<TraceViewer trace={trace} />
```

Input types are exported for typing raw payloads: `OtlpTracesData`, `OtlpResourceSpans`, `OtlpSpan`, `OtlpEvent`, `OtlpKeyValue`, `OtlpAnyValue`, `FromOtlpOptions`, `XRaySegment`, `XRaySubsegment`, `XRayException`, `XRayCause`, `FromXRayOptions`.

## Trace model helpers

Secondary exports for building custom trace views (sidebars, mini waterfalls, summaries) on the same model `TraceViewer` uses. Not needed for the common path.

| Export | Signature | Description |
| ------ | --------- | ----------- |
| `buildTraceModel` | `(spans: TraceSpan[]) => TraceModel` | Links parents, sorts siblings by start, returns `{ byId, ordered, roots, total, maxDepth }` |
| `selfTime` | `(span: TraceModelNode) => number` | Duration minus time covered by direct children (ms) |
| `visibleRows` | `(ordered: TraceModelNode[], collapsed: Set<string>) => TraceModelNode[]` | Preorder rows with collapsed subtrees hidden |
| `createTimeScale` | `(t0: number, t1: number, pad?: number) => TimeScale` | Linear ms-to-percent scale `{ x, w }`; `pad` defaults to 2 (%) |
| `niceTicks` | `(t0: number, t1: number) => { ticks: number[]; step: number }` | About 8 axis ticks on 1/2/5 steps |
| `fmtTraceMs` | `(ms: number \| null \| undefined) => string` | `'1.25 s'`, `'42 ms'`, `'3.4 ms'`, `'0.25 ms'`; `'—'` for null |
| `resolveServiceColor` | `(service, services?, serviceColor?, palette?) => string` | Callback, then `services[key].color`, then palette |
| `resolveServiceLabel` | `(service, services?) => string` | `services[key].label` or the raw key |
| `paletteColor` | `(service: string, palette?: readonly string[]) => string` | Deterministic hash of the key into the palette |
| `DEFAULT_SERVICE_PALETTE` | `readonly string[]` | Ten service hues; rose is excluded (reserved for errors) |

`TraceModelNode` is a `TraceSpan` plus `end`, `depth`, `children`, and `hasChildren`. `fmtTraceMs` is the package export name of the internal `fmtMs`.

```tsx
const model = buildTraceModel(trace.spans)
const scale = createTimeScale(0, model.total)
const rows = visibleRows(model.ordered, new Set<string>())

<ul>
  {rows.map((s) => (
    <li key={s.id} style={{ paddingLeft: s.depth * 12 }}>
      <span style={{ color: resolveServiceColor(s.service, trace.services) }}>
        {resolveServiceLabel(s.service, trace.services)}
      </span>{' '}
      {s.name} · {fmtTraceMs(s.duration)} (self {fmtTraceMs(selfTime(s))}) @ {scale.x(s.start).toFixed(1)}%
    </li>
  ))}
</ul>
```

## LogStream

Monospace, auto-following log tail with timestamp and level columns, and optional operation / target columns.

```tsx
import { LogStream, type LogEntry } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `entries` | `LogEntry[]` | required | Log lines, oldest first |
| `follow` | `boolean` | `true` | Auto-scroll to new entries |
| `maxRows` | `number` | `500` | Render only the last N entries |
| `showOps` | `boolean` | `false` | Show `op` and `target` columns |
| `aria-label` | `string` | `'Log stream'` | Accessible name of the `role="log"` region |
| `...divProps` | | | Remaining props spread onto the root `<div>` (the scroll container) |

### Data types

```ts
interface LogEntry {
  id?: string                                  // stable React key; strongly recommended
  timestamp: Date | string                     // rendered as local HH:MM:SS
  level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG'
  message: string
  op?: string                                  // shown when showOps
  target?: string                              // shown when showOps
}
```

### Usage

```tsx
<div style={{ height: 320 }}>
  <LogStream entries={entries} />
</div>
```

```tsx
const opsEntries: LogEntry[] = [
  { id: 'log_001', timestamp: '2026-06-05T14:30:15Z', level: 'INFO', op: 'upsert', target: 'cls_organism', message: 'Wrote 47 individuals' },
  { id: 'log_002', timestamp: '2026-06-05T14:30:16Z', level: 'WARN', op: 'link', target: 'rel_parent_of', message: '3 targets unresolved' },
  { id: 'log_003', timestamp: '2026-06-05T14:30:18Z', level: 'ERROR', op: 'delete', target: 'cls_legacy', message: 'Constraint violation' },
]

<div style={{ height: 400 }}>
  <LogStream entries={opsEntries} showOps maxRows={1000} follow={false} aria-label="svc_ingest logs" />
</div>
```

### Gotchas

- The root is the scroll container with `height: 100%`; give the parent a height or it grows with its content and never scrolls.
- Following pauses when the user scrolls more than 50px above the bottom and resumes when the bottom comes back into view. `follow={false}` disables auto-scroll entirely.
- `maxRows` drops the oldest entries from the render, not from your array. Trim the source array yourself for long-running streams.
- Without `id`, the key is built from timestamp, level, message, op, and target. Two identical lines then share a key; always set `id` for live streams.
- `level` must be one of the four uppercase strings. Timestamps show time only (no date, no milliseconds); an unparsable string renders blank.
- `aria-live="polite"` is set only while following.
- With no entries it renders "No log entries".

## DiffViewer

Tabbed diff panel that switches between a set diff (`DiffViewer.HashSet`, added / removed / kept items) and a line diff (`DiffViewer.SideBySide`). `mode` selects which child renders.

```tsx
import {
  DiffViewer,
  type DiffViewerMode,
  type DiffViewerHashSetProps,
  type DiffViewerSideBySideProps,
} from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `mode` | `DiffViewerMode` (`'hash-set' \| 'side-by-side'`) | `'hash-set'` | Active tab; resyncs internal state when changed |
| `onModeChange` | `(mode: DiffViewerMode) => void` | — | Tab clicked |
| `children` | `ReactNode` | — | `DiffViewer.HashSet` and/or `DiffViewer.SideBySide` |
| `...divProps` | | | Remaining props spread onto the root `<div role="region">` (overrides its `aria-label="Diff Viewer"`) |

### Modes

`DiffViewerMode` is a two-way switch. Each subcomponent reads the mode from context and renders only in its own mode:

| `mode` | Renders | Props type | Wraps |
| ------ | ------- | ---------- | ----- |
| `'hash-set'` | `DiffViewer.HashSet` | `DiffViewerHashSetProps` | `HashSetDiff` plus a label pill |
| `'side-by-side'` | `DiffViewer.SideBySide` | `DiffViewerSideBySideProps` | `SideBySideDiff` plus label pills |

Include both children to make both tabs useful; a tab without its matching child shows an empty panel. `children` is typed as `ReactNode`, so the pairing is not type-checked.

### Usage

```tsx
<DiffViewer>
  <DiffViewer.HashSet added={['schema.version']} removed={['old_field']} kept={['name', 'owner']} />
</DiffViewer>
```

```tsx
const [mode, setMode] = useState<DiffViewerMode>('hash-set')

<DiffViewer mode={mode} onModeChange={setMode}>
  <DiffViewer.HashSet
    added={['metadata.author', 'config.debug']}
    removed={['deprecated_key']}
    kept={keptFields}
    maxVisible={8}
    label="Schema changes"
    labelTone="amber"
  />
  <DiffViewer.SideBySide
    lines={[
      { type: 'hunk', content: '@@ -1,4 +1,4 @@' },
      { type: 'context', content: 'export interface User {' },
      { type: 'removed', content: '  email: string' },
      { type: 'added', content: '  email_address: string' },
      { type: 'context', content: '}' },
    ]}
    addedLabel="v2"
    removedLabel="v1"
  />
</DiffViewer>
```

### Compound subcomponents

#### DiffViewer.HashSet

Renders `HashSetDiff` under a label pill, only when `mode === 'hash-set'`.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `added` | `string[]` | `[]` | Items only in the new version |
| `removed` | `string[]` | `[]` | Items only in the old version |
| `kept` | `string[]` | `[]` | Items in both |
| `maxVisible` | `number` | `10` | Kept items shown before the expand row |
| `label` | `string` | `'Changes'` | Pill above the diff; `''` hides it |
| `labelTone` | `VersionPillTone` (`'amber' \| 'emerald' \| 'rose'`) | `'amber'` | Pill tone |
| `className` | `string` | `''` | Class on the wrapper `<div>` |
| `...divProps` | | | Remaining props spread onto the wrapper `<div>` |

#### DiffViewer.SideBySide

Renders `SideBySideDiff` under a row of label pills, only when `mode === 'side-by-side'`.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `lines` | `DiffLine[]` | `[]` | Diff lines in display order |
| `addedLabel` | `string` | `'Version 2 (Added)'` | Emerald pill; `''` hides it |
| `removedLabel` | `string` | `'Version 1 (Removed)'` | Rose pill; `''` hides it |
| `addedLabelTone` | `VersionPillTone` | `'emerald'` | Added pill tone |
| `removedLabelTone` | `VersionPillTone` | `'rose'` | Removed pill tone |
| `className` | `string` | `''` | Class on the wrapper `<div>` |
| `...divProps` | | | Remaining props spread onto the wrapper `<div>` |

### Gotchas

- `mode` is semi-controlled: tab clicks switch the view even if you ignore `onModeChange`, and a new `mode` value overrides the internal state. Passing the same value again does not reset a user's tab choice.
- Subcomponents read the mode from context and return `null` outside a `DiffViewer`. Use `HashSetDiff` / `SideBySideDiff` directly for standalone diffs.
- Tab and panel elements use fixed DOM ids (`diff-viewer-hash-set-tab`, …), so two `DiffViewer`s on one page produce duplicate ids.
- Left/Right/Home/End move focus between tabs without activating them; Enter or Space activates.
- `DiffViewer.SideBySide` labels are added above `SideBySideDiff`, which always renders its own fixed "Version 2 (Added)" / "Version 1 (Removed)" header, so two rows of pills appear. Set both labels to `''` to keep only the inner header.

## HashSetDiff

Three-column set diff (Added / Removed / Kept, with counts) for comparing two versions of a set of identifiers. Standalone version of `DiffViewer.HashSet` without the label pill.

```tsx
import { HashSetDiff } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `added` | `string[]` | `[]` | Items only in the new version |
| `removed` | `string[]` | `[]` | Items only in the old version |
| `kept` | `string[]` | `[]` | Items in both |
| `maxVisible` | `number` | `10` | Kept items shown before the expand row |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<HashSetDiff added={['cls_organism']} removed={['cls_legacy']} />
```

```tsx
<HashSetDiff
  added={['schema.version', 'metadata.author', 'metadata.created']}
  removed={['old_field', 'deprecated_key']}
  kept={['name', 'description', 'type', 'status', 'owner', 'tags', 'permissions']}
  maxVisible={5}
/>
```

### Gotchas

- The component does not compute the diff; pass the three lists already split.
- Columns are aligned by index only. Row N shows `added[N]`, `removed[N]`, and `kept[N]` side by side; they are unrelated items.
- Kept items beyond `maxVisible` collapse into a "… N more carried forward" button. Expanding is one-way; there is no collapse control.
- The body is virtualized at 28px rows and scrolls between 200px and 400px tall.
- All three lists empty renders "No changes between these versions".

## SideBySideDiff

Virtualized line diff with +/− gutter markers, tinted added and removed rows, and full-width hunk headers. Lines render in one column in the order given (a unified diff), under a fixed "Version 2 (Added)" / "Version 1 (Removed)" header.

```tsx
import { SideBySideDiff, type DiffLine } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `lines` | `DiffLine[]` | `[]` | Diff lines in display order |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

```ts
type DiffLineType = 'context' | 'added' | 'removed' | 'hunk'

interface DiffLine {
  type: DiffLineType
  content: string
  lineNumber?: number   // accepted but not rendered
}
```

### Usage

```tsx
<SideBySideDiff lines={[{ type: 'added', content: 'retries: 3' }]} />
```

```tsx
const lines: DiffLine[] = [
  { type: 'hunk', content: '@@ -24,5 +25,8 @@' },
  { type: 'context', content: 'export interface User {' },
  { type: 'removed', content: '  is_active: boolean' },
  { type: 'added', content: "  status: 'active' | 'inactive'" },
  { type: 'context', content: '}' },
]

<SideBySideDiff lines={lines} />
```

### Gotchas

- Despite the name there are no left/right panes. Interleave `removed` and `added` lines yourself, as in a unified diff.
- The header pills are hard-coded and cannot be relabeled. Use `DiffViewer.SideBySide` for custom labels.
- Rows are a fixed 24px for virtualization; the body scrolls between 200px and 500px tall.
- `lineNumber` is not displayed.
- An empty `lines` array renders "No changes between these versions".

## VersionTimeline

Vertical, selectable version history: amber version pill, optional headline, diff stats or a state transition, and a relative timestamp per entry, with a filled dot and `head` chip on the current version.

```tsx
import { VersionTimeline, type VersionEntry } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `entries` | `VersionEntry[]` | required | Versions, newest first |
| `selectedId` | `string` | — | Selected entry id (controlled) |
| `onSelect` | `(id: string) => void` | — | Entry clicked or arrow-key navigated |
| `order` | `'newest-first' \| 'oldest-first'` | `'newest-first'` | `'oldest-first'` reverses `entries` |
| `emptyState` | `string` | `'No versions available'` | Text when `entries` is empty |
| `...divProps` | | | Remaining props spread onto the root `<div>` (native `onSelect` is omitted) |

### Data types

```ts
interface VersionEntry {
  id: string
  label: string                                         // shown in the version pill
  headline?: string
  timestamp: Date | string
  head?: boolean                                        // filled dot + `head` chip
  stats?: DiffStats                                     // { added?, removed?, kept? }
  transition?: StateTransition                          // { from, to }; replaces stats
}
```

### Usage

```tsx
<VersionTimeline entries={versions} />
```

```tsx
const versions: VersionEntry[] = [
  { id: 'v3.2.1', label: 'v3.2.1', headline: 'Bug fix release', timestamp: '2026-06-05T14:30:00Z', head: true, stats: { added: 2, removed: 3, kept: 145 } },
  { id: 'v3.2.0', label: 'v3.2.0', timestamp: '2026-06-01T10:15:00Z', stats: { added: 12, removed: 5 } },
  { id: 'v3.1.5', label: 'v3.1.5', timestamp: '2026-05-25T08:00:00Z', transition: { from: 'stable', to: 'deprecated' } },
]

const [selectedId, setSelectedId] = useState('v3.2.1')

<VersionTimeline entries={versions} selectedId={selectedId} onSelect={setSelectedId} order="newest-first" />
```

### Gotchas

- Fully controlled: selection only changes when you update `selectedId` from `onSelect`.
- `order` does not sort. It keeps or reverses the array as given, so supply `entries` newest first.
- Without `onSelect`, entries are not clickable and the keyboard does nothing.
- Keyboard (list focused): Up/Down select the previous/next entry in display order; with nothing selected, Down selects the first.
- `transition` takes precedence over `stats`; only stats fields that are set are shown.
- Timestamps are relative (`just now`, `5m ago`, `2h ago`, `3d ago`, then a locale date) and computed at render; they do not tick.

## LineageRail

Horizontal chain of chips joined by arrows, showing the lineage of a dataset, run, or entity. The first node is styled as the head.

```tsx
import { LineageRail, type LineageNode } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `nodes` | `LineageNode[]` | required | Chain, head first |
| `wrap` | `boolean` | `false` | Wrap onto new lines instead of scrolling |
| `aria-label` | `string` | auto | Defaults to `'Lineage: a → b → c'` from labels |
| `...divProps` | | | Remaining props spread onto the root `<div role="list">` |

### Data types

```ts
interface LineageNode {
  icon?: IconName       // any key of ICONS
  label: string
  onClick?: () => void  // makes the chip focusable and clickable
}
```

### Usage

```tsx
<LineageRail nodes={[{ label: 'src_orders' }, { label: 'stg_orders' }, { label: 'fct_revenue' }]} />
```

```tsx
<LineageRail
  wrap
  nodes={[
    { icon: 'data', label: 'raw_events', onClick: () => openNode('raw_events') },
    { icon: 'pipeline', label: 'sessionize', onClick: () => openNode('sessionize') },
    { icon: 'schema', label: 'fct_sessions' },
  ]}
/>
```

### Gotchas

- An empty `nodes` array renders nothing (no element, so a forwarded ref stays `null`).
- The first node gets head styling and `aria-current="step"`; order the array so the node to emphasize comes first.
- Without `wrap`, long chains scroll horizontally inside the rail.
- Only nodes with `onClick` are focusable; Enter and Space activate them.
