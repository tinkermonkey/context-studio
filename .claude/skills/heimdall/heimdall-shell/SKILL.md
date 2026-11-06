---
name: heimdall-shell
description: Heimdall component guide for Shell: AppTitle, Titlebar, Statusbar, ShellLayout
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## AppTitle

Brand row with the amber mark, application name, optional version tag, and an optional trailing action; sits at the top of the sidebar column.

```tsx
import { AppTitle } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `title` | `string` | required | Application name |
| `version` | `string` | — | Mono version tag below the name |
| `collapsed` | `boolean` | `false` | Hides name and version; mark only |
| `action` | `ReactNode` | — | Trailing control, e.g. a collapse toggle |
| `aria-label` | `string` | `` `${title} ${version}` `` | Accessible label; `title` alone without `version` |
| `role` | `AriaRole` | `'banner'` | Landmark role of the root |
| `...divProps` | | | Remaining props spread onto the root `<div>` (ref forwarded) |

### Usage

```tsx
<AppTitle title="Heimdall" version="v0.9.0" />
```

```tsx
// Trailing action, and the collapsed form for a 64px column
<>
  <div style={{ width: 256 }}>
    <AppTitle
      title="Heimdall"
      version="v0.9.0"
      action={
        <Button variant="ghost" size="sm" icon aria-label="Collapse sidebar" onClick={() => setCollapsed(true)}>
          <Icon name="chevronLeft" size={16} />
        </Button>
      }
    />
  </div>
  <div style={{ width: 64 }}>
    <AppTitle title="Heimdall" version="v0.9.0" collapsed />
  </div>
</>
```

### Gotchas

- The mark is a fixed CSS amber gradient; there is no prop for a custom logo.
- `version` is rendered uppercase by CSS (`v0.9.0` displays as `V0.9.0`).
- `collapsed` hides the text and centers the mark; `action` still renders.
- The root has `role="banner"`. Next to a `Titlebar` (also `banner`) the page has two banner landmarks; pass `role` to change one.
- Inside `Sidebar` (via `appTitle`) or `ShellLayout`, `collapsed` is driven by the sidebar and the collapse toggle fills `action` when none is given. Do not set `collapsed` yourself there.
- The root carries right and bottom borders sized for the sidebar column; it is not meant for the topbar row.

---

## Titlebar

48px full-width chrome bar with left, center, and right slots, rendered above the sidebar and content.

```tsx
import { Titlebar } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `left` | `ReactNode` | — | Natural-width left slot |
| `center` | `ReactNode` | — | Flexible slot; content centered |
| `right` | `ReactNode` | — | Natural-width right slot |
| `role` | `AriaRole` | `'banner'` | Landmark role of the root |
| `aria-label` | `string` | `'Application titlebar'` | Accessible label of the root |
| `...divProps` | | | Remaining props spread onto the root `<div>` (ref forwarded) |

### Usage

```tsx
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
<Titlebar
  left={<span className="font-mono text-sm">heimdall</span>}
  center={<span className="font-mono text-xs uppercase tracking-widest">env_production</span>}
  right={<Icon name="bell" size={14} />}
/>
```

### Gotchas

- A slot renders only when its value is truthy; omitted slots leave no empty element. Without `center`, `left` and `right` are pushed to the edges.
- `center` is centered in the space between `left` and `right`, not in the window, so unequal side slots shift it.
- The bar is `overflow: hidden` at a fixed 48px height; oversized slot content is clipped.

---

## Statusbar

27px bottom bar with left, center, and right slots; each slot takes React nodes or a typed `StatusbarItem[]` of pulses, icons, and dividers.

```tsx
import { Statusbar, type StatusbarItem } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `left` | `ReactNode \| StatusbarItem[]` | — | Natural-width left slot |
| `center` | `ReactNode \| StatusbarItem[]` | — | Flexible, centered slot |
| `right` | `ReactNode \| StatusbarItem[]` | — | Natural-width right slot |
| `mobileBreakpoint` | `number \| false` | `768` | Max-width in px for mobile mode; `false` disables |
| `role` | `AriaRole` | `'status'` | Root role; `status` is a polite live region |
| `...divProps` | | | Remaining props spread onto the root `<div>` (ref forwarded) |

### Data types

`StatusbarItem` is the union `StatusbarPulseItem | StatusbarIconItem | StatusbarDividerItem`, discriminated by `kind`. All four types are exported.

#### StatusbarPulseItem

Solid 8px dot with the animated glow (1.6s) and a label.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `kind` | `'pulse'` | Discriminator |
| `tone` | `StatusbarTone` | Dot color |
| `label` | `string` | Text after the dot |
| `mono` | `boolean` | JetBrains Mono label in a brighter color |

#### StatusbarIconItem

| Field | Type | Description |
| ----- | ---- | ----------- |
| `kind` | `'icon'` | Discriminator |
| `icon` | `IconName` | Rendered at 14px |
| `label` | `string` | Optional visible text; also the item's `aria-label` |
| `mono` | `boolean` | Brightens the icon only; label font is unchanged |

#### StatusbarDividerItem

| Field | Type | Description |
| ----- | ---- | ----------- |
| `kind` | `'divider'` | 1×12px vertical separator |

#### StatusbarTone

`'emerald' | 'cyan' | 'rose' | 'amber' | 'violet' | 'neutral'` — emerald for ok/running, cyan for updating, rose for error, amber for the accent, violet for secondary, neutral for idle.

### Usage

```tsx
<Statusbar
  left={<span>svc_ingest · v0.4.1</span>}
  right={<span>12,480 individuals · 128 classes</span>}
/>
```

```tsx
const left: StatusbarItem[] = [
  { kind: 'pulse', tone: 'emerald', label: 'connected' },
  { kind: 'divider' },
  { kind: 'icon', icon: 'check', label: 'no errors' },
]
const right: StatusbarItem[] = [
  { kind: 'pulse', tone: 'cyan', label: 'syncing', mono: true },
  { kind: 'divider' },
  { kind: 'icon', icon: 'gitBranch', label: 'main' },
]

<Statusbar left={left} center={<span>ws_production</span>} right={right} mobileBreakpoint={640} />
```

### Gotchas

- Slot type detection checks only the first array element: if it has a `kind` property the whole array renders as items, otherwise the array renders as React nodes. Do not mix items and elements in one array. An empty array still renders an empty slot.
- The root is `role="status"`, so screen readers announce every content change. For content that updates constantly (cursor position, clocks), pass a different `role`.
- Mobile mode applies when the viewport is at or below `mobileBreakpoint`: the center slot clips its overflow and item labels become single-line with ellipsis. Slots are not hidden or stacked, and `left`/`right` never shrink, so keep them short.
- `mobileBreakpoint={false}` keeps desktop styling at every width; the root's `data-mobile` attribute overrides the built-in 768px media query.
- Inside `ShellLayout` the statusbar inherits ShellLayout's `mobileBreakpoint` unless the `statusbar` config sets its own.

---

## ShellLayout

Full-viewport IDE chrome: optional Titlebar on top, Sidebar (with AppTitle) on the left, Topbar above a scrolling canvas `<main>`, optional Statusbar at the bottom, and a drawer-based sidebar below a mobile breakpoint.

```tsx
import { ShellLayout } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `titlebar` | `TitlebarProps & { hide?: boolean }` | — | Full-width bar above everything |
| `appTitle` | `AppTitleProps & { hide?: boolean }` | — | Brand; becomes the sidebar header |
| `topbar` | `TopbarProps & { hide?: boolean }` | — | Bar above the canvas |
| `sidebar` | `SidebarProps & { hide?: boolean }` | — | Left navigation column |
| `statusbar` | `StatusbarProps & { hide?: boolean }` | — | Full-width bar below everything |
| `mobileBreakpoint` | `number \| false` | `768` | Max-width in px for drawer mode; `false` disables |
| `children` | `ReactNode` | — | Canvas content, rendered inside `<main>` |
| `...divProps` | | | Remaining props spread onto the root `<div>` (ref forwarded) |

### Usage

```tsx
<ShellLayout
  appTitle={{ title: 'Heimdall', version: 'v0.9.0' }}
  sidebar={{
    sections: [
      {
        title: 'Workspace',
        items: [
          { id: 'dashboard', label: 'Dashboard', icon: 'dashboard' },
          { id: 'schema', label: 'Schema', icon: 'schema' },
        ],
      },
    ],
    activeItemId: activeId,
    onSelectItem: setActiveId,
    collapsed,
    onCollapse: setCollapsed,
  }}
  topbar={{ breadcrumbs: [{ label: 'Dashboard' }] }}
>
  <DashboardPage />
</ShellLayout>
```

```tsx
// Full chrome: expandable nav, sidebar footer, topbar actions, structured statusbar
<ShellLayout
  appTitle={{ title: 'Heimdall', version: 'v0.9.0' }}
  sidebar={{
    sections: [
      {
        title: 'Workspace',
        items: [
          { id: 'dashboard', label: 'Dashboard', icon: 'dashboard' },
          {
            id: 'schema',
            label: 'Schema',
            icon: 'schema',
            count: 128,
            children: [
              { id: 'cls_organism', label: 'life.organism', count: 42 },
              { id: 'cls_cell', label: 'life.cell', count: 18 },
            ],
          },
          { id: 'pipelines', label: 'Pipelines', icon: 'pipeline', count: 17 },
        ],
      },
      {
        title: 'Tools',
        items: [{ id: 'settings', label: 'Settings', icon: 'settings' }],
      },
    ],
    activeItemId: activeId,
    onSelectItem: setActiveId,
    collapsed,
    onCollapse: setCollapsed,
    defaultExpandedIds: ['schema'],
    footer: <span className="font-mono text-xs">usr_ops_admin</span>,
  }}
  topbar={{
    breadcrumbs: [{ label: 'Schema' }, { label: 'life.organism' }],
    searchPlaceholder: 'Search classes…',
    searchHint: '⌘K',
    onSearch: setQuery,
    children: (
      <Button variant="ghost" size="sm" icon aria-label="Toggle dark canvas" onClick={toggleDarkCanvas}>
        <Icon name="moon" size={14} />
      </Button>
    ),
  }}
  statusbar={{
    left: [
      { kind: 'pulse', tone: 'emerald', label: 'connected' },
      { kind: 'divider' },
      { kind: 'icon', icon: 'gitBranch', label: 'main' },
    ],
    right: <span>12,480 individuals</span>,
  }}
  mobileBreakpoint={900}
>
  <SchemaPage />
</ShellLayout>
```

### Gotchas

- The root is `height: 100vh; overflow: hidden`. `<main>` is the scroll container; do not add another page-level scroller. To embed the shell in a smaller box, override the height with `className` or `style`.
- The canvas already has padding (`22px 26px 32px`, `18px 20px 28px` at ≤1024px, `14px 16px 24px` at ≤640px) and an 8px top-left radius. Do not add outer padding or a `<main>` of your own.
- A region renders only when its config object is passed and `hide` is not `true`; `hide` is stripped before props reach the child. Topbar actions go in the `children` key of the `topbar` config.
- `appTitle` with a sidebar becomes the sidebar's header (it overrides `sidebar.appTitle`), the collapse toggle moves into its action slot, and its `collapsed` follows the sidebar. Without a sidebar it renders on its own at the left of the main row, beside the topbar and canvas.
- ShellLayout holds no collapse state. Pass `collapsed` and `onCollapse` in the `sidebar` config, or the toggle does nothing.
- At or below `mobileBreakpoint` (viewport `max-width`):
  - The sidebar column is removed. A menu button (`aria-label="Open sidebar menu"`) is prepended to the topbar's `leadingContent`, or shown in a 56px header row when there is no topbar.
  - The button opens a 280px left `Drawer` holding the sidebar with `collapsed` forced to `false` and `showCollapseToggle` forced to `false`. Focus is trapped, Escape and backdrop clicks close it, and body scroll is locked. The drawer stays mounted, so expansion state survives.
  - Selecting a leaf item calls `onSelectItem` and then closes the drawer; toggling a parent does not.
  - Widening past the breakpoint closes the drawer. The consumer's `collapsed` value is ignored while mobile and applies again on desktop.
  - The breakpoint is forwarded to `Topbar` (search box hides, breadcrumbs truncate) and `Statusbar` (labels truncate) unless their configs set their own `mobileBreakpoint`.
- With `appTitle` set, the drawer's AppTitle still shows the collapse caret (Sidebar ignores `showCollapseToggle` when it hosts an AppTitle). Clicking it calls `onCollapse(true)` but the drawer stays expanded.
- `mobileBreakpoint={false}` disables drawer mode; the sidebar stays inline at every width.
- The root carries `data-mobile="true" | "false"` for styling. Without `window` (SSR) the first render is desktop.
