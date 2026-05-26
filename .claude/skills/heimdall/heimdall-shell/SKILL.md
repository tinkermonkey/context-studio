---
name: heimdall-shell
description: Heimdall component guide for Shell: AppTitle, Titlebar, Statusbar, ShellLayout
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## AppTitle

Brand mark with application name and optional version tag; collapses to icon-only for narrow sidebars.

```tsx
import { AppTitle } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | required | Application name |
| `version` | `string` | — | Version string (e.g. `'v0.1.0'`) |
| `collapsed` | `boolean` | `false` | Hides text; shows mark only |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
<AppTitle title="Heimdall" version="v0.1.0" />
```

```tsx
// Icon-only for collapsed sidebar
<AppTitle title="Heimdall" version="v0.1.0" collapsed />
```

### Gotchas

- When using `ShellLayout`, `collapsed` is automatically synced to the sidebar's collapse state — you do not need to manage it manually
- `aria-label` is auto-generated as `"${title} ${version}"` unless overridden

---

## Titlebar

Top-of-app chrome bar with left, center, and right slots for arbitrary content.

```tsx
import { Titlebar } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `left` | `ReactNode` | — | Left slot (brand, breadcrumb) |
| `center` | `ReactNode` | — | Center slot (auto-centered, expands) |
| `right` | `ReactNode` | — | Right slot (actions, user menu) |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
// Left and right slots
<Titlebar
  left={<span className="font-mono text-sm">heimdall</span>}
  right={
    <Button variant="ghost" size="sm">
      <Icon name="settings" size={14} /> Settings
    </Button>
  }
/>
```

```tsx
// All three slots
<Titlebar
  left={<span>heimdall</span>}
  center={<span className="uppercase text-xs tracking-widest">production</span>}
  right={<Icon name="bell" size={14} />}
/>
```

### Gotchas

- Only non-empty slots render a slot div — passing `undefined` produces no empty DOM element
- The center slot takes `flex: 1` and centers its content; left/right are natural width
- Default `role="banner"` and `aria-label="Application titlebar"` — override if needed

---

## Statusbar

Bottom status bar with three slots. Each slot accepts either React nodes or a structured `StatusbarItem[]` array.

```tsx
import { Statusbar } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `left` | `ReactNode \| StatusbarItem[]` | — | Left slot |
| `center` | `ReactNode \| StatusbarItem[]` | — | Center slot |
| `right` | `ReactNode \| StatusbarItem[]` | — | Right slot |
| `...HTMLAttributes` | | | Standard div attributes |

```ts
type StatusbarItem =
  | { kind: 'pulse'; tone: StatusbarTone; label: string; mono?: boolean }
  | { kind: 'icon'; icon: IconName; label?: string; mono?: boolean }
  | { kind: 'divider' }

type StatusbarTone = 'emerald' | 'cyan' | 'rose' | 'amber' | 'violet' | 'neutral'
```

### Usage

```tsx
// Plain React nodes
<Statusbar
  left={<span>context-studio · v0.4.1</span>}
  right={<span>12,480 individuals · 128 classes</span>}
/>
```

```tsx
// Structured items
<Statusbar
  left={[
    { kind: 'pulse', tone: 'emerald', label: 'connected' },
    { kind: 'divider' },
    { kind: 'icon', icon: 'check', label: 'no errors' },
  ]}
  right={[
    { kind: 'pulse', tone: 'amber', label: 'Ln 42, Col 8', mono: true },
  ]}
/>
```

### Gotchas

- Slot detection is automatic: if the first item in an array has a `kind` property, the array is treated as `StatusbarItem[]`; otherwise it's rendered as `ReactNode`
- Icon items render at a fixed 14px size
- `kind: 'divider'` renders a vertical separator line between items
- Renders as `role="status"` for live region announcements

---

## ShellLayout

Full IDE-chrome shell that composes AppTitle, Sidebar, Topbar, Titlebar, and Statusbar around a main canvas.

```tsx
import { ShellLayout } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `appTitle` | `AppTitleProps & { hide?: boolean }` | — | AppTitle config; set `hide: true` to omit |
| `titlebar` | `TitlebarProps & { hide?: boolean }` | — | Titlebar config |
| `sidebar` | `SidebarProps & { hide?: boolean }` | — | Sidebar config |
| `topbar` | `TopbarProps & { hide?: boolean }` | — | Topbar config |
| `statusbar` | `StatusbarProps & { hide?: boolean }` | — | Statusbar config |
| `children` | `ReactNode` | required | Main canvas content |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
// Minimal shell with sidebar and topbar
<ShellLayout
  appTitle={{ title: 'Heimdall', version: 'v0.1.0' }}
  sidebar={{
    sections: [
      {
        title: 'Nav',
        items: [
          { id: 'dashboard', label: 'Dashboard', icon: 'dashboard' },
          { id: 'schema', label: 'Schema', icon: 'schema' },
        ],
      },
    ],
    activeItemId: activeId,
    onSelectItem: setActiveId,
    onCollapse: setCollapsed,
  }}
  topbar={{ breadcrumbs: [{ label: 'Dashboard' }] }}
  statusbar={{ right: <span>v0.1.0</span> }}
>
  <div style={{ padding: '22px 26px' }}>
    {/* page content */}
  </div>
</ShellLayout>
```

```tsx
// With titlebar and no sidebar
<ShellLayout
  titlebar={{
    left: <span className="font-mono">heimdall</span>,
    right: <Button variant="ghost" size="sm">Sign out</Button>,
  }}
  topbar={{ breadcrumbs: [{ label: 'Settings' }] }}
>
  {/* content */}
</ShellLayout>
```

### Gotchas

- `AppTitle.collapsed` is automatically synced to the sidebar's `collapsed` state — do not set it manually when using `ShellLayout`
- The `hide` field on each config object is stripped before passing props to the child component
- Children are always rendered inside `<main>` — no need to add your own `<main>` tag
- Canvas inner padding should be applied by child content: recommended `padding: '22px 26px 32px'`
