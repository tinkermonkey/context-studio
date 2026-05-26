---
name: heimdall-charts
description: Heimdall component guide for Charts: Sparkline, LineChart, BarChart, BarV, BarH, StackedBar, Donut, PieChart, Heatmap, StatusTimeline, ProgressBar, MetricRow
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

All chart components accept a `tone` prop (`'light' | 'dark'`, default `'light'`) for canvas surface matching.

The canonical 6-color series palette (in order): `#22D3EE` cyan, `#10B981` emerald, `#F59E0B` amber, `#818CF8` indigo, `#8B5CF6` violet, `#F43F5E` rose.

---

## Sparkline

88×28 shape-only trend indicator for embedding in tiles and cards. No axes or labels.

```tsx
import { Sparkline } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `data` | `number[]` | required | Min 2 data points |
| `width` | `number` | `88` | SVG width in px |
| `height` | `number` | `28` | SVG height in px |
| `color` | `StatusColor \| string` | `'emerald'` | Line color — StatusColor name or hex string |
| `area` | `boolean` | `true` | Gradient fill beneath line |
| `label` | `string` | `'trend sparkline'` | `aria-label` |

### Usage

```tsx
<Sparkline data={[12, 14, 13, 16, 19, 17, 21, 24]} />
```

```tsx
<Sparkline data={sparkData} color="#22D3EE" area width={120} height={36} />
```

### Gotchas

- Returns `null` if `data` has fewer than 2 points — no error thrown
- Accepts StatusColor names (`'emerald'`, `'amber'`, etc.) or any hex string

---

## LineChart

Multi-series line chart with optional area fill, axes, grid, threshold line, event markers, and tooltip.

```tsx
import { LineChart } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `series` | `number[][]` | required | Each array is one series |
| `colors` | `string[]` | SERIES_COLORS | Hex color per series |
| `xLabels` | `string[]` | — | X-axis tick labels |
| `width` | `number` | `480` | SVG width in px |
| `height` | `number` | `200` | SVG height in px |
| `area` | `boolean` | `false` | Gradient fill beneath lines |
| `axes` | `boolean` | `false` | Y-axis line + tick labels |
| `grid` | `boolean` | `false` | Horizontal grid lines |
| `ticks` | `number` | `4` | Y-axis tick count |
| `threshold` | `{ value: number; label?: string }` | — | Horizontal reference line |
| `markers` | `{ x: number; label?: string }[]` | — | Amber vertical event markers |
| `tooltip` | `boolean` | `false` | Hover column tooltip card |
| `tone` | `'light' \| 'dark'` | `'light'` | Color theme |
| `padding` | `{ top?, right?, bottom?, left? }` | — | Plot area padding overrides |

### Usage

```tsx
// Minimal
<LineChart series={[[10, 20, 15, 30, 25, 40]]} />
```

```tsx
// Full-featured
<LineChart
  series={[seriesA, seriesB]}
  colors={['#22D3EE', '#818CF8']}
  width={720}
  height={320}
  area
  axes
  grid
  ticks={5}
  xLabels={xLabels}
  threshold={{ value: 40, label: 'target' }}
  markers={[{ x: 8, label: 'v1.4 release' }]}
  tooltip
  tone="light"
/>
```

### Gotchas

- When `axes={true}`, left padding increases to 30px and bottom to 22px automatically
- Threshold value expands the Y-range if it falls outside the data range
- Tooltip card flips left when it would clip the right edge

---

## BarV

Single-series vertical bar chart. Y-axis always starts at zero.

```tsx
import { BarV } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `values` | `number[]` | required | Bar heights |
| `xLabels` | `string[]` | — | X-axis labels (requires `axes={true}`) |
| `color` | `string` | amber (`SERIES_COLORS[2]`) | Bar fill color |
| `width` | `number` | `480` | SVG width |
| `height` | `number` | `200` | SVG height |
| `axes` | `boolean` | `false` | Show axes |
| `grid` | `boolean` | `false` | Horizontal grid lines |
| `ticks` | `number` | `4` | Y-axis tick count |
| `threshold` | `{ value: number; label?: string }` | — | Reference line |
| `tone` | `'light' \| 'dark'` | `'light'` | Color theme |

### Usage

```tsx
<BarV values={[82, 64, 91, 47, 73, 88]} />
```

```tsx
<BarV
  values={[82, 64, 91, 47, 73, 88, 56, 79, 95, 68, 72, 84]}
  xLabels={['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']}
  color="#10B981"
  width={480}
  height={200}
  axes
  grid
  threshold={{ value: 80, label: 'sla' }}
/>
```

---

## BarH

Horizontal bar chart for ranked categories. Shows an inset track with a filled bar per item.

```tsx
import { BarH } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `items` | `BarHItem[]` | required | Bars to render |
| `width` | `number` | `320` | SVG width |
| `height` | `number` | `200` | SVG height |
| `tone` | `'light' \| 'dark'` | `'light'` | Color theme |
| `showValues` | `boolean` | `true` | Label at right of bar |
| `valueFormat` | `(value: number) => string` | `fmt()` | Custom value formatter |
| `maxValue` | `number` | max of items | Fixed scale maximum |

```ts
interface BarHItem {
  label: string
  value: number
  color?: string  // optional per-item override
}
```

### Usage

```tsx
<BarH
  items={[
    { label: 'nyx-01', value: 92, color: '#22D3EE' },
    { label: 'aether-02', value: 78, color: '#818CF8' },
    { label: 'vega-03', value: 64, color: '#F59E0B' },
  ]}
  width={320}
  height={140}
  valueFormat={v => `${v.toFixed(1)} ms`}
/>
```

---

## StackedBar

Multi-segment stacked bar chart with optional normalized (100%) mode.

```tsx
import { StackedBar } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `stacks` | `StackedBarStack[]` | required | Array of stacks |
| `colors` | `string[]` | SERIES_COLORS | Hex color per segment part |
| `width` | `number` | `480` | SVG width |
| `height` | `number` | `200` | SVG height |
| `axes` | `boolean` | `false` | Show axes |
| `grid` | `boolean` | `false` | Grid lines |
| `ticks` | `number` | `4` | Y-axis tick count |
| `normalized` | `boolean` | `false` | 100% stacked mode |
| `tone` | `'light' \| 'dark'` | `'light'` | Color theme |

```ts
interface StackedBarStack {
  label: string
  parts: number[]  // 1–4 values per stack
}
```

### Usage

```tsx
<StackedBar
  stacks={[
    { label: 'Mon', parts: [42, 28, 14, 8] },
    { label: 'Tue', parts: [48, 31, 12, 11] },
    { label: 'Wed', parts: [38, 26, 18, 9] },
  ]}
  axes
  grid
/>
```

```tsx
// Normalized (percentage) mode
<StackedBar stacks={stacks} normalized axes ticks={4} />
```

### Gotchas

- When `normalized={true}`, Y-axis shows percentages (0%–100%) not raw values

---

## Donut

Ring chart showing composition. Optional center value and label. No built-in legend.

```tsx
import { Donut } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `slices` | `DonutSlice[]` | required | 1–5 slices (merge 6th+ into "other") |
| `colors` | `string[]` | SERIES_COLORS | Hex per slice |
| `width` | `number` | `160` | SVG width |
| `height` | `number` | `160` | SVG height |
| `thickness` | `number` | `14` | Ring width in px |
| `gap` | `number` | `0.03` | Gap between slices in radians |
| `centerValue` | `string` | — | Bold number in center |
| `centerLabel` | `string` | — | Monospace eyebrow below center value |
| `tone` | `'light' \| 'dark'` | `'light'` | Color theme |

```ts
interface DonutSlice {
  value: number
  color?: string
}
```

### Usage

```tsx
<Donut
  slices={[
    { value: 134, color: '#10B981' },
    { value: 72, color: '#818CF8' },
    { value: 45, color: '#22D3EE' },
  ]}
  centerValue="267"
  centerLabel="ind."
/>
```

### Gotchas

- No built-in legend — compose one yourself alongside the chart
- Merge more than 5 slices into an "other" slice before passing to avoid visual clutter

---

## PieChart

Solid-wedge pie chart with optional legend.

```tsx
import { PieChart } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `segments` | `PieChartSegment[]` | required | Slices to render |
| `legend` | `boolean` | `false` | Show legend below chart |
| `width` | `number` | `200` | SVG width |
| `height` | `number` | `200` | SVG height |
| `tone` | `'light' \| 'dark'` | `'light'` | Color theme |

```ts
interface PieChartSegment {
  name: string
  value: number
  color?: string
}
```

### Usage

```tsx
<PieChart
  segments={[
    { name: 'CPU Bound', value: 35 },
    { name: 'I/O Wait', value: 25 },
    { name: 'Memory', value: 20 },
    { name: 'Network', value: 20 },
  ]}
  legend
  width={240}
  height={240}
/>
```

### Gotchas

- Zero and negative segment values are filtered out automatically
- Renders as a `<div>` wrapping an SVG (not a forwardRef to SVG directly)

---

## Heatmap

2D density grid with single-hue alpha scale. Used for calendars and host/metric matrices.

```tsx
import { Heatmap } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `data` | `(number \| null)[][]` | required | 2D array `[rows][cols]` |
| `baseColor` | `string` | `'#10B981'` | Hex color for highest-density cells |
| `xLabels` | `string[]` | — | Column labels (requires `axes={true}`) |
| `yLabels` | `string[]` | — | Row labels (requires `axes={true}`) |
| `width` | `number` | `480` | SVG width |
| `height` | `number` | `120` | SVG height |
| `axes` | `boolean` | `false` | Show x/y labels |
| `tone` | `'light' \| 'dark'` | `'light'` | Color theme |

### Usage

```tsx
<Heatmap
  data={data}  // 7 rows × 24 cols
  baseColor="#10B981"
  width={320}
  height={110}
  axes
  yLabels={['M','T','W','T','F','S','S']}
  xLabels={['0h','','','','','','6h','','','','','','12h','','','','','','18h','','','','','23h']}
/>
```

### Gotchas

- `null` cells render as the inset/empty background color — use `null` for missing data, not `0`
- Alpha scale: 12% opacity at minimum value → 100% at maximum

---

## StatusTimeline

Gantt-style status history for N services across a time window.

```tsx
import { StatusTimeline } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `tracks` | `StatusTrack[]` | required | One track per service |
| `range` | `[number, number]` | `[0, 100]` | Time range (relative units) |
| `width` | `number` | `480` | SVG width |
| `height` | `number` | `160` | SVG height |
| `axes` | `boolean` | `false` | Show x-axis labels |
| `xLabels` | `string[]` | — | X-axis time labels |
| `marker` | `{ x: number; label?: string }` | — | Amber event marker line |
| `tone` | `'light' \| 'dark'` | `'light'` | Color theme |

```ts
interface StatusTrack {
  label: string
  segments: StatusSegment[]
}
interface StatusSegment {
  start: number    // range-relative position
  end: number
  kind: 'ok' | 'warn' | 'error' | 'idle' | 'info' | string  // or custom hex
}
```

### Usage

```tsx
<StatusTimeline
  tracks={[
    {
      label: 'graph daemon',
      segments: [
        { start: 0, end: 22, kind: 'ok' },
        { start: 22, end: 28, kind: 'warn' },
        { start: 28, end: 64, kind: 'ok' },
        { start: 64, end: 68, kind: 'error' },
        { start: 68, end: 100, kind: 'ok' },
      ],
    },
  ]}
  width={480}
  height={100}
  range={[0, 100]}
  axes
  xLabels={['-24h', '-18h', '-12h', '-6h', 'now']}
  marker={{ x: 64, label: 'incident #142' }}
/>
```

### Gotchas

- Segment `start`/`end` values are relative to `range`, not pixel positions
- Gaps between segments show the inset background color automatically
- Minimum rendered segment width is 2px regardless of its time span

---

## ProgressBar

Horizontal fill bar for simple progress or usage indicators.

```tsx
import { ProgressBar } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `percent` | `number` | required | 0–100 fill value |
| `color` | `'emerald' \| 'amber' \| 'rose' \| 'cyan' \| 'violet' \| 'neutral'` | `'emerald'` | Fill color |
| `height` | `number` | `6` | Bar height in px |
| `label` | `string` | — | `aria-label` |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
<ProgressBar percent={72} color="amber" label="CPU usage" />
```

```tsx
<ProgressBar percent={percent} color={percent > 90 ? 'rose' : 'emerald'} height={8} />
```

### Gotchas

- `percent` is clamped to `[0, 100]`; NaN is treated as 0

---

## MetricRow

Composite row combining a label, progress bar, inline sparkline, and value. For live metrics dashboards.

```tsx
import { MetricRow } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `label` | `string` | required | Row label |
| `value` | `number \| string` | required | Primary metric display value |
| `unit` | `string` | — | Suffix after value (e.g. `'%'`, `'MB'`) |
| `percent` | `number` | required | Progress bar fill 0–100 |
| `sparklineData` | `number[]` | `[]` | Data for 60×18 inline sparkline |
| `color` | `StatusColor` | `'emerald'` | Color for progress bar and sparkline |
| `progressLabel` | `string` | `label` | `aria-label` for progress bar |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
<MetricRow
  label="CPU Usage"
  value={72}
  unit="%"
  percent={72}
  sparklineData={[45, 52, 48, 65, 72, 68, 75, 70, 72, 68]}
  color="amber"
/>
```

```tsx
// Multiple metrics in a list
{metrics.map(m => (
  <MetricRow
    key={m.label}
    label={m.label}
    value={m.value}
    unit={m.unit}
    percent={m.percent}
    sparklineData={m.history}
    color={m.percent > 90 ? 'rose' : 'emerald'}
  />
))}
```
