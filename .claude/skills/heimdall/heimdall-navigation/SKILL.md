---
name: heimdall-navigation
description: Heimdall component guide for Navigation: NavItem, Sidebar, Topbar, TabBar
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## NavItem

Single navigation entry rendered as a button, with optional icon, count badge, and active state.

```tsx
import { NavItem } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `label` | `string` | required | Display text |
| `icon` | `IconName` | — | Icon left of label (top-level only; ignored at depth=1) |
| `count` | `number` | — | Badge count shown right-aligned |
| `active` | `boolean` | `false` | Amber left border + shell-surface background |
| `depth` | `0 \| 1` | `0` | Indentation; depth=1 is a sub-item, never shows icon |
| `...ButtonHTMLAttributes` | | | Standard button attributes |

### Usage

```tsx
// Top-level item
<NavItem
  icon="dashboard"
  label="Dashboard"
  active={activeId === 'dashboard'}
  onClick={() => setActiveId('dashboard')}
/>
```

```tsx
// With count and sub-item
<NavItem icon="schema" label="Schema" count={128} active={activeId === 'schema'} onClick={() => setActiveId('schema')} />
<NavItem label="life.organism" depth={1} count={42} active={activeId === 'cls-organism'} onClick={() => setActiveId('cls-organism')} />
```

### Gotchas

- `icon` is silently ignored when `depth={1}` — sub-items never show icons
- Sets `aria-current="page"` when `active={true}`
- Labels truncate with ellipsis on overflow

---

## Sidebar

Full left-navigation panel with collapsible sections, child item expansion, and 256px/64px width toggle.

```tsx
import { Sidebar } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `sections` | `SidebarSection[]` | required | Array of section groups |
| `activeItemId` | `string` | — | ID of currently active item |
| `collapsed` | `boolean` | `false` | Collapsed (icon-only) mode |
| `onCollapse` | `(collapsed: boolean) => void` | — | Called when toggle button clicked |
| `onSelectItem` | `(itemId: string) => void` | — | Called when a non-parent item is clicked |
| `...HTMLAttributes` | | | Standard div attributes |

```ts
interface SidebarSection {
  title: string
  items: SidebarItem[]
}

interface SidebarItem {
  id: string
  label: string
  icon?: IconName
  count?: number
  children?: Array<{ id: string; label: string; count?: number }>
}
```

### Usage

```tsx
<Sidebar
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
            { id: 'cls-organism', label: 'life.organism', count: 42 },
            { id: 'cls-cell', label: 'life.cell', count: 18 },
          ],
        },
      ],
    },
    {
      title: 'Tools',
      items: [{ id: 'settings', label: 'Settings', icon: 'settings' }],
    },
  ]}
  activeItemId="cls-organism"
  collapsed={collapsed}
  onCollapse={setCollapsed}
  onSelectItem={setActiveItemId}
/>
```

### Gotchas

- Clicking a parent item with children **toggles expansion** — `onSelectItem` is NOT called for parent items
- Child expand/collapse state is managed internally; the parent does not need to track it
- In collapsed mode: labels, counts, section titles, and child items are all hidden — only top-level icons remain
- `collapsed` is controlled by the parent; Sidebar itself does not persist collapse state

---

## Topbar

Above-content header bar with breadcrumb navigation, optional search input, and a right-side action slot.

```tsx
import { Topbar } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `breadcrumbs` | `BreadcrumbItem[]` | — | Array of breadcrumb items |
| `searchPlaceholder` | `string` | `'Search…'` | Placeholder for search input |
| `onSearch` | `(query: string) => void` | — | When provided, renders a search input |
| `children` | `ReactNode` | — | Custom actions in right slot |
| `...HTMLAttributes` | | | Standard div attributes |

```ts
interface BreadcrumbItem {
  label: string
  href?: string      // renders as <a>
  onClick?: () => void  // renders as <button>
  // neither href nor onClick → renders as static <span>
}
```

### Usage

```tsx
// Static breadcrumbs
<Topbar
  breadcrumbs={[
    { label: 'Workspace' },
    { label: 'Schema' },
    { label: 'life.organism' },
  ]}
/>
```

```tsx
// Linked breadcrumbs, search, and actions
<Topbar
  breadcrumbs={[
    { label: 'Workspace', href: '/' },
    { label: 'Individuals' },
  ]}
  searchPlaceholder="Filter individuals…"
  onSearch={setQuery}
>
  <Button variant="primary" size="sm">
    <Icon name="plus" size={14} /> Create
  </Button>
</Topbar>
```

### Gotchas

- `onSearch` fires on every keystroke — debounce in the parent if needed
- The search input only renders if `onSearch` is provided
- Last breadcrumb automatically receives `aria-current="page"`

---

## TabBar

Horizontal tab strip with ARIA-compliant keyboard navigation and optional count badges.

```tsx
import { TabBar } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `tabs` | `Tab[]` | `[]` | Array of tab definitions |
| `activeTabId` | `string` | `''` | ID of the active tab |
| `onSelectTab` | `(tabId: string) => void` | — | Called when tab is clicked or keyboard-selected |
| `...HTMLAttributes` | | | Standard div attributes |

```ts
interface Tab {
  id: string
  label: string
  count?: number
  disabled?: boolean
}
```

### Usage

```tsx
// Minimal
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
// With counts and disabled tabs
<TabBar
  tabs={[
    { id: 'all', label: 'All', count: 248 },
    { id: 'running', label: 'Running', count: 12 },
    { id: 'stopped', label: 'Stopped', count: 0, disabled: true },
  ]}
  activeTabId={activeTabId}
  onSelectTab={setActiveTabId}
/>
```

### Gotchas

- Arrow keys (←/→) navigate between enabled tabs; disabled tabs are skipped entirely
- Home/End jump to first/last enabled tab
- Count badges render as `Chip` with `form="id-tag"` internally; they turn amber when the tab is active
- Only the active tab has `tabIndex={0}`; all others use `tabIndex={-1}`
