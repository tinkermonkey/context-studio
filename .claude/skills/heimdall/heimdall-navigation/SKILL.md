---
name: heimdall-navigation
description: Heimdall component guide for Navigation: NavItem, Sidebar, Topbar, TabBar
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## NavItem

Single shell-surface navigation button with optional icon, count, and active marker; use it to build a custom nav column when `Sidebar` does not fit.

```tsx
import { NavItem } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `label` | `string` | required | Display text; truncates with ellipsis |
| `icon` | `IconName` | — | 16px icon left of label; top level only |
| `count` | `number` | — | Mono count, right-aligned |
| `active` | `boolean` | `false` | Amber left marker, surface background, `aria-current="page"` |
| `depth` | `0 \| 1` | `0` | `1` indents as a sub-item and drops the icon |
| `type` | `'button' \| 'submit' \| 'reset'` | `'button'` | Native button type |
| `...buttonProps` | | | Remaining props spread onto the root `<button>` (ref forwarded) |

### Usage

```tsx
<NavItem
  icon="dashboard"
  label="Dashboard"
  active={activeId === 'dashboard'}
  onClick={() => setActiveId('dashboard')}
/>
```

```tsx
// Custom nav column: parent item with counts and depth-1 children
<div style={{ background: 'rgb(var(--shell-bg-2))', padding: '10px 8px', width: 256 }}>
  <NavItem
    icon="schema"
    label="Schema"
    count={128}
    active={activeId === 'schema'}
    onClick={() => setActiveId('schema')}
  />
  <NavItem
    label="life.organism"
    depth={1}
    count={42}
    active={activeId === 'cls_organism'}
    onClick={() => setActiveId('cls_organism')}
  />
  <NavItem label="life.cell" depth={1} count={18} disabled />
</div>
```

### Gotchas

- `icon` is ignored when `depth={1}`.
- The active marker is drawn at `left: -8px`, outside the button. Give the container at least 8px horizontal padding or the marker is clipped.
- Colors use shell tokens (`--shell-fg-*`, `--shell-surface`). On a light canvas the text has poor contrast; place NavItem on a shell-colored container.
- The button is `width: 100%`; constrain width with the container.
- `disabled` renders at 40% opacity with `pointer-events: none`.
- `Sidebar` renders its own item buttons, not `NavItem`. Use one or the other.

---

## Sidebar

Left navigation column with titled sections, expandable parent items, a 256px/64px collapse toggle, an optional `AppTitle` header, and a footer slot.

```tsx
import { Sidebar } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `sections` | `SidebarSection[]` | required | Titled groups of items |
| `activeItemId` | `string` | — | Id of the highlighted item or child |
| `collapsed` | `boolean` | `false` | Icon-only 64px mode; controlled by the parent |
| `onCollapse` | `(collapsed: boolean) => void` | — | Toggle clicked; receives the next value |
| `onSelectItem` | `(itemId: string) => void` | — | Leaf item or child clicked |
| `defaultExpandedIds` | `string[]` | — | Parents expanded on first render (uncontrolled) |
| `expandedIds` | `string[]` | — | Controlled set of expanded parents |
| `onExpandedChange` | `(ids: string[]) => void` | — | Called with the next expanded set |
| `showCollapseToggle` | `boolean` | `true` | Built-in toggle; ignored when `appTitle` is set |
| `appTitle` | `AppTitleProps` | — | Renders an `AppTitle` header hosting the toggle |
| `footer` | `ReactNode` | — | Content pinned to the bottom edge |
| `...divProps` | | | Remaining props spread onto the root `<div>` (ref forwarded) |

### Data types

#### SidebarSection

| Field | Type | Description |
| ----- | ---- | ----------- |
| `title` | `string` | Mono uppercase eyebrow; also the React key, so keep unique |
| `items` | `SidebarItem[]` | Items in the section |

#### SidebarItem

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | `string` | Passed to `onSelectItem`; matched against `activeItemId` |
| `label` | `string` | Display text; becomes the `title` tooltip when collapsed |
| `icon` | `IconName` | 18px icon; the only thing visible when collapsed |
| `count` | `number` | Mono count, right-aligned |
| `children` | `Array<{ id: string; label: string; count?: number }>` | One level of sub-items; makes the item an expandable parent |

### Usage

```tsx
<Sidebar
  sections={[
    {
      title: 'Workspace',
      items: [
        { id: 'dashboard', label: 'Dashboard', icon: 'dashboard' },
        { id: 'pipelines', label: 'Pipelines', icon: 'pipeline', count: 17 },
      ],
    },
  ]}
  activeItemId={activeId}
  onSelectItem={setActiveId}
  showCollapseToggle={false}
/>
```

```tsx
// AppTitle header, collapse, controlled expansion, footer
<div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
  <Sidebar
    appTitle={{ title: 'Heimdall', version: 'v0.9.0' }}
    sections={[
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
        ],
      },
      {
        title: 'Tools',
        items: [{ id: 'settings', label: 'Settings', icon: 'settings' }],
      },
    ]}
    activeItemId={activeId}
    onSelectItem={setActiveId}
    collapsed={collapsed}
    onCollapse={setCollapsed}
    expandedIds={expandedIds}
    onExpandedChange={setExpandedIds}
    footer={<span className="font-mono text-xs">usr_ops_admin</span>}
  />
</div>
```

### Gotchas

- Clicking a parent (an item with `children`) toggles its expansion and does **not** call `onSelectItem`. Parents are not selectable; give the overview page its own leaf item if one is needed.
- Expansion is uncontrolled by default. `defaultExpandedIds` is read once on mount. Passing `expandedIds` switches to controlled mode: the component only reflects that prop, so update it in `onExpandedChange` or toggles do nothing.
- `collapsed` is fully controlled. The toggle only calls `onCollapse(!collapsed)`; without `onCollapse` it does nothing, so hide it with `showCollapseToggle={false}`.
- Collapsed mode hides section titles, labels, counts, chevrons, and child items. Items without an `icon` render as empty buttons, so give every top-level item an icon when collapse is enabled. Clicking a parent while collapsed still flips its expansion state, which shows up after expanding the sidebar.
- With `appTitle`: when expanded, the toggle sits in the AppTitle `action` slot; when collapsed, the AppTitle shows the mark only and the toggle renders below it. The AppTitle's `collapsed` always follows the sidebar's. Passing `appTitle.action` replaces the toggle while expanded, which leaves no collapse control in that state.
- The root uses `flex: 1; min-height: 0` with a fixed `width` (200ms width transition). Place it in a flex **column** container that has a height, as above. As a direct child of a flex row it grows past 256px to fill the free width.
- The nav area scrolls internally (`overflow-y: auto`); `footer` stays pinned below it with a top border.
- Inside `ShellLayout`, pass the brand through ShellLayout's `appTitle` prop rather than `sidebar.appTitle`; ShellLayout's value wins.

---

## Topbar

48px bar above the canvas with breadcrumbs, a leading slot, an optional search box with a shortcut hint, and a right-side actions slot.

```tsx
import { Topbar } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `breadcrumbs` | `BreadcrumbItem[]` | — | Trail separated by `/`; last item is current |
| `searchPlaceholder` | `string` | `'Search…'` | Search placeholder and its `aria-label` |
| `onSearch` | `(query: string) => void` | — | Renders the search box; fires per keystroke |
| `leadingContent` | `ReactNode` | — | Content before the breadcrumbs, e.g. workspace switcher |
| `searchHint` | `ReactNode` | — | Shortcut glyph inside the search box, e.g. `⌘K` |
| `mobileBreakpoint` | `number \| false` | `768` | Max-width in px for mobile mode; `false` disables |
| `children` | `ReactNode` | — | Actions in the right slot |
| `...divProps` | | | Remaining props spread onto the root `<div>` (ref forwarded) |

### Data types

#### BreadcrumbItem

| Field | Type | Description |
| ----- | ---- | ----------- |
| `label` | `string` | Display text |
| `href` | `string` | Renders an `<a>`; takes precedence over `onClick` |
| `onClick` | `() => void` | Renders a `<button>` when `href` is absent |

An item with neither `href` nor `onClick` renders as a static `<span>`.

### Usage

```tsx
<Topbar
  breadcrumbs={[
    { label: 'Workspace' },
    { label: 'Schema' },
    { label: 'life.organism' },
  ]}
/>
```

```tsx
// Leading slot, linked breadcrumbs, search with hint, actions
<Topbar
  leadingContent={
    <Button variant="ghost" size="sm" onClick={openWorkspaceSwitcher}>
      ws_production
    </Button>
  }
  breadcrumbs={[
    { label: 'Workspace', href: '/' },
    { label: 'Individuals', onClick: () => navigate('/individuals') },
    { label: 'ind_4f3a' },
  ]}
  searchPlaceholder="Filter individuals…"
  searchHint="⌘K"
  onSearch={setQuery}
>
  <Button variant="primary" size="sm">
    <Icon name="plus" size={14} /> Create
  </Button>
</Topbar>
```

### Gotchas

- The search input is uncontrolled: there is no `value` prop, so it cannot be cleared or prefilled from outside. Debounce `onSearch` in the parent if filtering is expensive.
- Mobile mode applies when the viewport is at or below `mobileBreakpoint` (`max-width` media query). The search box unmounts (typed text is lost, `onSearch` is not called with `''`), the gap shrinks to 8px, and breadcrumbs truncate with ellipsis. Provide another search entry point, such as a `CommandPalette`, on small screens.
- `mobileBreakpoint={false}` keeps desktop layout at every width; a `data-mobile` attribute on the root overrides the built-in 768px media query, so custom breakpoints work too.
- `searchHint` is visual only (`pointer-events: none`). Register the keyboard shortcut yourself.
- The last breadcrumb gets `aria-current="page"` regardless of whether it is a link.
- Inside `ShellLayout`, below the breakpoint a menu button is prepended to `leadingContent`, and the topbar inherits ShellLayout's `mobileBreakpoint` unless the `topbar` config sets its own.

---

## TabBar

Canvas-surface horizontal tab strip with an amber underline on the active tab, optional count chips, and roving-focus keyboard navigation.

```tsx
import { TabBar } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `tabs` | `Tab[]` | `[]` | Tab definitions, in display order |
| `activeTabId` | `string` | `''` | Id of the selected tab |
| `onSelectTab` | `(tabId: string) => void` | — | Click or arrow/Home/End key selection |
| `...divProps` | | | Remaining props spread onto the root `<div role="tablist">` (ref forwarded) |

### Data types

#### Tab

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | `string` | Passed to `onSelectTab`; also the React key |
| `label` | `string` | Display text; does not wrap |
| `count` | `number` | Renders an `id-tag` Chip; `0` still renders |
| `disabled` | `boolean` | Not clickable; skipped by keyboard navigation |

### Usage

```tsx
<TabBar
  tabs={[
    { id: 'overview', label: 'Overview' },
    { id: 'details', label: 'Details' },
    { id: 'history', label: 'History' },
  ]}
  activeTabId={activeTabId}
  onSelectTab={setActiveTabId}
/>
```

```tsx
// Counts, a disabled tab, and a panel rendered by the parent
<>
  <TabBar
    aria-label="Service filters"
    tabs={[
      { id: 'all', label: 'All', count: 248 },
      { id: 'running', label: 'Running', count: 12 },
      { id: 'archived', label: 'Archived', disabled: true },
    ]}
    activeTabId={activeTabId}
    onSelectTab={setActiveTabId}
  />
  <div role="tabpanel">{activeTabId === 'running' ? <RunningServices /> : <AllServices />}</div>
</>
```

### Gotchas

- Fully controlled: the active tab only changes when the parent updates `activeTabId`.
- Keyboard selection follows focus: ←/→ (wrapping), Home and End move focus **and** call `onSelectTab`. Disabled tabs are skipped.
- Only the active tab has `tabIndex={0}`. If `activeTabId` matches no enabled tab (including the `''` default), the strip is unreachable with the Tab key; always pass a valid initial id.
- TabBar renders no panels and sets no `aria-controls`; render the content yourself.
- Disabled tabs use `aria-disabled` rather than the native `disabled` attribute and render at 50% opacity.
- Count chips turn amber on the active tab.
- Colors use canvas tokens (`--canvas-border`, `--canvas-fg-*`); TabBar belongs on the canvas, not the shell.
- Tabs do not wrap or scroll; a long tab list overflows its container.
