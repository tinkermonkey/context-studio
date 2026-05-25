---
name: heimdall-ux
description: Build or fix Context Studio UX using Heimdall design system components correctly. Covers component catalog, gap remediation patterns (A/B/C), CSS token rules, anti-patterns, and page-by-page recipes. Use when implementing any new page, fixing a design gap, or replacing custom components with Heimdall equivalents.
user-invocable: true
---

You are building or fixing Context Studio UX using Heimdall design system components. Everything in this skill comes from the authoritative sources — read them before implementing:

- **Component catalog + tokens**: `ux/node_modules/@tinkermonkey/heimdall-ui/` 
- **Build guide (page recipes + anti-patterns)**: `ux/design/CONTEXT_STUDIO_BUILD_GUIDE.md`
- **Gap inventory (what's wrong and why)**: `documentation/ux-audit/heimdall-gap-inventory.md`
- **Design prototype**: serve `ux/design/Context Studio.html` via `python3 -m http.server 3200` in `ux/design/` and open `http://localhost:3200/Context%20Studio.html`

---

## Import pattern

```tsx
import { Button, Table, Modal, StatTile, PageHeader, ... } from "@tinkermonkey/heimdall-ui"
```

All 77 components are available from this single import. Never reach into subpaths.

---

## CSS token rules (critical)

Heimdall tokens store **raw RGB channel values** — they MUST be wrapped in `rgb()`:

```css
/* ✅ correct */
color: rgb(var(--canvas-fg-1));
background: rgb(var(--canvas-bg));
border: 1px solid rgb(var(--canvas-border));

/* ❌ broken — produces "color: 11 18 32" (invalid CSS) */
color: var(--canvas-fg-1);
```

This applies to all shell and canvas tokens: `--shell-bg`, `--canvas-fg-*`, `--canvas-bg`, `--canvas-border`, `--canvas-border-strong`, `--accent-primary`, `--status-*`.

Exception: tokens defined in `app-overrides.css` (e.g. `--accent-cyan`, `--accent-amber`) are already `rgb()`-wrapped and can be used directly.

**`--accent-primary` is amber** (`#fbbf24`), not cyan. Use `--status-cyan` or `--accent-cyan` when you want cyan.

---

## Layer ordering (do not change)

`src/index.css` declares:
```css
@layer properties, theme, base, components, utilities, heimdall, app, graph;
```

This must stay as the first rule. The `heimdall` layer must come after `utilities` so Heimdall's component styles win over Tailwind's base reset. Never reorder this.

---

## Gap remediation patterns

### Category A — Replace (custom → Heimdall)

When you find a custom component doing what Heimdall already does:
1. Find the Heimdall equivalent in the catalog below
2. Read its props interface in `node_modules/@tinkermonkey/heimdall-ui/`
3. Replace the custom component — do not keep both
4. Delete the custom component file and its CSS if it is now fully replaced
5. Remove the CSS block from studio.css that was styling the custom component

### Category B — Override (fighting Heimdall)

When CSS in `studio.css`, `crud.css`, or `app-overrides.css` is fighting a Heimdall component:
1. Open DevTools and inspect the element — find which CSS rule is winning
2. Trace the rule to its source file and line
3. Delete the rule if Heimdall handles it natively
4. If the rule is legitimately needed (e.g. an app-specific override), keep it but scope it precisely (no `body.dark-canvas .table *` catch-alls)

### Category C — Underuse (missing props)

When a Heimdall component is used but not given what the design requires:
1. Read the component's TypeScript interface in `node_modules/@tinkermonkey/heimdall-ui/`
2. Find the prop that enables the missing feature
3. Wire the prop — data usually comes from an existing API query already in the page

---

## Component catalog (key components)

### Shell

**`ShellLayout`** — root container. Takes `sidebar`, `topbar`, `titlebar`, `statusbar` as prop objects. Never build shell chrome outside this component.

**`Sidebar`** — left nav. Key props:
- `sections` — array of `{ id, label?, items: NavItem[] }`. Set `label: undefined` to suppress the section header text shown in small-caps.
- `activeItemId` — matched by longest-path string comparison
- `collapsed` / `onCollapse`
- `footer` — pass the user profile chip here

**`Topbar`** — top bar. The `children` slot spans the full width between the workspace chip and the right-side icons. Pass a full-width search input there, not a narrow one.

**`Statusbar`** — bottom bar. Pass `left` and `right` arrays of `StatusItem`. Wire entity counts, running pipeline indicator, branch, and CPU/mem from the health and stats API endpoints.

### Dashboard

**`StatTile`** — stat card. Key props:
- `value` — the number
- `label` — the metric name
- `tone` — `"ok" | "warn" | "error" | "info"`
- `sparkData` — array of numbers for the sparkline. **Do not use a custom Sparkline component.** Pass data here.

**`ActivityTimeline`** — activity feed. Each item: `{ id, action, entityType, entityLabel, user, timestamp, href }`. Do not build a custom bullet list.

**`HierarchyTree`** — tree view. Each node: `{ id, label, type, count, children?, expanded? }`. Builds the collapsible taxonomy → scheme → class structure.

**`QuickAccessTile` / `QuickAccessGrid`** — quick-access cards. `QuickAccessTile` takes `icon`, `label`, `count`, `accent`, `onClick`.

**`PipelineCard`** — pipeline card with flow visualization. Key props:
- `name`, `id`, `status`
- `steps` — array of `{ icon, label, sublabel }`
- `metrics` — object with `lastRun`, `ingested`, `created`, `updated`, `errors`
- `description`
- `onRun`, `onCancel`, `onMenu`

### Schema pages

**`Table<T>`** — generic table. Columns: `{ key, label, sortable?, width?, render? }`. Handles sorting, selection, and keyboard navigation natively. Do not add custom pagination unless `Table` has no built-in support.

**`InspectorPanel`** — inline detail panel. Opens in a split layout next to the table when a row is selected. Use this instead of a `Drawer` for schema detail views.

**`FilterBar`** — chip-based filter bar. Takes `filters` array and `onFilterChange`.

**`SegmentedControl`** — button group for view toggles. Takes `options` array and `value`/`onChange`.

**`TabBar`** — horizontal tabs. Each tab: `{ id, label, count? }`.

**`VersionPill`** — version display badge. Takes `version` string.

### Overlays

**`Modal`** — dialog. Key props: `isOpen`, `onClose`, `title`, `subtitle`, `footer`, `hintFooter` (the HTTP verb + path shown at the bottom per BUILD_GUIDE §5).

**`Drawer`** — side panel. Use only for complex flows that need a large canvas, not for schema detail inspection (use `InspectorPanel` there).

**`CommandPalette`** — global search/command overlay. Already wired — do not add custom palette CSS.

### Forms

**`TextInput`** — text field. Props: `mono` (monospace font for identifiers/paths), `error` (error state).

**`Field`** — label + input wrapper. Required for all form fields.

**`Select`** — dropdown. Standard HTML `<select>` wrapper.

**`SegmentedControl`** — use for binary/tertiary toggles within forms.

---

## Page recipes (from BUILD_GUIDE §4)

Read `ux/design/CONTEXT_STUDIO_BUILD_GUIDE.md` for the full recipes. The most critical ones:

### Dashboard
```
PageHeader (eyebrow, title, IdTag)
StatGrid → StatTile × 4 (with sparkData)
[two columns]:
  HierarchyTree (knowledge graph)
  ActivityTimeline (recent events)
Active Pipelines: PipelineCard grid
QuickAccessGrid → QuickAccessTile × 6
```

### Schema pages (all 5 routes)
```
TabBar (Taxonomies | Schemes | Classes | Properties | Relationships, with counts)
PageHeader (eyebrow chip, title, IdTag for route path, + New button)
FilterBar
[split layout]:
  Table (with RowMenu per row)
  InspectorPanel (when row selected)
```

### Pipelines
```
PageHeader (eyebrow "● pipelines", title "Pipelines", IdTag "/pipelines/all")
TabBar (All | Running | Success | Idle | Failed, with counts)
FilterBar
PipelineCard grid (each card has steps, metrics, description, Run/Cancel)
```

### Settings / Configuration
```
PageHeader (eyebrow "● settings", title "Configuration", IdTag "/settings", Reload button)
TabBar (General | Pipelines | Storage | Members | Integrations, with counts)
[two columns]:
  form fields (TextInput wrapped in Field, monospace values)
  ConfigTile sidebar (Backups, Performance, Telemetry)
Modal footer: hintFooter = "PUT /workspace/{name}/config"
```

---

## Anti-patterns (from BUILD_GUIDE §7)

| Anti-pattern | Correct approach |
|---|---|
| Custom `Sparkline` component inside `StatTile` | Pass `sparkData` prop to `StatTile` directly |
| `Drawer` for schema entity detail | Use `InspectorPanel` in a split layout |
| Raw `body.dark-canvas` catch-all overrides | Fix token wrapping (`rgb(var(--token))`) instead |
| Section header labels in sidebar groups | Pass `label: undefined` on the section config object |
| Hardcoded colors (`#22d3ee`, `#fbbf24`) | Use Heimdall tokens (`rgb(var(--status-cyan))`, `rgb(var(--accent-primary))`) |
| Tab labels as feature states (Enabled/Disabled) | Tab labels as run states (Running/Success/Idle/Failed) for pipelines |
| Generic workspace chip ("local") | Wire the workspace name from the API |
| Narrow search in topbar | Pass search as full-width child in `Topbar` |
| ConfigTile nav grid on settings | Form fields directly visible + ConfigTile sidebar column |

---

## Verification after any change

```bash
# TypeScript must be clean
cd ux && npm run typecheck

# Then run visual QA
/frontend-visual-qa

# Then compare against prototype
/context-studio-design-audit
```

Mark the gap in `documentation/ux-audit/heimdall-gap-inventory.md` as ✅ with the date fixed.
