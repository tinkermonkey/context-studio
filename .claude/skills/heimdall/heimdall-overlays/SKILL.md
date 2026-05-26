---
name: heimdall-overlays
description: Heimdall component guide for Overlays: Modal, ConfirmDialog, Toast, CommandPalette, WorkspaceSwitcherDialog, Drawer
---

Import all components from `@tinkermonkey/heimdall-ui`. Import the CSS once at your app entry point:

```tsx
import '@tinkermonkey/heimdall-ui/css'
```

## Modal

General-purpose dialog with header, body, footer, and optional hint strip.

```tsx
import { Modal } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `isOpen` | `boolean` | required | Controls visibility |
| `onClose` | `() => void` | required | Called on Escape, backdrop click, or close button |
| `title` | `string` | — | Header title |
| `subtitle` | `string` | — | Secondary line below title |
| `children` | `ReactNode` | required | Modal body |
| `footer` | `ReactNode` | — | Footer slot (typically action buttons) |
| `hintFooter` | `string` | — | Monospace hint strip below footer |
| `size` | `'sm' \| 'md' \| 'lg' \| 'xl'` | `'md'` | Width: sm=360px, md=480px, lg=640px, xl=820px |

### Usage

```tsx
// Minimal
<Modal isOpen={open} onClose={() => setOpen(false)} title="Create entity">
  <p>Modal body content.</p>
</Modal>
```

```tsx
// With footer and hint
<Modal
  isOpen={open}
  onClose={() => setOpen(false)}
  title="Import data"
  subtitle="428 individuals · last synced 2m ago"
  size="lg"
  footer={
    <div className="flex gap-2 justify-end">
      <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
      <Button variant="primary" onClick={handleImport}>Import</Button>
    </div>
  }
  hintFooter="↵ confirm  esc close"
>
  {/* form content */}
</Modal>
```

### Gotchas

- Focus is automatically trapped inside when open (`useFocusTrap`)
- Body scroll is blocked when open (`useBodyOverflow`)
- Close button in the header only renders when `title` is provided
- Backdrop click triggers `onClose` only when clicking the backdrop itself, not child elements

---

## ConfirmDialog

Specialized two-button confirmation dialog. Default variant is `'danger'` (red confirm button).

```tsx
import { ConfirmDialog } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `isOpen` | `boolean` | required | Controls visibility |
| `onClose` | `() => void` | required | Cancel handler |
| `onConfirm` | `() => void` | required | Confirm handler |
| `title` | `string` | — | Dialog title |
| `subtitle` | `string` | — | Secondary line below title |
| `message` | `ReactNode` | required | Consequence description |
| `confirmLabel` | `string` | `'Confirm'` | Confirm button text |
| `cancelLabel` | `string` | `'Cancel'` | Cancel button text |
| `variant` | `'primary' \| 'danger'` | `'danger'` | Confirm button color |

### Usage

```tsx
<ConfirmDialog
  isOpen={open}
  onClose={() => setOpen(false)}
  onConfirm={() => { deleteEntity(); setOpen(false) }}
  title="Delete entity"
  message={<>Delete <code>cls_organism</code>? 47 individuals will be unlinked.</>}
  confirmLabel="Delete"
/>
```

```tsx
// Primary variant (non-destructive confirmation)
<ConfirmDialog
  isOpen={open}
  onClose={() => setOpen(false)}
  onConfirm={() => { deploy(); setOpen(false) }}
  title="Deploy to production"
  message="This will push the current build to the production environment."
  confirmLabel="Deploy"
  variant="primary"
/>
```

### Gotchas

- `onConfirm` does **not** auto-close — you must call `setOpen(false)` inside your `onConfirm` handler
- `onClose` is wired to the Cancel button and does auto-close
- Always wraps `Modal`; inherits Escape key, backdrop click, and focus trap behavior

---

## Toast

Auto-dismissing notification. Positioned via `style` prop — the component does not self-position.

```tsx
import { Toast } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `isOpen` | `boolean` | required | Controls visibility |
| `onClose` | `() => void` | required | Called after auto-dismiss or dismiss button click |
| `title` | `string` | — | Primary message |
| `subtitle` | `string` | — | Secondary detail |
| `variant` | `'success' \| 'error' \| 'warning' \| 'info'` | `'info'` | Color and icon preset |
| `icon` | `IconName` | — | Overrides variant's default icon |
| `duration` | `number` | `4000` | Auto-dismiss delay in ms; `0` disables auto-dismiss |

### Usage

```tsx
// Positioned at bottom-right
<Toast
  isOpen={toastOpen}
  onClose={() => setToastOpen(false)}
  title="Pipeline complete"
  subtitle="1,234 records processed."
  variant="success"
  style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 9999 }}
/>
```

```tsx
// Error that stays open until dismissed
<Toast
  isOpen={toastOpen}
  onClose={() => setToastOpen(false)}
  title="Sync failed"
  subtitle="Connection timeout after 30s."
  variant="error"
  duration={0}
  style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 9999 }}
/>
```

### Gotchas

- **You must position the Toast yourself** using `style` — it has no built-in fixed positioning
- `duration={0}` disables auto-dismiss; the user must click the dismiss button
- `variant` controls both color (emerald/rose/amber/cyan) and ARIA role (`role="alert"` for error/warning, `role="status"` for others)

---

## CommandPalette

Full-screen command search overlay with fuzzy text filter and keyboard navigation.

```tsx
import { CommandPalette } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `isOpen` | `boolean` | required | Controls visibility |
| `onClose` | `() => void` | required | Called on Escape or backdrop click |
| `commands` | `Command[]` | `[]` | Available commands |
| `placeholder` | `string` | `'Search commands…'` | Search input placeholder |
| `emptyMessage` | `string` | `'No commands found'` | Message when no results match |

```ts
interface Command {
  id: string
  label: string
  description?: string
  icon?: IconName
  onSelect: () => void
}
```

### Usage

```tsx
<CommandPalette
  isOpen={paletteOpen}
  onClose={() => setPaletteOpen(false)}
  commands={[
    { id: 'create', label: 'Create class', description: 'Add a new schema class', icon: 'plus', onSelect: () => navigate('/schema/new') },
    { id: 'run', label: 'Run pipeline', icon: 'pipeline', onSelect: () => runPipeline() },
    { id: 'settings', label: 'Open settings', icon: 'settings', onSelect: () => navigate('/settings') },
  ]}
/>
```

### Gotchas

- Search input auto-focuses when `isOpen` becomes true
- Fuzzy search is simple substring match on `label` and `description` (case-insensitive)
- Arrow keys wrap around: Up at index 0 goes to last command
- Enter executes the selected command, calls `onSelect()`, and closes the palette
- Typing resets the selected index to 0
- Focus is trapped and body scroll is blocked while open

---

## WorkspaceSwitcherDialog

Modal for switching between workspaces, with recent workspace list and optional action tiles.

```tsx
import { WorkspaceSwitcherDialog } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `isOpen` | `boolean` | required | Controls visibility |
| `onClose` | `() => void` | required | Called when dialog should close |
| `title` | `string` | `'Switch Workspace'` | Dialog heading |
| `current` | `Workspace` | — | Currently active workspace (highlighted with "open" badge) |
| `recent` | `Workspace[]` | `[]` | List of recent workspaces |
| `onPickRecent` | `(workspace: Workspace) => void` | required | Called when a recent workspace is selected |
| `onOpenFolder` | `() => void` | — | When provided, renders "Open folder…" action tile |
| `onNewWorkspace` | `() => void` | — | When provided, renders "New workspace…" action tile |
| `onCloneFromGit` | `() => void` | — | When provided, renders "Clone from git…" action tile |

```ts
interface Workspace {
  id: string
  name: string
  path?: string
  classCount?: number
  individualCount?: number
}
```

### Usage

```tsx
<WorkspaceSwitcherDialog
  isOpen={open}
  onClose={() => setOpen(false)}
  current={{ id: 'ws-1', name: 'Production', path: '/workspaces/prod' }}
  recent={[
    { id: 'ws-1', name: 'Production', path: '/workspaces/prod', classCount: 14, individualCount: 302 },
    { id: 'ws-2', name: 'Staging', path: '/workspaces/staging', classCount: 12, individualCount: 145 },
  ]}
  onPickRecent={ws => { switchWorkspace(ws); setOpen(false) }}
  onOpenFolder={() => openFolderPicker()}
  onNewWorkspace={() => navigate('/new')}
/>
```

### Gotchas

- Action tiles only render when their corresponding callback prop is provided
- `onPickRecent` is required and does not auto-close — you must call `setOpen(false)` inside it
- Action callbacks (onOpenFolder, etc.) also do not auto-close — call `setOpen(false)` there too
- The "open" badge appears on the workspace whose `id` matches `current?.id`

---

## Drawer

Slide-in side panel with optional title, configurable edge, and custom width.

```tsx
import { Drawer } from '@tinkermonkey/heimdall-ui'
```

### Props

| Prop | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `isOpen` | `boolean` | required | Controls visibility |
| `onClose` | `() => void` | required | Called on Escape or backdrop click |
| `title` | `string` | — | Header title; omit for titleless drawer |
| `position` | `'left' \| 'right'` | `'right'` | Which edge to slide in from |
| `width` | `string` | `'320px'` | Width as any CSS length |
| `children` | `ReactNode` | required | Drawer body |
| `...HTMLAttributes` | | | Standard div attributes |

### Usage

```tsx
// Right drawer (default)
<Drawer isOpen={open} onClose={() => setOpen(false)} title="Record details">
  <KVGrid rows={metadataRows} />
</Drawer>
```

```tsx
// Left navigation drawer
<Drawer
  isOpen={open}
  onClose={() => setOpen(false)}
  title="Filters"
  position="left"
  width="380px"
>
  {/* filter controls */}
</Drawer>
```

```tsx
// Titleless drawer
<Drawer isOpen={open} onClose={() => setOpen(false)}>
  {/* custom header rendered inside */}
</Drawer>
```

### Gotchas

- The close button (×) always renders regardless of whether `title` is provided
- `width` accepts any valid CSS length: `'320px'`, `'50vw'`, `'400px'`
- Focus is trapped and body scroll is blocked while open
