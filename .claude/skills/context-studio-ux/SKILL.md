---
name: context-studio-ux
description: Entry-point skill for all Context Studio frontend work. Covers the Heimdall design system, the reference design prototype, the page-component map, CSS architecture, and customization rules.
---

# Context Studio UX — Heimdall Design System Guide

**Read this skill before touching any UX code.** It is the entry point that tells you what to look at, what to reach for, and what not to build from scratch.

---

## 1. The Reference Design

The design team rebuilt the Context Studio prototype using **real `@tinkermonkey/heimdall-ui` React components**. Every JSX tag in the prototype maps 1:1 to a production import — this is a spec-grade handoff, not a visual mock.

### Files

| File | What it is |
|---|---|
| `ux/design/Context Studio.html` | Open in a browser — no build step. Boots Heimdall then renders all pages. |
| `ux/design/cs/app.jsx` | Shell, routing, overlays (CommandPalette, Modal, Toast, Statusbar) |
| `ux/design/cs/pages.jsx` | All 9 page components using real Heimdall imports |
| `ux/design/HEIMDALL_REBUILD.md` | 8 known findings: icon remaps, sidebar quirks, Toast positioning, CommandPalette grouping — read before filing bugs or building workarounds |
| `ux/design/heimdall/components/` | 77 Heimdall source files (`.tsx` + `.css`) — authoritative component source |

### How to use it

1. Open `ux/design/Context Studio.html` in a browser (or take a screenshot with MCP tools)
2. Navigate to the relevant page
3. Find the corresponding component in `cs/pages.jsx` or `cs/app.jsx`
4. Copy the JSX
5. In production, replace bare component references with a single import: `import { ... } from '@tinkermonkey/heimdall-ui'`

The JSX compiles as-is in the Vite build. The only difference between prototype and production is the import line.

### Known icon remaps (prototype data → valid IconName)

The prototype's CS_DATA uses icon names that aren't in the Heimdall icon set. These are the correct substitutions:

```
reference → link
sparkle   → zap
doc       → file
database  → hardDrive
folder    → hardDrive  (no folder icon — use hardDrive as substitute)
tag       → component  (no tag icon — use component as substitute)
```

---

## 2. The Two-Surface Model

Context Studio renders on two distinct surfaces that must never be mixed:

**Shell** — always dark slate navy, regardless of canvas mode:
- `Sidebar`, `Topbar`, `Statusbar`, `Titlebar`, `AppTitle`
- CSS token prefix: `--shell-*`
- Never put canvas-colored content or canvas tokens in shell components

**Canvas** — light by default; toggled dark via `body.dark-canvas`:
- All page content: `Panel`, `Table`, `StatGrid`, `PageHeader`, etc.
- CSS token prefix: `--canvas-*`

### Token usage — critical

Heimdall CSS variables store **raw RGB channel values**, not complete color values. They **must** be wrapped in `rgb()`:

```css
/* correct */
color: rgb(var(--canvas-fg-1));
background: rgb(var(--canvas-bg));
border: 1px solid rgb(var(--canvas-border));

/* broken — produces invalid CSS: "color: 11 18 32" */
color: var(--canvas-fg-1);
```

This applies to all `--shell-*`, `--canvas-*`, `--accent-*`, and `--status-*` tokens.

### Accent colors

- `--accent-primary` is **amber** (`#fbbf24`) — Heimdall's native accent
- `--accent-cyan` (from `app-overrides.css`) — the app's cyan palette
- Use `--accent-cyan` explicitly when you want cyan; never assume `--accent-primary` is cyan

---

## 3. Page → Component Map

Use this to know which Heimdall component to reach for on each page.

### Dashboard (`/app/index.tsx`)
```
PageHeader         — eyebrow, title, idChip, subtitle, actions (Fragment with Buttons)
StatGrid(columns=4)
  └── StatTile     — label, value, color, icon, delta, sparkData, meta
Panel              — "Knowledge graph structure" with headerAction
  └── HierarchyTree / HierarchyRow   — taxonomy → scheme → class tree
Panel              — "Recent activity" with headerAction
  └── ActivityTimeline               — chronological event list
PipelineCard (×N)  — active pipelines with flow steps
QuickAccessGrid    — 6 tiles for common nav shortcuts
  └── QuickAccessTile
```

### Schema · Taxonomies (`/app/schema/taxonomies.tsx`)
```
PageHeader
TabBar             — shared across all schema/* pages
Panel(noPadding)
  └── Table        — id, title, description, classes count, individuals count, version
        └── VersionPill (cell render)
```

### Schema · Concept Schemes (`/app/schema/schemes.tsx`)
```
PageHeader
TabBar
Panel(noPadding)
  └── Table        — id, title, description, taxonomy (Chip), classes count, version
        └── Chip (cell render)
        └── VersionPill (cell render)
```

### Schema · Classes (`/app/schema/classes.tsx`) — keystone page
```
PageHeader
TabBar
TextInput + SegmentedControl   — filter bar (search + domain filter)
  [split grid: 1fr 380px]
  Panel(noPadding)
    └── Table      — domain swatch, id (mono), title, description, scheme (Chip), individuals count, version
  InspectorPanel   — selected class detail
    ├── InspectorPanel.Section "Identity"
    │     └── KVGrid
    ├── InspectorPanel.PropertySection "Property definitions"
    ├── InspectorPanel.Section "Sample individuals"
    │     └── VersionPill (inline)
    └── InspectorPanel.Section "Relationships"
```

### Schema · Properties (`/app/schema/properties.tsx`)
```
PageHeader
TabBar
Panel(noPadding)
  └── Table        — identifier (mono), title, description, relevance (Chip tri-state), origin, used_by, version
        └── Chip variant="emerald|rose|neutral" (relevance render)
        └── VersionPill
```

### Schema · Relationships (`/app/schema/relationships.tsx`)
```
PageHeader
TabBar
Panel(noPadding)
  └── Table        — id, source (domain dot + title), predicate (mono arrow), target, confidence, created
```

### Data · Individuals (`/app/data/individuals.tsx`)
```
PageHeader
Panel(noPadding)
  └── Table        — id (mono), title, description, class_ids (Chip[]), source, confidence, version
        └── Chip variant="neutral" (class membership chips)
        └── VersionPill
```

### Pipelines (`/app/pipelines/index.tsx`)
```
PageHeader
PipelineCard (×N)  — one per pipeline, vertical stack, gap 14
  — pipeline.flow[] must have icon mapped to valid IconName (see remaps above)
```

### App Shell (wraps all pages — `ux/src/routes/app.tsx`)
```
ShellLayout        — top-level container, accepts: appTitle, sidebar, topbar, statusbar
  AppTitle         — logo + workspace name + version
  Sidebar          — sections[], activeItemId, collapsed, onCollapse, onSelectItem
  Topbar           — breadcrumbs[], children (search bar + Buttons + Chip)
  Statusbar        — left[], right[] (kind: pulse|icon|divider, label, mono, tone)
CommandPalette     — isOpen, onClose, commands[], placeholder
Modal              — isOpen, onClose, title, subtitle, hintFooter, footer (Fragment)
Toast              — isOpen, onClose, variant, title, subtitle, duration
  (wrap in position:fixed div for bottom-right pinning — or use the app's Toast context wrapper)
```

---

## 4. CSS Architecture — Do Not Change the Layer Order

`ux/src/index.css` declares an explicit cascade layer order at the very top. **This line must never be moved, removed, or reordered:**

```css
@layer properties, theme, base, components, utilities, heimdall, app, graph;
```

If `heimdall` is declared after Tailwind's `base`, Tailwind's border reset (`border: 0px solid`) overrides every Heimdall border, background, and shadow.

### The 4 custom CSS files and their sole purposes

| File | Purpose |
|---|---|
| `src/design-system/app-overrides.css` | Color aliases (`--accent-cyan`, `--accent-rose`, etc.) and dark-mode token overrides. Nothing else. |
| `src/design-system/studio.css` | Shell/layout utilities, empty state classes, drawer classes, statusbar helpers, scrollbar resets |
| `src/design-system/crud.css` | Form field layout (`.stack-lg`, `.stack-sm`), readonly display, form callout positioning |
| `src/design-system/graph.css` | `GraphCanvas` container, domain cluster colors (`.graph-cluster-life-bg`, etc.), node styles |

**Do not add to these files unless you have exhausted Heimdall's own props.** The prototype's entire custom CSS is 2 selectors (`cs-domain-dot`, `cs-between`) — that is the gold standard.

---

## 5. Minimization Rules

Before writing any CSS or building any component, ask:

1. **Does a Heimdall component already do this?** Check the component map above and the skill files below.
2. **Does a Heimdall prop solve it?** Common props that eliminate custom CSS:
   - `noPadding` on `Panel` — removes inner padding
   - `headerAction` on `Panel` — right-side slot in the panel header
   - `variant` on `Button`, `Chip`, `Badge` — covers all color states
   - `color` on `StatTile` — cyan/violet/emerald/amber/rose
   - `size="sm"` on `Button` — 28px height variant
   - `icon` on `Button` — constrain to square for icon-only
   - `mono` on `TextInput` — monospace font
   - `footer`, `hintFooter`, `subtitle` on `Modal` — built-in layout slots
   - `eyebrow`, `idChip`, `actions` on `PageHeader` — no wrapper div needed
3. **Is this value computed at runtime?** If yes, `style={{}}` is acceptable. If no, add a CSS class.
4. **Does this pattern appear more than once?** If yes, add a utility class to the appropriate file above. If no, defer.

### Custom UI wrappers — the 5 intentional ones

These are the only components in `ux/src/components/ui/` that wrap a Heimdall component with extra behavior. Do not duplicate their functionality:

| Component | File | What it adds |
|---|---|---|
| `Drawer` | `components/ui/Drawer.tsx` | Autosave state, revert/delete action slots around `HeimdallDrawer` |
| `Toast` / `ToastProvider` | `components/ui/Toast.tsx` | Context-based queue, auto-dismiss, `useToasts` hook |
| `EmptyState` | `components/ui/EmptyState.tsx` | Layout convenience — centered icon + message + action |
| `TypeToConfirmDialog` | `components/ui/TypeToConfirmDialog.tsx` | Destructive confirm modal with typed confirmation |
| `GraphCanvasComponent` | `components/graph/GraphCanvasComponent.tsx` | Edge endpoint validation around `GraphCanvas` |

---

## 6. Heimdall Component Skill Index

Read the relevant skill file before implementing any component. Each file has prop tables, usage examples, and gotchas.

| Skill file | Components |
|---|---|
| `.claude/skills/heimdall/heimdall-shell/SKILL.md` | `ShellLayout`, `AppTitle`, `Titlebar`, `Statusbar` |
| `.claude/skills/heimdall/heimdall-primitives/SKILL.md` | `Icon`, `Button`, `Chip`, `Badge`, `StatusBadge`, `VersionPill`, `SegmentedControl` |
| `.claude/skills/heimdall/heimdall-navigation/SKILL.md` | `NavItem`, `Sidebar`, `Topbar`, `TabBar` |
| `.claude/skills/heimdall/heimdall-layout/SKILL.md` | `Panel`, `SplitPane` |
| `.claude/skills/heimdall/heimdall-inputs/SKILL.md` | `TextInput`, `TextArea`, `NumberInput`, `Select`, `TriState`, `Field`, `FilterDropdown`, `EntityPicker`, `KeyValueEditor`, `OrderedList`, `RelationshipBuilder` |
| `.claude/skills/heimdall/heimdall-overlays/SKILL.md` | `Modal`, `ConfirmDialog`, `Toast`, `CommandPalette`, `WorkspaceSwitcherDialog`, `Drawer` |
| `.claude/skills/heimdall/heimdall-data-display/SKILL.md` | `StatTile`, `StatGrid`, `Table`, `KVGrid`, `InspectorPanel` |
| `.claude/skills/heimdall/heimdall-page-patterns/SKILL.md` | `PageHeader`, `FilterBar`, `ActivityTimeline`, `AlertStrip`, `QuickAccessGrid`, `QuickAccessTile`, `ConfigTile`, `PipelineCard`, `FormCallout`, `RowMenu` |
| `.claude/skills/heimdall/heimdall-charts/SKILL.md` | `Sparkline`, `LineChart`, `BarChart`, `BarV`, `BarH`, `StackedBar`, `Donut`, `PieChart`, `Heatmap`, `StatusTimeline`, `ProgressBar`, `MetricRow` |
| `.claude/skills/heimdall/heimdall-graph/SKILL.md` | `GraphCanvas`, `GraphNode`, `GraphEdge`, `GraphInspector`, `TopologyNode`, `HierarchyRow`, `HierarchyTree` |
| `.claude/skills/heimdall/heimdall-chat/SKILL.md` | `ChatMessage`, `ToolBlock`, `ThinkingBlock`, `ChatDivider`, `ChatSuggestions`, `ChatComposer`, `ChatContainer` |

---

## 7. Implementation Workflow

Follow these steps in order for any new page, section, or component:

1. **Open the reference design** — `ux/design/Context Studio.html` in a browser. Navigate to the relevant page.
2. **Find the prototype source** — locate the page component in `cs/pages.jsx` or shell code in `cs/app.jsx`.
3. **Identify every Heimdall component used** — list them before writing any code.
4. **Read the relevant skill files** from the index above for any component you haven't used before.
5. **Copy the JSX** from the prototype, replacing `window.CS_DATA` references with real typed props/hooks.
6. **Add a single import line** at the top of your file: `import { ComponentA, ComponentB } from '@tinkermonkey/heimdall-ui'`
7. **Wire real data** — replace prototype's static sample data with TanStack Query hooks and API types.
8. **Run `/frontend-visual-qa`** before marking the task complete — it takes screenshots in both canvas modes and validates layout composition.

### Pages with a detail drawer

Any page that opens a detail panel on row selection **must** use `SchemaPageLayout`:

```tsx
<SchemaPageLayout
  data={filteredData}
  selectedId={selectedId}
  renderDrawerContent={(entity) => <MyDrawer entity={entity} ... />}
>
  <MyTable ... />
</SchemaPageLayout>
```

This applies the `split-2` CSS grid (`1fr 380px`). Never render a drawer as stacked content below the table. The prototype's Classes page is the canonical example.

---

## 8. Recurring Patterns

These appear on nearly every page — internalize them:

```tsx
// Every data page starts with:
<PageHeader
  eyebrow="CONTEXT · node_type · entity_type"
  title="Page Title"
  idChip="/route/path"
  subtitle="One sentence explaining what this entity is and how it relates to others."
  actions={
    <>
      <Button variant="ghost"><Icon name="download" size={13}/> Export</Button>
      <Button variant="primary"><Icon name="plus" size={13}/> New entity</Button>
    </>
  }
/>
```

```tsx
// Every table section:
<Panel noPadding>
  <Table
    rowKey="id"
    columns={[
      { key: 'id', label: 'Identifier', width: '160px',
        render: (v) => <span style={{fontFamily:'var(--font-mono)', fontSize:12.5}}>{v}</span> },
      { key: 'title', label: 'Title',
        render: (v) => <span style={{fontWeight:500}}>{v}</span> },
      { key: 'version', label: 'Ver', width: '60px',
        render: (v) => <VersionPill>{v}</VersionPill> },
    ]}
    data={rows}
    selectedRows={[selectedId]}
    onRowClick={(row) => setSelectedId(row.id)}
  />
</Panel>
```

```tsx
// Mono identifier display (used in table cells, inspector panels):
<span style={{fontFamily:'var(--font-mono)', fontSize:12.5}}>{entity.id}</span>

// Muted metadata text:
<span style={{color:'rgb(var(--canvas-fg-3))', fontSize:12.5}}>{entity.description}</span>
```

```tsx
// Domain color dot (2 custom CSS selectors from app.css):
<span className="cs-domain-dot" style={{background:`var(--dom-${entity.domain})`}}/>
// (add .cs-domain-dot { width:8px; height:8px; border-radius:2px; flex-shrink:0; } to studio.css if not present)
```
