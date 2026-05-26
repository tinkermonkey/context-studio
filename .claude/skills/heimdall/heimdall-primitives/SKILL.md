---
name: heimdall-primitives
description: Heimdall component guide for Primitives: Icon, Button, Chip, Badge, StatusBadge, VersionPill, SegmentedControl
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## Icon

Renders a named SVG icon from the Heimdall icon set using `currentColor` for stroke.

```tsx
import { Icon } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `name` | `IconName` | required | Icon to render (see list below) |
| `size` | `number` | `24` | Width and height in pixels |
| `...SVGAttributes` | | | All standard SVG attributes |

Available icon names: `'dashboard' | 'schema' | 'data' | 'pipeline' | 'graph' | 'search' | 'bell' | 'plus' | 'check' | 'x' | 'chevronDown' | 'chevronUp' | 'chevronLeft' | 'chevronRight' | 'menu' | 'settings' | 'alert' | 'trash' | 'edit' | 'download' | 'upload' | 'eye' | 'eyeOff' | 'clock' | 'calendar' | 'filter' | 'link' | 'lock' | 'unlock' | 'user' | 'copy' | 'info' | 'help' | 'spinner' | 'loading' | 'moreVertical' | 'moreHorizontal' | 'reload' | 'arrowRight' | 'arrowLeft' | 'arrowUp' | 'arrowDown' | 'star' | 'heart' | 'palette' | 'component' | 'table' | 'layout' | 'moon' | 'sun' | 'bar-chart' | 'trending-up' | 'trending-down' | 'send' | 'bot' | 'paperclip' | 'pie-chart' | 'slash' | 'file' | 'zap' | 'hardDrive'`

### Usage

```tsx
// Minimal
<Icon name="settings" size={16} />
```

```tsx
// With aria-label for decorative/standalone icons
<Icon name="alert" size={18} aria-label="Warning" />
<Icon name="plus" size={14} className="text-amber-500" />
```

### Gotchas

- `aria-hidden="true"` is set automatically unless you provide `aria-label`
- Logs a console warning (does not throw) if the icon name doesn't exist
- Uses `stroke`, not `fill` — color is inherited via `currentColor` from the parent

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
| `icon` | `boolean` | `false` | Constrain to square for icon-only use |
| `children` | `ReactNode` | required | Button label or content |
| `...ButtonHTMLAttributes` | | | All standard button attributes |

### Usage

```tsx
// Minimal
<Button>Save</Button>
```

```tsx
// Full variants
<Button variant="primary">Create</Button>
<Button variant="accent"><Icon name="upload" size={14} /> Run pipeline</Button>
<Button variant="secondary" size="sm">Cancel</Button>
<Button variant="ghost" icon><Icon name="plus" size={14} /></Button>
<Button variant="danger" onClick={handleDelete}>Delete</Button>
<Button variant="link">Learn more</Button>
<Button disabled>Unavailable</Button>
```

### Gotchas

- `type` defaults to `'button'`, not `'submit'` — set `type="submit"` explicitly inside forms
- The `icon` prop makes the button square; you must size the child `<Icon>` yourself

---

## Chip

Inline status and label tag for entity types, environment names, and identifiers.

```tsx
import { Chip } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `variant` | `'emerald' \| 'amber' \| 'rose' \| 'cyan' \| 'violet' \| 'neutral'` | `'neutral'` | Semantic color (only applies to `form='default'`) |
| `form` | `'default' \| 'id-tag' \| 'version' \| 'env'` | `'default'` | Visual style |
| `children` | `ReactNode` | required | Label text |

### Usage

```tsx
// Status chip (default form)
<Chip variant="cyan">running</Chip>
<Chip variant="emerald">success</Chip>
<Chip variant="rose">failed</Chip>
```

```tsx
// Specialized forms
<Chip form="id-tag">cls_4f3a</Chip>
<Chip form="version">v2.4.0</Chip>
<Chip form="env">production</Chip>
```

### Gotchas

- `variant` is silently ignored when `form` is anything other than `'default'`
- `form='default'` and `form='env'` auto-render a colored dot — there is no way to suppress it
- Semantic color guide: emerald=ok/success, rose=error/failed, cyan=active/updating, amber=warning, violet=secondary/pending, neutral=idle/stopped

---

## Badge

A small colored dot indicator for inline use alongside text or icons.

```tsx
import { Badge } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `color` | `'cyan' \| 'emerald' \| 'amber' \| 'violet' \| 'rose' \| 'neutral'` | `'cyan'` | Dot color |
| `pulse` | `boolean` | `false` | Animated pulse ring (for live/active states) |
| `...HTMLAttributes` | | | Standard span attributes |

### Usage

```tsx
// Static dot
<Badge color="emerald" />
```

```tsx
// Inline with text
<span className="flex items-center gap-1">
  <Badge color="cyan" />
  syncing
</span>
```

### Gotchas

- `Badge` renders as `<span>`; use `StatusBadge` instead when you need the animated pulse halo

---

## StatusBadge

Colored dot with optional pulse animation for live status indicators.

```tsx
import { StatusBadge } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `color` | `'cyan' \| 'emerald' \| 'amber' \| 'violet' \| 'rose' \| 'neutral'` | `'cyan'` | Dot color |
| `pulse` | `boolean` | `false` | Animated pulse halo |
| `role` | `string` | `'img'` | ARIA role; override with `'presentation'` if purely decorative |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
// Minimal
<StatusBadge color="emerald" aria-label="running" />
```

```tsx
// Pulsing live indicator
<StatusBadge color="cyan" pulse aria-label="syncing" />
<StatusBadge color="rose" aria-label="error" />
```

### Gotchas

- Renders as `<div>` (block element), unlike `Badge` which is `<span>`
- Pulse adds an extra halo DOM element — avoid using inside very tight layouts

---

## VersionPill

Compact amber monospace tag for displaying version strings.

```tsx
import { VersionPill } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `children` | `ReactNode` | required | Version string content |
| `...HTMLAttributes` | | | Standard span attributes |

### Usage

```tsx
<VersionPill>v1.0.0</VersionPill>
```

```tsx
// Inside a header row
<div className="flex items-center gap-2">
  <h2>My Component</h2>
  <VersionPill>v2.3.4</VersionPill>
</div>
```

### Gotchas

- Always amber background — not color-customizable
- No format validation; any string is accepted

---

## SegmentedControl

Accessible radio-button group rendered as a connected pill row for mutually exclusive filter/view selection.

```tsx
import { SegmentedControl } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `value` | `string \| number` | required | Currently selected value |
| `onChange` | `(value: string \| number) => void` | required | Called on selection change |
| `options` | `SegmentedControlOption[]` | required | Array of option definitions |
| `disabled` | `boolean` | `false` | Disable the entire control |

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
const [view, setView] = useState('all')

<SegmentedControl
  value={view}
  onChange={setView}
  options={[
    { value: 'all', label: 'All' },
    { value: 'active', label: 'Active' },
    { value: 'archived', label: 'Archived' },
  ]}
/>
```

```tsx
// With per-option disabling and icons
<SegmentedControl
  value={view}
  onChange={setView}
  options={[
    { value: 'today', label: 'Today' },
    { value: 'week', label: 'This week' },
    { value: 'month', label: 'This month', disabled: true },
  ]}
/>
```

### Gotchas

- Arrow keys navigate between enabled options; disabled options are skipped entirely
- If the current `value` matches no option, the first enabled option receives `tabIndex={0}` for keyboard access
- Don't mix string and number types in `value` across options and the controlled `value` prop
