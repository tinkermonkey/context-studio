---
name: heimdall-primitives
description: Heimdall component guide for Primitives: Icon, Avatar, Button, Chip, Badge, StatusBadge, VersionPill, SegmentedControl
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## Icon

Renders a named outline icon from the Heimdall icon set. Use it for every icon; never paste raw SVG.

```tsx
import { Icon } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `name` | `IconName` | required | Key of the `ICONS` map |
| `size` | `number` | `24` | Width and height in pixels |
| `...svgProps` | | | Remaining props spread onto the root `<svg>` |

### Usage

```tsx
// Minimal
<Icon name="settings" size={16} />
```

```tsx
// Standalone meaningful icon, and a tinted inline icon
<Icon name="alert" size={18} role="img" aria-label="Warning" />
<Icon name="gitBranch" size={14} className="text-amber-500" />
```

### Gotchas

- Valid names are the keys of `ICONS` (see "Icon map" below); the `IconName` type rejects anything else at compile time.
- Key naming is mixed: most are camelCase (`chevronDown`, `eyeOff`, `hardDrive`), a few are kebab-case (`bar-chart`, `trending-up`, `pie-chart`). Check the exact key.
- `aria-hidden` is set automatically unless `aria-label` is passed. `aria-label` alone does not add a role; pass `role="img"` for standalone icons that convey meaning.
- An unknown name (e.g. from untyped data cast to `IconName`) logs a console warning and renders nothing.
- Stroke-only (`fill="none"`, `stroke="currentColor"`, width 1.75): set color through the parent's or the icon's text color.
- `spinner` and `loading` are static glyphs. Add a rotation animation yourself if they should spin.
- Inside a `Button`, the button's CSS forces every child `<svg>` to 14×14 with stroke width 2, so `size` has no visible effect there.

## Icon map

`ICONS` is the name-to-path map behind `Icon`. `IconName` is `keyof typeof ICONS`. Each value is a single SVG path `d` string drawn on a 24×24 viewBox.

```tsx
import { ICONS, Icon, type IconName } from '@tinkermonkey/heimdall-ui'

const iconNames = Object.keys(ICONS) as IconName[]

export function IconGallery() {
  return (
    <div className="flex flex-wrap gap-3">
      {iconNames.map((name) => (
        <Icon key={name} name={name} size={16} role="img" aria-label={name} />
      ))}
    </div>
  )
}
```

Representative keys: `dashboard`, `schema`, `pipeline`, `graph`, `search`, `plus`, `x`, `chevronDown`, `settings`, `trash`, `filter`, `clock`, `folder`, `gitBranch`, `code`, `zoomIn`, `maximize`, `bar-chart`. Read `Object.keys(ICONS)` for the current set rather than relying on a copied list.

- Type data-driven icon fields as `IconName` so typos fail at compile time.
- Adding an icon to the library means adding a key and path string to `ICONS` in `src/components/Icon.tsx`; consumers cannot register icons at runtime.

---

## Avatar

People identifier: renders a photo, or initials on a deterministic gradient, with an optional presence dot.

```tsx
import { Avatar } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `name` | `string` | required | Full name; drives initials, gradient and accessible label |
| `src` | `string` | — | Image URL; falls back to initials on load error |
| `size` | `'xs' \| 'sm' \| 'md' \| 'lg'` | `'md'` | 20 / 28 / 36 / 64px |
| `shape` | `'circle' \| 'rounded'` | `'circle'` | Circle or 6px-radius square |
| `status` | `StatusColor` | — | Presence dot color, bottom-right |
| `color` | `StatusColor \| string` | auto | Initials background; auto-derived from `name` |
| `decorative` | `boolean` | — | Hide from assistive tech when name is shown nearby |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

`StatusColor` is `'emerald' | 'amber' | 'rose' | 'cyan' | 'violet' | 'neutral'`.

### Usage

```tsx
// Minimal
<Avatar name="Ada Lovelace" />
```

```tsx
// Photo with fallback, presence, explicit color, and a decorative avatar beside a visible name
<Avatar name="Grace Hopper" src="/avatars/ghopper.png" size="lg" status="emerald" />
<Avatar name="svc ingest" shape="rounded" size="sm" color="violet" />
<Avatar name="Alan Turing" color="linear-gradient(135deg, #0f1729, #243763)" />
<div className="flex items-center gap-2">
  <Avatar name="Katherine Johnson" size="sm" decorative />
  <span>Katherine Johnson</span>
</div>
```

### Gotchas

- Initials are the first letter of the first two space-separated words, uppercased. A single word like `svc_ingest` yields one letter; split on spaces if two are wanted.
- Without `color`, the gradient is picked from the six status colors by hashing `name`, so the same name always gets the same color.
- `color` accepts a `StatusColor` key (mapped to a gradient) or any CSS `background` value, which is applied as-is.
- Not decorative: the root gets `role="img"` and `aria-label` of `name`, or `"name (status)"` when `status` is set. Passing `role` or `aria-label` overrides these.
- After an image fails once, the avatar stays on initials even if `src` changes. Change `key` to retry a new URL.
- The image renders with `alt=""`; the accessible name comes from the root label.
- The status dot has a 2px ring in the canvas card color, so it reads correctly only on card or canvas backgrounds.

---

## Button

Standard action button with six variants and two sizes.

```tsx
import { Button } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `variant` | `'primary' \| 'accent' \| 'secondary' \| 'ghost' \| 'danger' \| 'link'` | `'primary'` | Visual style |
| `size` | `'sm' \| 'md'` | `'md'` | Height: md=34px, sm=28px |
| `icon` | `boolean` | — | Square button for icon-only use |
| `children` | `ReactNode` | required | Label, icon, or both |
| `type` | `'button' \| 'submit' \| 'reset'` | `'button'` | Native button type |
| `...buttonProps` | | | Remaining props spread onto the root `<button>` |

### Usage

```tsx
// Minimal
<Button>Save</Button>
```

```tsx
// Variants, icons, icon-only, form submit
<Button variant="primary"><Icon name="plus" size={14} /> Create</Button>
<Button variant="accent"><Icon name="upload" size={14} /> Run pipeline</Button>
<Button variant="secondary" size="sm">Cancel</Button>
<Button variant="ghost" icon aria-label="Add class"><Icon name="plus" size={14} /></Button>
<Button variant="danger" onClick={() => deleteClass('cls_organism')}>Delete</Button>
<Button variant="link">View lineage</Button>
<Button type="submit" disabled>Unavailable</Button>
```

### Gotchas

- `type` defaults to `'button'`, not `'submit'`; set `type="submit"` explicitly inside forms.
- `icon` sets width equal to height (34px md, 28px sm, zero padding). Add `aria-label` since there is no text.
- Every child `<svg>` is forced to 14×14 with stroke width 2 by the button CSS, regardless of `Icon`'s `size`.
- `secondary` and `ghost` currently render identically (transparent, bordered). `primary` is near-black on light canvas and amber on dark canvas; `accent` is amber-700 in both.
- `link` drops height, padding and border; it is underlined text in `accent-primary-deep`.
- Disabled buttons use `opacity: 0.5` and `pointer-events: none`, so tooltips or hover handlers on a disabled button never fire. Wrap it if a tooltip is needed.

---

## Chip

Inline tag for statuses, identifiers, versions, environments and inferred values.

```tsx
import { Chip } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `variant` | `'emerald' \| 'amber' \| 'rose' \| 'cyan' \| 'violet' \| 'neutral'` | `'neutral'` | Semantic color; only used when `form='default'` |
| `form` | `'default' \| 'id-tag' \| 'version' \| 'env' \| 'inferred'` | `'default'` | Visual style |
| `children` | `ReactNode` | required | Label text |
| `...spanProps` | | | Remaining props spread onto the root `<span>` |

### Usage

```tsx
// Status chip (default form)
<Chip variant="emerald">running</Chip>
```

```tsx
// Every form
<Chip variant="cyan">pulling</Chip>
<Chip variant="rose">failed</Chip>
<Chip form="id-tag">cls_4f3a</Chip>
<Chip form="version">v2.4.0</Chip>
<Chip form="env">production</Chip>
<Chip form="inferred">life.organism</Chip>
```

### Gotchas

- `variant` is ignored for every `form` other than `'default'`.
- `form='default'` and `form='env'` always render a leading 6px dot; there is no prop to hide it. The other forms have no dot.
- `version` is fully rounded (one of the few allowed pills); `env` uses 6px radius; `inferred` has a dashed border and no fill, for values derived rather than asserted.
- All forms are monospace 11px (`version` is 10.5px) and `white-space: nowrap`; long labels do not wrap.
- Color mapping: emerald=ok/running, rose=error/failed, cyan=updating/pulling, amber=warning/degraded, violet=secondary/pending, neutral=stopped/idle.

---

## Badge

A static 8px colored dot for inline use beside text.

```tsx
import { Badge } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `color` | `'cyan' \| 'emerald' \| 'amber' \| 'violet' \| 'rose' \| 'neutral'` | `'cyan'` | Dot color |
| `pulse` | `boolean` | `false` | Pulse the dot itself (scale and fade) |
| `...spanProps` | | | Remaining props spread onto the root `<span>` |

### Usage

```tsx
// Static dot
<Badge color="emerald" />
```

```tsx
// Inline with text
<span className="inline-flex items-center gap-1.5">
  <Badge color="cyan" />
  syncing
</span>
```

### Gotchas

- `pulse` animates the dot itself, which fades fully out each 1.6s cycle. For a live indicator with a solid dot and a pulsing halo, use `StatusBadge`.
- Renders an empty `<span>` with no role or label. Pair it with visible text, or add `role="img"` and `aria-label`.

---

## StatusBadge

Solid 8px dot with an optional pulsing halo, for live status indicators.

```tsx
import { StatusBadge } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `color` | `'cyan' \| 'emerald' \| 'amber' \| 'violet' \| 'rose' \| 'neutral'` | `'cyan'` | Dot and halo color |
| `pulse` | `boolean` | `false` | Animate the halo behind the dot |
| `role` | `AriaRole` | `'img'` | ARIA role; use `'presentation'` when decorative |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
// Minimal
<StatusBadge color="emerald" aria-label="running" />
```

```tsx
// Live and static states
<StatusBadge color="cyan" pulse aria-label="pulling" />
<StatusBadge color="rose" aria-label="failed" />
<StatusBadge color="neutral" role="presentation" />
```

### Gotchas

- Defaults to `role="img"`, so always pass `aria-label` (or set `role="presentation"`).
- Renders a `<div>` displayed `inline-flex`; it sits inline with text but is invalid inside a `<p>` or other phrasing-only parent. Use `Badge` there.
- The halo is a CSS pseudo-element (no extra DOM), scaling 0.6→1.4 and fading over 1.6s; it overflows the 8px box, so leave a few pixels of room.

---

## VersionPill

Compact monospace tag for version strings, tinted by tone.

```tsx
import { VersionPill } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `children` | `ReactNode` | required | Version text |
| `tone` | `'amber' \| 'emerald' \| 'rose'` | `'amber'` | Tint color |
| `...spanProps` | | | Remaining props spread onto the root `<span>` |

### Usage

```tsx
// Minimal
<VersionPill>v1.0.0</VersionPill>
```

```tsx
// Tones, inside a header row
<div className="flex items-center gap-2">
  <h2>cls_organism</h2>
  <VersionPill>v2.3.4</VersionPill>
  <VersionPill tone="emerald">v2.4.0</VersionPill>
  <VersionPill tone="rose">v2.2.1</VersionPill>
</div>
```

### Gotchas

- Fixed 18px height, 10.5px semibold mono, 3px radius, `white-space: nowrap`; meant for short strings.
- No format validation; any content is rendered as-is.
- Only three tones exist. For other semantic colors use `Chip form="version"` or a `Chip` variant.

---

## SegmentedControl

Radio group rendered as a connected row of segments, for mutually exclusive view or filter selection.

```tsx
import { SegmentedControl } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `value` | `string \| number` | required | Currently selected value |
| `onChange` | `(value: string \| number) => void` | required | Called with the newly selected value |
| `options` | `SegmentedControlOption[]` | required | Segments to render |
| `disabled` | `boolean` | `false` | Disable every segment |
| `...divProps` | | | Remaining props spread onto the root `<div role="radiogroup">` |

### Data types

```ts
interface SegmentedControlOption {
  value: string | number
  label: React.ReactNode
  disabled?: boolean
}
```

### Usage

```tsx
// Minimal
const [view, setView] = useState<string | number>('all')

<SegmentedControl
  value={view}
  onChange={setView}
  aria-label="Class filter"
  options={[
    { value: 'all', label: 'All' },
    { value: 'active', label: 'Active' },
    { value: 'archived', label: 'Archived' },
  ]}
/>
```

```tsx
// Narrow string state, icon labels, a disabled option
type Range = 'today' | 'week' | 'month'
const [range, setRange] = useState<Range>('today')

<SegmentedControl
  value={range}
  onChange={(v) => setRange(v as Range)}
  aria-label="Time range"
  options={[
    { value: 'today', label: 'Today' },
    { value: 'week', label: <><Icon name="calendar" size={12} /> This week</> },
    { value: 'month', label: 'This month', disabled: true },
  ]}
/>
```

### Gotchas

- `onChange` receives `string | number`. Passing a `useState<string>` setter directly fails to type-check; type the state `string | number` or cast in a wrapper.
- Selection follows focus: arrow keys (Left/Up, Right/Down) move focus and call `onChange` immediately, wrapping around and skipping disabled options.
- Clicking the already-active segment still calls `onChange` with the same value.
- If `value` matches no option, nothing is shown as selected and the first enabled option takes the tab stop.
- Option values are used as React keys and compared with `===`; keep them unique and of one type (`1` and `'1'` do not match).
- The root has `role="radiogroup"` but no label; pass `aria-label` or `aria-labelledby`.
