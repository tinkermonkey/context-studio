---
name: heimdall-overlays
description: Heimdall component guide for Overlays: Modal, ConfirmDialog, Toast, Tooltip, Popover, CommandPalette, WorkspaceSwitcherDialog, Drawer
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

None of these overlays use a portal. Modal, ConfirmDialog, CommandPalette, WorkspaceSwitcherDialog and Drawer render in place with `position: fixed`, so an ancestor with `transform`, `filter` or `contain` breaks their positioning. Tooltip and Popover position absolutely inside their own wrapper, so an ancestor with `overflow: hidden` or `overflow: auto` clips them.

For a non-modal side panel that leaves the page interactive, use `DetailDrawer` (documented in the `heimdall-graph` skill) instead of `Drawer`.

## Modal

General-purpose dialog with header, body, footer, and optional hint strip.

```tsx
import { Modal } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `isOpen` | `boolean` | required | Renders the modal when true |
| `onClose` | `() => void` | required | Called on Escape, backdrop click, or close button |
| `title` | `string` | — | Header title; header renders only when set |
| `subtitle` | `string` | — | Secondary line below title |
| `children` | `ReactNode` | required | Modal body |
| `footer` | `ReactNode` | — | Footer row, typically action buttons |
| `hintFooter` | `string` | — | Monospace hint strip below footer |
| `size` | `ModalSize` (`'sm' \| 'md' \| 'lg' \| 'xl'`) | `'md'` | Width: 360 / 480 / 640 / 820px |
| `...divProps` | | | Remaining props spread onto the `role="dialog"` `<div>` |

### Usage

```tsx
<Modal isOpen={open} onClose={() => setOpen(false)} title="Create class">
  <p>Modal body content.</p>
</Modal>
```

```tsx
<Modal
  isOpen={open}
  onClose={() => setOpen(false)}
  title="Import data"
  subtitle="428 individuals · last synced 2m ago"
  size="lg"
  footer={
    <>
      <span style={{ flex: 1 }} />
      <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
      <Button variant="primary" size="sm" onClick={handleImport}>Import</Button>
    </>
  }
  hintFooter="↵ confirm  esc close"
>
  <Field label="Source">
    <TextInput placeholder="s3://bucket/path" mono />
  </Field>
</Modal>
```

### Gotchas

- Fully controlled: the modal never closes itself. Every close path calls `onClose`; you set `isOpen` to false.
- Returns `null` when closed, so body state (form inputs) resets on every open.
- The header, including the close button, renders only when `title` is set. Without `title` the only close paths are Escape and backdrop click.
- On open, focus moves to the first focusable element. With a `title`, that is the header close button, not the first form field. Focus returns to the previously focused element on close.
- Tab is trapped inside the dialog and body scroll is locked while open.
- Backdrop click closes only when the click lands on the backdrop itself, not on the dialog.
- Escape is a `document` listener. Two open modals (or a Modal over a Drawer) both close on one Escape press.
- The footer is a left-aligned flex row with an 8px gap. Add a `flex: 1` spacer (as above) to right-align buttons.
- The dialog caps at `90%` width and `90vh` height and scrolls internally (`overflow: auto`), which also clips any Tooltip or Popover inside it.

---

## ConfirmDialog

Two-button confirmation built on `Modal`. Defaults to the `danger` variant.

```tsx
import { ConfirmDialog } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `isOpen` | `boolean` | required | Renders the dialog when true |
| `onClose` | `() => void` | required | Cancel button, Escape, backdrop, close button |
| `onConfirm` | `() => void` | required | Confirm button handler |
| `title` | `string` | — | Dialog title; header renders only when set |
| `subtitle` | `string` | — | Secondary line below title |
| `message` | `ReactNode` | required | Consequence description |
| `confirmLabel` | `string` | `'Confirm'` | Confirm button text |
| `cancelLabel` | `string` | `'Cancel'` | Cancel button text |
| `variant` | `ConfirmDialogVariant` (`'primary' \| 'danger'`) | `'danger'` | Confirm button variant |

### Usage

```tsx
<ConfirmDialog
  isOpen={open}
  onClose={() => setOpen(false)}
  onConfirm={() => { deleteClass('cls_organism'); setOpen(false) }}
  title="Delete class"
  message={<>Delete <code>cls_organism</code>? 47 individuals will be unlinked.</>}
  confirmLabel="Delete"
/>
```

```tsx
<ConfirmDialog
  isOpen={open}
  onClose={() => setOpen(false)}
  onConfirm={() => { deploy(); setOpen(false) }}
  title="Deploy to production"
  subtitle="svc_ingest · build 4f3a"
  message="Active connections will restart."
  confirmLabel="Deploy"
  cancelLabel="Keep current"
  variant="primary"
/>
```

### Gotchas

- `onConfirm` does not close the dialog. Set `isOpen` to false inside the handler.
- `onClose` covers Cancel, Escape, backdrop click and the header close button; it does not close by itself either.
- Inherits Modal behavior: focus trap, scroll lock, and initial focus on the header close button when `title` is set (otherwise on the Cancel button).
- No rest props: `className`, `style` and other DOM attributes are not accepted.

---

## Toast

Single dismissible notification with optional auto-dismiss. Does not position itself.

```tsx
import { Toast } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `isOpen` | `boolean` | required | Renders the toast when true |
| `onClose` | `() => void` | required | Called on auto-dismiss or dismiss button |
| `title` | `string` | — | Primary message |
| `subtitle` | `string` | — | Secondary detail |
| `variant` | `ToastVariant` (`'success' \| 'error' \| 'warning' \| 'info'`) | `'info'` | Icon, color and ARIA role preset |
| `icon` | `IconName` | — | Overrides the variant icon |
| `duration` | `number` | `4000` | Auto-dismiss delay in ms; `0` disables |
| `...divProps` | | | Remaining props spread onto the root `<div>` |

### Usage

```tsx
<Toast
  isOpen={toastOpen}
  onClose={() => setToastOpen(false)}
  title="Pipeline complete"
  variant="success"
  style={{ position: 'fixed', bottom: 24, right: 24 }}
/>
```

```tsx
// Stacked toasts: fixed container, error stays until dismissed
<div style={{ position: 'fixed', bottom: 24, right: 24, display: 'flex', flexDirection: 'column', gap: 8, zIndex: 300 }}>
  <Toast
    isOpen={syncFailed}
    onClose={closeSyncToast}
    title="Sync failed"
    subtitle="svc_ingest timed out after 30s."
    variant="error"
    duration={0}
  />
  <Toast
    isOpen={pulling}
    onClose={closePullToast}
    title="Pulling image"
    subtitle="registry/svc_ingest:4f3a"
    icon="download"
  />
</div>
```

### Gotchas

- Position it yourself: the root is `position: relative` with `max-width: 400px`. Pass `style` for one toast, or wrap several in a fixed flex column.
- Variant icons: success `check`, error `x`, warning `alert`, info `info`. Colors: emerald, rose, amber, cyan.
- `error` and `warning` render `role="alert"` with `aria-live="assertive"`; the others `role="status"` with `aria-live="polite"`.
- The auto-dismiss timer restarts whenever `onClose` changes identity. An inline arrow in a parent that re-renders often keeps postponing the dismissal; pass a stable callback (`useCallback`).
- `duration={0}` keeps the toast open until the dismiss button is clicked. The dismiss button always renders.
- There is no queue. Manage which toasts are open in your own state.

---

## Tooltip

Short hover/focus hint attached to a single child element.

```tsx
import { Tooltip } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `content` | `ReactNode` | required | Tooltip body; `null`/`undefined` shows nothing |
| `children` | `ReactElement` | required | Single trigger element |
| `placement` | `TooltipPlacement` (`'top' \| 'bottom' \| 'left' \| 'right'`) | `'top'` | Preferred side; flips at viewport edge |
| `delay` | `number` | `200` | Show delay in ms (uncontrolled only) |
| `offset` | `number` | `6` | Gap between trigger and tooltip in px |
| `className` | `string` | `''` | Extra class on the tooltip card |
| `disabled` | `boolean` | `false` | Suppresses the tooltip |
| `open` | `boolean` | — | Controlled visibility; ignores hover and focus |
| `id` | `string` | auto (`useId`) | Tooltip element id |

### Usage

```tsx
<Tooltip content="Reload schema">
  <Button variant="ghost" size="sm" aria-label="Reload schema">
    <Icon name="reload" size={14} />
  </Button>
</Tooltip>
```

```tsx
<Tooltip
  content={<><code>cls_4f3a</code> · 47 individuals</>}
  placement="right"
  delay={0}
  offset={10}
  disabled={!showHints}
>
  <span className="font-mono">life.organism</span>
</Tooltip>

// Controlled: visibility follows `open` only
<Tooltip content="Unsaved changes" open={isDirty} placement="bottom">
  <Button variant="primary" size="sm">Save</Button>
</Tooltip>
```

### Gotchas

- Wraps `children` in an inline-flex `<span>` that listens for pointer enter/leave and focus/blur. A block-level child no longer stretches to full width.
- `children` must be a single React element. It receives `aria-describedby` while the tooltip is visible.
- The card is `position: absolute` inside the wrapper (`z-index: 300`, `max-width: 240px`). Ancestors with `overflow: hidden` or `auto` (Panel, Modal, SplitPane panes, table cells) clip it.
- Edge handling only flips to the opposite side (top↔bottom, left↔right); a top tooltip near the left edge is not shifted horizontally.
- With `open` set, `delay` has no effect and there is no change callback; drive `open` from your own state.
- The card uses shell colors (dark) in both canvas modes.
- Not interactive: it hides when the pointer leaves the trigger. Use Popover for clickable content.

---

## Popover

Click-to-open non-modal panel anchored to a trigger. Compound component: `Popover` + `Popover.Trigger` + `Popover.Panel`.

```tsx
import { Popover } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `children` | `ReactNode` | required | `Popover.Trigger` and `Popover.Panel` |
| `placement` | `PopoverPlacement` (`'top' \| 'bottom' \| 'left' \| 'right'`) | `'bottom'` | Preferred side; flips at viewport edge |
| `offset` | `number` | `8` | Gap between trigger and panel in px |
| `open` | `boolean` | — | Controlled open state; requires `onOpenChange` |
| `onOpenChange` | `(open: boolean) => void` | — | Open-state change handler; required with `open` |
| `disableOutsideClick` | `boolean` | `false` | Keep open on outside mousedown |
| `panelId` | `string` | auto (`useId`) | Panel element id |
| `autoFocus` | `boolean` | `false` | Focus first focusable panel element on open |

### Usage

```tsx
<Popover>
  <Popover.Trigger>
    <Button variant="secondary" size="sm">Details</Button>
  </Popover.Trigger>
  <Popover.Panel aria-label="Class details">
    <div style={{ padding: 12 }}>
      <code>cls_organism</code> · 47 individuals
    </div>
  </Popover.Panel>
</Popover>
```

```tsx
const [open, setOpen] = useState(false)

<Popover open={open} onOpenChange={setOpen} placement="right" offset={12} autoFocus>
  <Popover.Trigger>
    <Button variant="ghost" size="sm" aria-label="Rename class">
      <Icon name="edit" size={14} />
    </Button>
  </Popover.Trigger>
  <Popover.Panel aria-labelledby="rename-title" className="rename-popover">
    <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div id="rename-title">Rename class</div>
      <TextInput defaultValue="life.organism" mono />
      <Button variant="primary" size="sm" onClick={() => setOpen(false)}>Save</Button>
    </div>
  </Popover.Panel>
</Popover>
```

### Compound subcomponents

#### Popover.Trigger

Clones its single child and wires click and Enter/Space to toggle the panel, plus `aria-haspopup`, `aria-expanded` and `aria-controls`.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `children` | `ReactElement` | required | Single focusable element that accepts a ref |

#### Popover.Panel

The floating `role="dialog"` panel. Renders nothing while closed.

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `children` | `ReactNode` | required | Panel content |
| `aria-label` | `string` | — | Accessible name for the dialog |
| `aria-labelledby` | `string` | — | Id of the element naming the dialog |
| `className` | `string` | `''` | Extra class on the panel |

### Gotchas

- `Popover.Trigger` and `Popover.Panel` throw outside a `Popover`.
- The trigger child must forward refs (Heimdall `Button` does) and accept `onClick`/`onKeyDown`. Its own handlers still run. Its `id` is replaced with a generated one.
- Controlled mode: `open` without `onOpenChange` is a type error and logs a console warning; the popover stays stuck. Omit both for uncontrolled mode.
- Closes on Escape (focus returns to the trigger) and on any mousedown outside the wrapper unless `disableOutsideClick`. Escape is stopped at the wrapper, so a Popover inside a Modal closes without closing the Modal.
- Tab wraps inside the open panel. Focus moves into the panel only with `autoFocus`.
- The panel has no padding; add your own. It uses shell colors (dark) in both canvas modes, `min-width: 200px`, `max-width: 360px`, `z-index: 1000`.
- The panel is `position: absolute` in an inline-flex wrapper, so `overflow: hidden`/`auto` ancestors (Panel, Modal) clip it. Edge handling only flips to the opposite side.
- Remounts panel content on every open; keep form state outside the panel if it must persist.

---

## CommandPalette

Keyboard-driven command launcher with substring search and optional groups.

```tsx
import { CommandPalette } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `isOpen` | `boolean` | required | Renders the palette when true |
| `onClose` | `() => void` | required | Escape, backdrop click, or after a selection |
| `commands` | `Command[]` | `[]` | Available commands |
| `placeholder` | `string` | `'Search commands…'` | Input placeholder and aria-label |
| `emptyMessage` | `string` | `'No commands found'` | Shown when nothing matches |

### Data types

```ts
interface Command {
  id: string          // unique; used in element ids
  label: string
  description?: string
  icon?: IconName
  group?: string      // section header; groups render in first-appearance order
  onSelect: () => void
}
```

### Usage

```tsx
<CommandPalette
  isOpen={paletteOpen}
  onClose={() => setPaletteOpen(false)}
  commands={[
    { id: 'create_class', label: 'Create class', icon: 'plus', onSelect: () => navigate('/schema/new') },
    { id: 'run_pipeline', label: 'Run pipeline', icon: 'pipeline', onSelect: runPipeline },
  ]}
/>
```

```tsx
const commands: Command[] = [
  { id: 'nav_graph', label: 'Graph view', description: 'Switch to graph visualization', icon: 'graph', group: 'Navigate', onSelect: () => navigate('/graph') },
  { id: 'nav_settings', label: 'Open settings', icon: 'settings', group: 'Navigate', onSelect: () => navigate('/settings') },
  { id: 'act_export', label: 'Export data', description: 'Download current view as CSV', icon: 'download', group: 'Actions', onSelect: exportCsv },
]

useEffect(() => {
  const onKey = (e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); setPaletteOpen(true) }
  }
  document.addEventListener('keydown', onKey)
  return () => document.removeEventListener('keydown', onKey)
}, [])

<CommandPalette
  isOpen={paletteOpen}
  onClose={() => setPaletteOpen(false)}
  commands={commands}
  placeholder="Search or run command…"
  emptyMessage="No commands match."
/>
```

### Gotchas

- No built-in shortcut: bind ⌘K / Ctrl+K yourself (as above).
- Selecting a command (click or Enter) calls `onSelect()` and then `onClose()`; do not close it again in `onSelect`.
- Search is a case-insensitive substring match on `label` and `description` only, not `group`.
- ArrowUp/ArrowDown wrap around; typing resets the selection to the first match. The search and selection reset when the palette closes.
- Commands are grouped by first appearance of each `group`; ungrouped commands form a header-less section in their position. Keyboard order follows the `commands` array, so keep each group's commands contiguous.
- `id` must be unique; it builds the option element ids used by `aria-activedescendant`.
- Focus moves to the input on open; Tab is trapped and body scroll is locked. No `className`/`style` passthrough.

---

## WorkspaceSwitcherDialog

Modal for switching workspaces: optional action tiles plus a recent-workspace list.

```tsx
import { WorkspaceSwitcherDialog } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `isOpen` | `boolean` | required | Renders the dialog when true |
| `onClose` | `() => void` | required | Escape, backdrop, or close button |
| `onPickRecent` | `(workspace: Workspace) => void` | required | Recent workspace clicked |
| `title` | `string` | `'Switch Workspace'` | Dialog heading |
| `current` | `Workspace` | — | Active workspace; marked "open" in the list |
| `recent` | `Workspace[]` | `[]` | Recent workspaces |
| `onOpenFolder` | `() => void` | — | Shows the "Open folder…" tile |
| `onNewWorkspace` | `() => void` | — | Shows the "New workspace…" tile |
| `onCloneFromGit` | `() => void` | — | Shows the "Clone from git…" tile |

### Data types

```ts
interface Workspace {
  id: string
  name: string
  path?: string
  classCount?: number       // rendered as "14 cls"
  individualCount?: number  // rendered as "302 ind"
}
```

### Usage

```tsx
<WorkspaceSwitcherDialog
  isOpen={open}
  onClose={() => setOpen(false)}
  recent={workspaces}
  onPickRecent={ws => { switchWorkspace(ws.id); setOpen(false) }}
/>
```

```tsx
const workspaces: Workspace[] = [
  { id: 'ws_prod', name: 'prod_ontology', path: '~/workspaces/prod_ontology', classCount: 14, individualCount: 302 },
  { id: 'ws_staging', name: 'staging_ontology', path: '~/workspaces/staging_ontology', classCount: 12, individualCount: 145 },
]

<WorkspaceSwitcherDialog
  isOpen={open}
  onClose={() => setOpen(false)}
  title="Switch workspace"
  current={workspaces[0]}
  recent={workspaces}
  onPickRecent={ws => { switchWorkspace(ws.id); setOpen(false) }}
  onOpenFolder={() => { setOpen(false); openFolderPicker() }}
  onNewWorkspace={() => { setOpen(false); navigate('/workspaces/new') }}
  onCloneFromGit={() => { setOpen(false); openCloneDialog() }}
/>
```

### Gotchas

- None of the callbacks close the dialog; set `isOpen` to false yourself.
- Each action tile renders only when its callback is provided; with none, the tile row is omitted.
- The "open" badge goes on the `recent` entry whose `id` equals `current.id`. `current` is not rendered on its own, so include it in `recent` to show it.
- An empty `recent` hides the "Recent" section entirely; there is no empty-state message.
- Always `size="lg"` (640px) Modal with a title, so initial focus lands on the header close button.
- The default title is title case (`'Switch Workspace'`); pass `title="Switch workspace"` for sentence case.

---

## Drawer

Modal slide-in side panel with backdrop, optional title, and configurable edge and width.

```tsx
import { Drawer } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `isOpen` | `boolean` | required | Shows the drawer when true |
| `onClose` | `() => void` | required | Escape, backdrop click, or close button |
| `children` | `ReactNode` | required | Drawer body |
| `title` | `string` | — | Header title; close button renders regardless |
| `position` | `'left' \| 'right'` | `'right'` | Edge it slides in from |
| `width` | `string` | `'320px'` | Any CSS length |
| `keepMounted` | `boolean` | `false` | Hide instead of unmount when closed |
| `...divProps` | | | Remaining props spread onto the drawer `<div role="dialog">` |

### Usage

```tsx
<Drawer isOpen={open} onClose={() => setOpen(false)} title="Record details">
  <KVGrid rows={[{ key: 'Identifier', value: <code>cls_4f3a</code> }]} />
</Drawer>
```

```tsx
<Drawer
  isOpen={filtersOpen}
  onClose={() => setFiltersOpen(false)}
  title="Filters"
  position="left"
  width="min(380px, 100vw)"
  keepMounted
  className="filters-drawer"
>
  <Field label="Domain">
    <TextInput placeholder="life" mono />
  </Field>
</Drawer>
```

### Gotchas

- Modal behavior: backdrop, Tab trapped inside, body scroll locked, focus moved to the first focusable element (the close button) on open. Use `DetailDrawer` for a non-modal panel.
- The close button always renders; without `title` the header shrinks to a right-aligned close button.
- Without `keepMounted` the drawer unmounts on close and children lose state. With `keepMounted` it stays in the DOM under a `display: none` backdrop, so inputs and scroll position survive.
- `style` replaces the inline `width` style; set width through `width`, not `style.width`.
- `width` is not responsive; use `min(…, 100vw)` on narrow screens.
- Body has 16px padding and scrolls vertically.
- Escape is a `document` listener, so a Modal opened from inside a Drawer closes both on one Escape press.
