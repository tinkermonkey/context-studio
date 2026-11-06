---
name: heimdall-charts
description: Heimdall component guide for Charts: ChartWrapper, Sparkline, LineChart, BarChart, BarV, BarH, StackedBar, Donut, Heatmap, StatusTimeline, ProgressBar, MetricRow
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## Shared chart conventions

These apply across the chart components below.

- **Fixed pixel size.** Every SVG chart renders at its `width` × `height` in pixels (default sizes differ per chart). Charts do not measure their container; to fill a responsive slot, measure the container (e.g. `ResizeObserver`) and pass the numbers in.
- **`tone`** (`'light' | 'dark'`, default `'light'`) picks text, grid, border and inset colors for the canvas the chart sits on. It does not follow the `dark-canvas` body class; pass `tone="dark"` yourself on a dark canvas. Accepted by `LineChart`, `BarChart`, `BarV`, `BarH`, `StackedBar`, `Donut`, `Heatmap` and `StatusTimeline`. `Sparkline`, `ProgressBar`, `MetricRow` and `ChartWrapper` have no `tone`.
- **Series palette.** Charts that take `colors?: string[]` default to the internal 6-color series palette, in order: `#22D3EE` cyan, `#10B981` emerald, `#F59E0B` amber, `#818CF8` indigo, `#8B5CF6` violet, `#F43F5E` rose. The palette is not exported; pass `colors` (hex strings) to override. Colors cycle when there are more series than colors.
- **Empty data.** Most SVG charts return `null` on empty input (no placeholder). `BarChart` is the exception and renders a "No data" box.
- **`style` merging.** SVG charts merge your `style` over `{ display: 'block' }`. `ChartWrapper`, `BarChart` and `ProgressBar` instead replace their root inline style with yours (see each section).

### StatusColor

`StatusColor` is the shared semantic color name used by `Sparkline`, `BarChart` series, `ProgressBar` and `MetricRow`. `SparklineColor` and `ProgressBarColor` are aliases of it.

```ts
import type { StatusColor } from '@tinkermonkey/heimdall-ui'

type StatusColor = 'emerald' | 'amber' | 'rose' | 'cyan' | 'violet' | 'neutral'
```

Meaning follows the design system: emerald = ok/running, rose = error/failed, cyan = updating, amber = warning/accent, violet = secondary, neutral = stopped/idle (`neutral` resolves to the canvas `fg-2` token, so it adapts to the canvas mode). Only `Sparkline` also accepts a raw CSS color string; the others accept the names only.

---

## ChartWrapper

Accessible `<svg>` container (`role="img"` plus `aria-label`) for hand-drawn custom charts.

```tsx
import { ChartWrapper } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `label` | `string` | required | Becomes the SVG `aria-label` |
| `children` | `React.ReactNode` | required | SVG content (paths, groups, text) |
| `width` | `number \| string` | — | SVG `width` attribute |
| `height` | `number \| string` | — | SVG `height` attribute |
| `viewBox` | `string` | — | SVG `viewBox`, e.g. `'0 0 320 120'` |
| `className` | `string` | `''` | Class on the `<svg>` |
| `...svgProps` | | | Remaining SVG attributes spread onto the root `<svg>` |

### Usage

```tsx
<ChartWrapper label="Ingest rate" width={320} height={120} viewBox="0 0 320 120">
  <line x1="0" y1="115" x2="320" y2="115" stroke="#E5E9EE" />
</ChartWrapper>
```

```tsx
const points = [12, 34, 28, 55, 44, 68, 61, 82, 75, 90, 85, 100]

<ChartWrapper label="Monthly active users" width="100%" height={120} viewBox="0 0 320 120" className="mau-chart">
  <line x1="0" y1="115" x2="320" y2="115" stroke="#E5E9EE" strokeWidth="1" />
  {points.map((v, i) => (
    <circle key={i} cx={(i / (points.length - 1)) * 310 + 5} cy={110 - v} r={3.5} fill="#F59E0B" />
  ))}
</ChartWrapper>
```

### Gotchas

- Children must be SVG elements; HTML inside an `<svg>` does not render.
- No `viewBox` is computed. Without one, `width="100%"` widens the element but does not scale the drawing.
- The root carries `style={{ display: 'block' }}`, but a `style` prop replaces it entirely. Include `display: 'block'` in your own `style` to keep it.
- `ref` forwards to the `<svg>`.

---

## Sparkline

Shape-only trend line (88 × 28 by default) for tiles, table cells and cards. No axes, labels or tooltip.

```tsx
import { Sparkline } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `data` | `number[]` | required | At least 2 points |
| `width` | `number` | `88` | SVG width in px |
| `height` | `number` | `28` | SVG height in px |
| `color` | `SparklineColor \| string` | `'emerald'` | `StatusColor` name or any CSS color |
| `area` | `boolean` | `true` | Gradient fill beneath the line |
| `label` | `string` | `'trend sparkline'` | SVG `aria-label` |
| `...svgProps` | | | Remaining SVG attributes spread onto the root `<svg>` |

### Usage

```tsx
<Sparkline data={[12, 14, 13, 16, 19, 17, 21, 24]} />
```

```tsx
<Sparkline
  data={[22, 24, 25, 24, 26, 28, 27, 30, 29, 31]}
  color="#22D3EE"
  area={false}
  width={120}
  height={36}
  label="svc_ingest throughput, last 10 min"
/>
```

### Gotchas

- Returns `null` when `data` has fewer than 2 points; no error, no placeholder.
- The y scale is min-to-max of the data, so small fluctuations look dramatic. A flat series draws along the bottom edge.
- `preserveAspectRatio="none"`: resizing the SVG with CSS stretches the line instead of re-plotting it. Change `width`/`height` instead.
- `color` names in `StatusColor` resolve to the status palette; any other string is used verbatim as the stroke color.

---

## LineChart

Multi-series line chart with optional area fill, axes, grid, threshold line, event markers and hover tooltip.

```tsx
import { LineChart, type ThresholdLine, type EventMarker } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `series` | `number[][]` | required | One inner array per series |
| `colors` | `string[]` | series palette | Hex per series; single series defaults to cyan |
| `xLabels` | `string[]` | — | One label per data index |
| `width` | `number` | `480` | SVG width in px |
| `height` | `number` | `200` | SVG height in px |
| `area` | `boolean` | `false` | Gradient fill beneath each line |
| `axes` | `boolean` | `false` | Axis lines, y tick labels, x labels |
| `grid` | `boolean` | `false` | Horizontal grid lines |
| `ticks` | `number` | `4` | Y intervals (draws `ticks + 1` lines) |
| `threshold` | `ThresholdLine` | — | Dashed horizontal reference line |
| `markers` | `EventMarker[]` | — | Amber vertical event markers |
| `tooltip` | `boolean` | `false` | Crosshair and hover value card |
| `tone` | `'light' \| 'dark'` | `'light'` | Canvas tone |
| `padding` | `{ top?: number; right?: number; bottom?: number; left?: number }` | auto | Merged over computed plot padding |
| `...svgProps` | | | Remaining SVG attributes (incl. `aria-label`) spread onto the root `<svg>` |

### Data types

```ts
interface ThresholdLine { value: number; label?: string }
interface EventMarker { x: number; label?: string } // x is a data index, not a pixel
```

### Usage

```tsx
<LineChart series={[[10, 20, 15, 30, 25, 40]]} />
```

```tsx
const ingest: number[] = [12, 14, 13, 16, 19, 17, 21, 24, 22, 27, 31, 28]
const query: number[] = [22, 24, 25, 24, 26, 28, 27, 30, 29, 31, 30, 33]
const weeks: string[] = ['W1', '', '', 'W4', '', '', 'W7', '', '', 'W10', '', 'W12']

<LineChart
  series={[ingest, query]}
  colors={['#22D3EE', '#818CF8']}
  xLabels={weeks}
  width={720}
  height={320}
  area
  axes
  grid
  ticks={5}
  threshold={{ value: 30, label: 'target' }}
  markers={[{ x: 8, label: 'v1.4 release' }]}
  tooltip
  aria-label="Ingest and query rate per week"
/>
```

### Gotchas

- Returns `null` when every series is empty. Do not switch the same mounted `LineChart` from empty to non-empty `series`: the component calls a hook after that early return, so React throws a hook-order error. Render your own empty state instead, or give the chart a new `key` when data arrives.
- The y range is the data min/max padded by 8% on both ends; it does not start at zero. A `threshold` outside that range extends it.
- `xLabels` render only with `axes`, positioned at each data index, so pass one entry per point (`''` skips a label). The tooltip header uses `xLabels[i]` even without `axes`, falling back to `t{i}`.
- `axes` raises left padding to 30 px and bottom to 22 px; `tooltip` raises right padding to 12 px. `padding` overrides any side.
- The tooltip card is always the dark shell popover, in both tones, and flips left near the right edge.
- `aria-label` defaults to `'Line chart'`.
- With `tooltip`, passing your own `onMouseMove` or `onMouseLeave` replaces the tooltip handlers.

---

## BarChart

Grouped multi-series vertical bar chart with built-in axes and an optional legend. Older API; for a single series prefer `BarV`, for composition `StackedBar`.

```tsx
import { BarChart, type BarChartSeries } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `series` | `BarChartSeries[]` | required | One entry per bar group member |
| `xLabels` | `string[]` | `[]` | Label under each group |
| `yMin` | `number` | `min(0, data min)` | Y-axis floor |
| `yMax` | `number` | data max | Y-axis ceiling |
| `yTickCount` | `number` | `5` | Total tick lines, ends included |
| `legend` | `boolean` | `false` | Color-keyed legend below the chart |
| `width` | `number` | `400` | SVG width in px |
| `height` | `number` | `200` | SVG height in px |
| `tone` | `'light' \| 'dark'` | `'light'` | Canvas tone |
| `ariaLabel` | `string` | series names joined | SVG `aria-label` and `<title>` |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Data types

```ts
interface BarChartSeries {
  name: string        // shown in the legend and default aria-label
  data: number[]      // one value per group
  color?: StatusColor // name only; defaults to the series palette by index
}
```

### Usage

```tsx
<BarChart
  series={[{ name: 'deployments', data: [4, 7, 3, 9, 5, 6], color: 'cyan' }]}
  xLabels={['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']}
/>
```

```tsx
<BarChart
  series={[
    { name: 'requests', data: [120, 145, 130, 170, 200], color: 'amber' },
    { name: 'errors', data: [8, 12, 10, 14, 6], color: 'rose' },
  ]}
  xLabels={['Jan', 'Feb', 'Mar', 'Apr', 'May']}
  yMin={0}
  yMax={220}
  yTickCount={6}
  legend
  width={480}
  height={250}
  ariaLabel="Requests and errors per month"
/>
```

### Gotchas

- The root is a `<div>` holding the `<svg>` and legend; `ref` and extra props go to the `<div>`.
- `color` takes a `StatusColor` name, not hex.
- Grid lines and axes always render; there is no `axes`/`grid` toggle.
- `yTickCount` counts tick lines including both ends, unlike `ticks` on the other charts (which counts intervals).
- With the default `yMax` the tallest bar touches the top. Set `yMax` for headroom.
- Negative values are supported: bars grow down from the zero baseline.
- Empty `series` (or all-empty `data`) renders a centered "No data" box at `width` × `height`.
- Passing `style` replaces the root's flex-column layout, which spaces the legend. Add `display: 'flex', flexDirection: 'column', gap: 8` to your `style` if you set one.

---

## BarV

Single-series vertical bar chart with a zero baseline.

```tsx
import { BarV } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `values` | `number[]` | required | Bar heights, zero or positive |
| `xLabels` | `string[]` | — | Label per bar (needs `axes`) |
| `color` | `string` | `'#F59E0B'` (amber) | Hex fill for every bar |
| `width` | `number` | `480` | SVG width in px |
| `height` | `number` | `200` | SVG height in px |
| `axes` | `boolean` | `false` | Axis lines, y ticks, x labels |
| `grid` | `boolean` | `false` | Horizontal grid lines |
| `ticks` | `number` | `4` | Y intervals (draws `ticks + 1` lines) |
| `threshold` | `{ value: number; label?: string }` | — | Dashed reference line |
| `tone` | `'light' \| 'dark'` | `'light'` | Canvas tone |
| `label` | `string` | — | SVG `aria-label` |
| `className` | `string` | `''` | Class on the `<svg>` |
| `style` | `React.CSSProperties` | — | Merged over `{ display: 'block' }` |
| `...svgProps` | | | Remaining SVG attributes spread onto the root `<svg>` |

### Usage

```tsx
<BarV values={[82, 64, 91, 47, 73, 88]} label="Builds per day" />
```

```tsx
<BarV
  values={[82, 64, 91, 47, 73, 88, 56, 79, 95, 68, 72, 84]}
  xLabels={['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']}
  color="#10B981"
  axes
  grid
  threshold={{ value: 80, label: 'sla' }}
  label="Monthly SLA attainment"
/>
```

### Gotchas

- Returns `null` for empty `values`.
- The y axis runs from 0 to the larger of the max value and `threshold.value`. Negative values are not supported and render broken bars.
- `xLabels` only render when `axes` is set.
- `label` has no default; without it the `role="img"` SVG has no accessible name.

---

## BarH

Horizontal bar chart for ranked categories: a label column, an inset track and a filled bar per item, with an optional value at the bar's end.

```tsx
import { BarH, type BarHItem } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `items` | `BarHItem[]` | required | One row per item |
| `width` | `number` | `320` | SVG width in px |
| `height` | `number` | `200` | SVG height in px |
| `tone` | `'light' \| 'dark'` | `'light'` | Canvas tone |
| `showValues` | `boolean` | `true` | Value text after each bar |
| `valueFormat` | `(value: number) => string` | compact (`1.2k`) | Formats the value text |
| `maxValue` | `number` | max item value | Value that fills the full track |
| `label` | `string` | `'Horizontal bar chart'` | SVG `aria-label` |
| `className` | `string` | `''` | Class on the `<svg>` |
| `style` | `React.CSSProperties` | — | Merged over `{ display: 'block' }` |
| `...svgProps` | | | Remaining SVG attributes spread onto the root `<svg>` |

### Data types

```ts
interface BarHItem {
  label: string  // row label; also the React key, so keep it unique
  value: number
  color?: string // per-row fill; defaults to cyan #22D3EE
}
```

### Usage

```tsx
<BarH
  items={[
    { label: 'svc_ingest', value: 92 },
    { label: 'svc_query', value: 78 },
    { label: 'svc_export', value: 64 },
  ]}
/>
```

```tsx
<BarH
  items={[
    { label: 'svc_ingest', value: 4.2, color: '#22D3EE' },
    { label: 'svc_query', value: 12.7, color: '#818CF8' },
    { label: 'svc_export', value: 31.4, color: '#F43F5E' },
  ]}
  width={320}
  height={120}
  maxValue={40}
  valueFormat={v => `${v.toFixed(1)} ms`}
  label="p95 latency by service"
/>
```

### Gotchas

- Returns `null` for empty `items`.
- All bars are cyan unless an item sets `color`; there is no `colors` array.
- The label column is a fixed 92 px with right-aligned text; long labels run off the left edge. The value gutter is 36 px, so long formatted values can clip near the right edge.
- Values above `maxValue` overflow the track. Set `maxValue` (e.g. `100`) to compare rows on a fixed scale.
- Bar thickness caps at 14 px; extra `height` adds spacing, not thicker bars.
- `item.label` is used as the React key; duplicate labels trigger key warnings.

---

## StackedBar

Vertical stacked bars, one stack per category, with optional 100% normalized mode and per-stack labels.

```tsx
import { StackedBar, type StackedBarStack } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `stacks` | `StackedBarStack[]` | required | One entry per bar |
| `colors` | `string[]` | series palette | Hex per part index |
| `width` | `number` | `480` | SVG width in px |
| `height` | `number` | `200` | SVG height in px |
| `axes` | `boolean` | `false` | Axis lines, y ticks, stack labels |
| `grid` | `boolean` | `false` | Horizontal grid lines |
| `ticks` | `number` | `4` | Y intervals (draws `ticks + 1` lines) |
| `normalized` | `boolean` | `false` | Scale each stack to 100% |
| `tone` | `'light' \| 'dark'` | `'light'` | Canvas tone |
| `label` | `string` | `'Stacked bar chart'` | SVG `aria-label` |
| `stackLabel` | `'total' \| ((stack: StackedBarStack) => string)` | — | Text above each stack |
| `className` | `string` | `''` | Class on the `<svg>` |
| `style` | `React.CSSProperties` | — | Merged over `{ display: 'block' }` |
| `...svgProps` | | | Remaining SVG attributes spread onto the root `<svg>` |

### Data types

```ts
interface StackedBarStack {
  label: string   // x-axis label (shown with `axes`)
  parts: number[] // bottom-up segment values; part i uses colors[i]
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
const stacks: StackedBarStack[] = [
  { label: 'Mon', parts: [42, 28, 14] },
  { label: 'Tue', parts: [48, 31, 12] },
  { label: 'Wed', parts: [38, 26, 18] },
]

<StackedBar
  stacks={stacks}
  colors={['#10B981', '#F59E0B', '#F43F5E']}
  width={480}
  height={180}
  axes
  grid
  normalized
  stackLabel="total"
  label="Job outcomes per day"
/>

<StackedBar stacks={stacks} axes stackLabel={s => `${s.parts[0]} ok`} />
```

### Gotchas

- Returns `null` for empty `stacks`.
- Colors map to the part position, not the stack: `parts[0]` of every stack shares `colors[0]`. Colors cycle past the end of the array.
- Stack labels (`stack.label`) only render with `axes`.
- With `normalized`, y ticks read `0%`–`100%`, but `stackLabel="total"` still prints the raw sum.
- `stackLabel` adds 16 px of top padding to make room for the text.
- A `NaN` part is skipped and suppresses that stack's `stackLabel`; in `normalized` mode such a stack is scaled against the largest valid total rather than its own.

---

## Donut

Ring chart for composition, with optional center value and eyebrow label. No legend. There is no separate pie component; see Gotchas for a pie.

```tsx
import { Donut, type DonutSlice } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `slices` | `DonutSlice[]` | required | One entry per slice, clockwise from 12 o'clock |
| `colors` | `string[]` | series palette | Hex per slice index |
| `width` | `number` | `160` | SVG width in px |
| `height` | `number` | `160` | SVG height in px |
| `thickness` | `number` | `14` | Ring width in px |
| `gap` | `number` | `0.03` | Gap between slices, radians |
| `centerValue` | `string` | — | Bold figure in the center |
| `centerLabel` | `string` | — | Mono uppercase label below it |
| `aria-label` | `string` | `'Donut chart'` | SVG `aria-label` |
| `tone` | `'light' \| 'dark'` | `'light'` | Canvas tone |
| `className` | `string` | `''` | Class on the `<svg>` |
| `style` | `React.CSSProperties` | — | Merged over `{ display: 'block' }` |
| `...svgProps` | | | Remaining SVG attributes spread onto the root `<svg>` |

### Data types

```ts
interface DonutSlice {
  value: number
  color?: string // overrides colors[i]
}
```

### Usage

```tsx
<Donut slices={[{ value: 134 }, { value: 72 }, { value: 45 }]} />
```

```tsx
const slices: DonutSlice[] = [
  { value: 134, color: '#10B981' },
  { value: 72, color: '#818CF8' },
  { value: 45, color: '#22D3EE' },
  { value: 16, color: '#F59E0B' },
]

<div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
  <Donut
    slices={slices}
    width={140}
    height={140}
    thickness={14}
    centerValue="267"
    centerLabel="ind."
    aria-label="Individuals by class"
  />
  <ul>{/* compose the legend yourself, one row per slice */}</ul>
</div>
```

### Gotchas

- No built-in legend; compose one beside the chart.
- Pie charts: there is no inner-radius prop. The outer radius is `min(width, height) / 2 - 4` and the inner radius is that minus `thickness`, so `thickness={Math.min(width, height) / 2 - 4}` (76 at the 160 px default) gives solid wedges. Larger values distort the shape, and `centerValue`/`centerLabel` then sit on top of the wedges.
- A single slice draws a full ring with no gap.
- All-zero values render as nearly invisible slivers, not an empty ring; handle that case yourself.
- `centerValue` font size scales with the chart (22% of the smaller side) and is not truncated; keep it short.
- Readability drops past about five slices; merge the tail into an "other" slice before passing.

---

## Heatmap

2-D density grid on a single-hue alpha scale, for hour-by-day activity or host-by-metric matrices.

```tsx
import { Heatmap } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `data` | `(number \| null)[][]` | required | `[rows][cols]` values |
| `baseColor` | `string` | `'#10B981'` | `#RRGGBB` for the hottest cells |
| `xLabels` | `string[]` | — | Column labels (needs `axes`) |
| `yLabels` | `string[]` | — | Row labels (needs `axes`) |
| `width` | `number` | `480` | SVG width in px |
| `height` | `number` | `120` | SVG height in px |
| `axes` | `boolean` | `false` | Show row/column labels |
| `tone` | `'light' \| 'dark'` | `'light'` | Canvas tone |
| `showValues` | `boolean` | `false` | Print each non-null value in its cell |
| `valueFormat` | `(value: number) => string` | compact (`1.2k`) | Formats cell values |
| `cellMark` | `(row: number, col: number, value: number \| null) => React.ReactNode` | — | SVG overlay per cell |
| `ariaLabel` | `string` | `'Heatmap'` | SVG `aria-label` and `<title>` |
| `className` | `string` | `''` | Class on the `<svg>` |
| `style` | `React.CSSProperties` | — | Merged over `{ display: 'block' }` |
| `...svgProps` | | | Remaining SVG attributes spread onto the root `<svg>` |

### Usage

```tsx
const activity: (number | null)[][] = [
  [0, 2, 5, 9, 4, 1],
  [1, 3, 7, null, 6, 2],
]

<Heatmap data={activity} />
```

```tsx
<Heatmap
  data={activity}
  baseColor="#22D3EE"
  width={320}
  height={110}
  axes
  yLabels={['Mon', 'Tue']}
  xLabels={['0h', '', '8h', '', '16h', '']}
  showValues
  valueFormat={v => `${v}`}
  cellMark={(row, col, value) =>
    value === 9 ? <circle r={3} fill="none" stroke="#F43F5E" strokeWidth={1.5} /> : null
  }
  ariaLabel="Requests per hour, svc_ingest"
/>
```

### Gotchas

- `baseColor` must be a 6-digit `#RRGGBB` hex: the component appends a two-digit alpha. `rgb()`, named colors and 3-digit hex produce invalid fills.
- The scale is relative: 12% opacity at the data minimum, 100% at the maximum. Uniform data renders every cell at 12%.
- `null` and `NaN` cells render as the inset background; use `null` for missing data, not `0`.
- Column count comes from `data[0].length`; keep rows the same length.
- Labels render only with `axes`. Row labels get a 28 px gutter, so use short ones (`'Mon'`, `'M'`); pass `''` to skip a column label.
- `showValues` switches to white text on cells above 55% intensity. Text is 10 px, so small cells get crowded.
- `cellMark` runs for every cell, including `null` ones (`value` is `null`). Its return value is placed in a `<g>` translated to the cell center, so draw around `(0, 0)` and return SVG elements. Falsy returns render nothing.
- The prop is `ariaLabel` (camelCase) here, unlike `aria-label` on `Donut` and `StatusTimeline`.

---

## StatusTimeline

Gantt-style status history: one horizontal track per service, colored segments across a time window, optional amber event marker.

```tsx
import { StatusTimeline, type StatusTrack, type StatusSegment, type SegmentKind } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `tracks` | `StatusTrack[]` | required | One row per service |
| `range` | `[number, number]` | `[0, 100]` | Domain that segment positions use |
| `width` | `number` | `480` | SVG width in px |
| `height` | `number` | `160` | SVG height in px |
| `axes` | `boolean` | `false` | Show `xLabels` below the tracks |
| `xLabels` | `string[]` | — | Evenly spaced time labels |
| `marker` | `{ x: number; label?: string }` | — | Amber event line, `x` in range units |
| `tone` | `'light' \| 'dark'` | `'light'` | Canvas tone |
| `aria-label` | `string` | — | SVG `aria-label` |
| `className` | `string` | `''` | Class on the `<svg>` |
| `style` | `React.CSSProperties` | — | Merged over `{ display: 'block' }` |
| `...svgProps` | | | Remaining SVG attributes spread onto the root `<svg>` |

### Data types

```ts
type SegmentKind = 'ok' | 'warn' | 'error' | 'idle' | 'info'

interface StatusSegment {
  start: number              // in `range` units
  end: number
  kind: SegmentKind | string // any other string is used as a CSS fill color
}

interface StatusTrack {
  label: string
  segments: StatusSegment[]
}
```

Kind colors: `ok` emerald, `warn` amber, `error` rose, `info` cyan, `idle` the tone's border gray.

### Usage

```tsx
<StatusTimeline
  tracks={[{ label: 'svc_ingest', segments: [{ start: 0, end: 100, kind: 'ok' }] }]}
  aria-label="svc_ingest status, last 24h"
/>
```

```tsx
const tracks: StatusTrack[] = [
  {
    label: 'svc_ingest',
    segments: [
      { start: 0, end: 22, kind: 'ok' },
      { start: 22, end: 28, kind: 'warn' },
      { start: 28, end: 64, kind: 'ok' },
      { start: 64, end: 68, kind: 'error' },
      { start: 68, end: 100, kind: 'ok' },
    ],
  },
  {
    label: 'svc_query',
    segments: [
      { start: 0, end: 14, kind: 'idle' },
      { start: 14, end: 86, kind: 'info' },
      { start: 86, end: 100, kind: '#8B5CF6' },
    ],
  },
]

<StatusTimeline
  tracks={tracks}
  width={720}
  height={180}
  range={[0, 100]}
  axes
  xLabels={['-24h', '-18h', '-12h', '-6h', 'now']}
  marker={{ x: 64, label: 'incident #142' }}
  aria-label="Service status, last 24h"
/>
```

### Gotchas

- Returns `null` for empty `tracks`.
- `aria-label` has no default; set one, or the `role="img"` SVG is unnamed.
- `xLabels` are spread evenly from the left to the right edge of the plot, independent of `range`; their count only sets spacing. Pass at least 2, and only with `axes`.
- Uncovered stretches show the inset track. Segments are not clipped to `range`, so out-of-range values draw outside the plot.
- Every segment is at least 2 px wide, so very short events stay visible.
- The track label column is a fixed 92 px; long labels run off the left edge.
- Bar thickness caps at 14 px.

---

## ProgressBar

Thin horizontal fill bar for progress, quota or utilization, with `role="progressbar"`.

```tsx
import { ProgressBar, type ProgressBarColor } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `percent` | `number` | required | Fill amount, clamped to 0–100 |
| `color` | `ProgressBarColor` | `'emerald'` | `StatusColor` name for the fill |
| `height` | `number` | `6` | Bar height in px |
| `label` | `string` | — | `aria-label` |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<ProgressBar percent={72} label="svc_ingest disk usage" />
```

```tsx
const percent = 94

<ProgressBar
  percent={percent}
  color={percent > 90 ? 'rose' : percent > 75 ? 'amber' : 'emerald'}
  height={8}
  label="Quota used"
/>
```

### Gotchas

- `percent` is clamped to `[0, 100]`; `NaN` becomes 0. `aria-valuenow` reports the clamped value.
- Fills 100% of its parent's width; constrain the parent to size it.
- `color` takes a `StatusColor` name only; hex values are not supported.
- The track uses the `shell-surface` navy on both light and dark canvas.
- A `style` prop replaces the inline `height`; include `height` in your `style` if you pass one.
- Width changes animate over 0.3 s.

---

## MetricRow

One dashboard row combining a label, a progress bar, a 60 × 18 sparkline and a value with unit.

```tsx
import { MetricRow } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `label` | `string` | required | Row label, first column |
| `value` | `number \| string` | required | Displayed value, last column |
| `unit` | `string` | — | Muted suffix after the value |
| `percent` | `number` | required | Progress bar fill, 0–100 |
| `sparklineData` | `number[]` | `[]` | Trend points for the sparkline |
| `color` | `SparklineColor` | `'emerald'` | Bar and sparkline color |
| `progressLabel` | `string` | `label` | Progress bar `aria-label` |
| `...divProps` | | | Remaining props (incl. `aria-label`, default `label`) spread onto the root `<div>` |

### Usage

```tsx
<MetricRow label="CPU usage" value={72} unit="%" percent={72} />
```

```tsx
interface Metric { label: string; value: number; unit: string; percent: number; history: number[] }

const metrics: Metric[] = [
  { label: 'CPU usage', value: 72, unit: '%', percent: 72, history: [45, 52, 48, 65, 72, 68, 75, 70, 72, 68] },
  { label: 'Memory', value: 1084, unit: 'MB', percent: 45, history: [890, 920, 950, 1000, 1050, 1080, 1084] },
  { label: 'Error rate', value: 5, unit: '%', percent: 95, history: [2, 3, 2, 4, 5, 4, 3, 5] },
]

<div role="table" aria-label="svc_ingest resources" style={{ maxWidth: 520 }}>
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
</div>
```

### Gotchas

- The root has `role="row"`; wrap rows in an element with `role="table"` (or `"grid"`) so the ARIA structure is valid.
- Fixed grid of `100px 1fr 70px 80px` with a 12 px gap: labels past 100 px truncate with an ellipsis, and the progress bar takes the remaining width.
- `value` and `percent` are independent; the component does not derive one from the other.
- The sparkline needs at least 2 points; with fewer, its column stays empty.
- Rows draw a bottom border except the last child, so render them as siblings in one parent.
- `color` is a `StatusColor` name only, applied to both the bar and the sparkline.
