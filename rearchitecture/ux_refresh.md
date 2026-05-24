# UX Refresh: Heimdall-UI Full Adoption

**Why**: The UX has accumulated 4,410 lines of custom CSS and a layer of thin wrapper components that duplicate functionality already in `@tinkermonkey/heimdall-ui`. Of the 80+ Heimdall components available in v0.3.0, only ~25 are used. The result is visual drift from the design spec, maintenance burden on duplicated styles, and missed functionality (graph visualization, inspector panels, hierarchy rows, etc.). This refresh eliminates the custom CSS and wrappers by adopting Heimdall components directly, targeting the `Context Studio.html` prototype as the visual contract.

**Outcome**: ~3,600 lines of custom CSS removed (from 4,410 to ~800). Direct Heimdall imports throughout. Near-zero custom styling for core patterns.

**Preserved throughout**: TanStack Router file routing, React Query hooks, API services, Zustand stores, `data-testid` instrumentation, ARIA roles, `app-overrides.css` (50 lines of color aliases), `body.dark-canvas` dark mode pattern, `Drawer.tsx` wrapper (carries app-specific autosave/revert/delete behavior not in Heimdall).

**Stub pages**: Several routes currently exist as functional stubs (`pipelines/runs`, `data/individuals`, `data/datasets`, `reference/grounding`). Phase 6 brings these up to spec with design-aligned layouts. The `versioning` route has no design spec and stays as-is.

---

## Component Name Reconciliation

The build guide (`CONTEXT_STUDIO_BUILD_GUIDE.md`) was written for a future Heimdall version. Map these build-guide names to actual v0.3.0 exports:

| Build Guide | Actual Export | Notes |
|---|---|---|
| `Desktop`, `AppShell`, `Workspace` | `ShellLayout` | Single root component |
| `CanvasArea` | `ShellLayout` children | Pass page content as children |
| `PageHead` | `PageHeader` | Same props |
| `Split` | `SplitPane` | `direction="horizontal"` |
| `SplitMasterDetail` | `SplitPane` | Same |
| `Grid` | Tailwind `grid grid-cols-N gap-N` | No Heimdall equivalent |
| `Stack` / `Row` | Tailwind flex utilities | No Heimdall equivalent |
| `Tabs` | `TabBar` | Use `TabBar` |
| `SectionHead` | Styled `<h2>` | No Heimdall equivalent |
| `Mono` | `<code className="font-mono text-xs">` | No component export |
| `IdTag` | `<code className="font-mono text-xs bg-canvas-bg-2 px-1 rounded">` | No component export |
| `Muted` | Tailwind `opacity-60` or `text-gray-400` | No component export |
| `KGNode` | `HierarchyRow` `domain` prop drives swatch | No standalone component |
| `HeimdallProvider` | Not required | Current app runs without it |
| `ToastStack` | Custom `Toast` + store | Not in exports |

---

## Phase 1 — App Shell

**Replace custom layout CSS with `ShellLayout` + Heimdall `Sidebar` / `Topbar` / `Titlebar` / `Statusbar`**

The `shell-layout`, `shell-layout__main`, `shell-layout__content`, `shell-layout__canvas`, `canvas-scroll`, `canvas-inner` CSS classes in `studio.css` are pure layout glue that `ShellLayout` already provides. The sidebar CSS (`.shell-rail`, `.nav-section`, `.nav-sub`, `.collapsed.*`) and topbar CSS (`.topbar`, `.topbar-actions`, `.ws-chip`, `.crumbs`, `.env-pill`) follow the same pattern.

**Files to change:**

- `src/routes/app.tsx` — Replace `<div className="shell-layout">` tree with `<ShellLayout sidebar={...} topbar={...} titlebar={...} statusbar={...}>`. The `collapsed` toggle state moves into `ShellLayout`'s sidebar `onCollapse` callback.
- `src/components/shell/Sidebar.tsx` — Remap `NAV_TREE` to `SidebarSection[]` shape (`{ title, items: [{ id, label, icon, children }] }`). Remove `<aside>` markup; this file becomes a pure data builder returning the props object, not a component.
- `src/components/shell/Topbar.tsx` — Map `ROUTE_LABELS` to a `breadcrumbs` array for Heimdall `Topbar`. Move the workspace chip, dark-canvas toggle, and `⌘K` palette trigger into `Topbar` children. Remove `<div className="topbar">` markup. Wire the workspace chip `onClick` to open `WorkspaceSwitcherDialog` (replacing the current redirect to `/welcome`); render the dialog in `app.tsx` with `isOpen`/`onClose` state.
- `src/components/shell/Statusbar.tsx` — Align statusbar groups with the design spec. Left group: graph daemon health status (with `Pulse` dot), schema stats (`{classes} cls · {individuals} ind · {relationships} rel`), active pipeline name + progress if running, git branch. Right group: CPU/mem, `UTF-8 · LF`, last sync timestamp. All items use the Heimdall `Statusbar` item API; do not add raw HTML.
- `src/components/shell/__tests__/Topbar.test.tsx` — Add `ShellLayout`, Heimdall `Sidebar`, Heimdall `Topbar` to the `vi.mock` factory.

**CSS removed:**
- `studio.css` shell layout block (~lines 61–91)
- `studio.css` sidebar block (~lines 225–292, main block): `.shell-rail`, `.nav-section`, `.nav-sub`, `.rail-collapse`, `.brand-row`, all `.collapsed.*`
- `studio.css` topbar block (~lines 501–650): `.topbar`, `.topbar-actions`, `.ws-chip`, `.crumbs`, `.crumbs-sep`, `.env-pill`
- `studio.css` canvas scroll block (~lines 652–660): `.canvas-scroll`, `.canvas-inner`

**Verify:** App loads, sidebar collapses/expands, breadcrumbs update per route, dark-canvas toggle works. Run `pnpm test -- src/components/shell`.

---

## Phase 2 — Wrapper Removal

**Delete thin wrappers; use Heimdall `Modal`, `Chip`, `StatTile`, `Panel`, `PageHeader`, `ConfirmDialog` directly. Add `RowMenu`.**

These wrappers in `src/components/ui/` are pass-throughs with minimal app logic that keep custom CSS alive.

**Files to change:**

- `src/components/ui/Modal.tsx` — Delete. All callers update import to `@tinkermonkey/heimdall-ui`. Verify Heimdall `Modal` `size` prop matches current usage.
- `src/components/ui/Chip.tsx` — Delete. Callers import `Chip` directly. Apply `gray → neutral` tone mapping at call sites.
- `src/components/ui/StatTile.tsx` — Delete. Callers import `StatTile` directly. Check Heimdall `StatTile` for `sub` prop equivalence.
- `src/components/ui/Panel.tsx` — Delete. Callers import `Panel` directly. Map `actions` prop to Heimdall's Panel `actions` slot; if absent, compose inside header child.
- `src/components/ui/PageHeader.tsx` — Delete. Callers import `PageHeader` from Heimdall. Props match (`eyebrow`, `title`, `subtitle`, `idChip`, `actions`).
- `src/components/ui/ConfirmDialog.tsx` — Keep file; replace internals. Use Heimdall `ConfirmDialog` with a local confirm handler that adds the app's `isLoading` / `isConfirmDisabled` / `onError` behavior on top.
- **All schema routes + component callers** (~20 files) — Update imports for the deleted wrappers.
- **Schema row actions** — Replace `<button class="btn btn-icon"><MoreVertical /></button>` with Heimdall `RowMenu` (accepts `actions: RowMenuAction[]` + `onAction`).

**CSS removed:**
- `studio.css` Panel block (~lines 843–889): `.panel`, `.panel-head`, `.panel-title`, `.panel-body`
- `studio.css` StatTile block (~lines 890–953): `.stat`, `.stat[data-color=*]`, `.stat .label/num/meta/delta-*`
- `studio.css` Chip block (~lines 1014–1083): `.chip`, `.chip.cyan/.amber/.violet/.emerald/.rose/.gray`
- `studio.css` Button block (~lines 765–842): `.btn`, `.btn-primary`, `.btn-ghost`, `.btn-danger`, `.btn-icon`
- `crud.css` Modal block (~lines 1–180): `.modal`, `.modal-backdrop`, `.modal-head`, `.modal-body`, `.modal-foot`
- `studio.css` page header block (~lines 2584+): `.page-header__*`
- `studio.css` layout utilities (~lines 1999–2030): `.row`, `.muted`, `.mono`, `.grow`

**Verify:** `data-testid="page-header"`, `data-testid="confirm-dialog"`, `data-testid="confirm-dialog-confirm"` all present. Run `pnpm test -- src/components/ui`.

---

## Phase 3 — Schema Pages

**Replace `SchemaTable`, `FilterBar` wrapper, `SchemaPageLayout` with Heimdall `Table`, `FilterBar`, `SplitPane`, `InspectorPanel`, `KVGrid`, `VersionPill`.**

Schema pages are the highest-traffic surface and the largest block of duplicated CSS (TanStack Table rows, table styling, filter bar, split-2 layout).

**Files to change:**

- `src/components/schema/SchemaTable.tsx` — Replace TanStack Table with Heimdall `Table`. Column shape `ColumnDef<T>` → `Column<T>` (`{ key, label, sortable, width, render }`). Sorting: `onSort` callback + external sort state. Row selection: `selectable`, `selectedRows`, `onSelectRows`. Preserve `data-testid` on the id column via `render`.
- `src/components/schema/FilterBar.tsx` — Delete; callers import `FilterBar` directly from Heimdall. Add `SegmentedControl` as a child where domain filters appear.
- `src/components/schema/SchemaPageLayout.tsx` — Replace `<div className="split-2">` with Heimdall `SplitPane direction="horizontal" first={tableNode} second={inspectorNode}`. Note: `SplitPane` uses `first`/`second` props, not children. Wrap in a `<div data-testid="schema-page-layout">` to preserve the test contract. CLAUDE.md requires all pages with a detail drawer to use this layout.
- **Schema drawer files** (`ClassDrawer`, `PropertyDrawer`, `RelationshipDrawer`, `SchemeDrawer`, `TaxonomyDrawer`) — Replace inline `<dt>/<dd>` KV patterns with `KVGrid` (`{ rows: [{ key: string, value: ReactNode }] }`). Replace version display with `VersionPill`. Replace `<span className="mono">` IDs with `<code className="font-mono text-xs">`. When using `HierarchyRow` in any drawer context, pass `description=""` where no description text is available (it is required, not optional).
- **Schema route files** (5 files: `taxonomies.tsx`, `schemes.index.tsx`, `classes.tsx`, `properties.tsx`, `relationships.tsx`) — Update column definitions to `Column<T>`, update imports. **Add `TabBar` to each route** with all five tabs, counts sourced from the same data query already in scope (taxonomies count, schemes count, classes count, properties count, relationships count). The active tab corresponds to the current route; tab `onChange` calls `navigate`. This is currently missing from all 5 routes.
- `src/routes/app/index.tsx` (System Status panel) — Replace raw `<dt>/<dd>` with `KVGrid`.

**Note on pagination:** Heimdall `Table` does not have built-in pagination. Keep a minimal pagination wrapper or slice data externally before passing to `Table`.

**CSS removed:**
- `studio.css` table block (~lines 954–1013): `.table-wrap`, `.t`, `.t th/td/tr.selected/tr:hover`
- `studio.css` split layout (~lines 1289–1302): `.split-2`
- `studio.css` filter bar (~lines 1617–1636): `.filterbar`, `.filterbar .search-input`
- `studio.css` KV grid in drawer (~lines 1269–1287): `.drawer-body .kv`, `.kv dt/dd`
- `crud.css` form field CSS (~lines 180–500): form-group, fieldset, label, input field CSS covered by Heimdall `Field`/`TextInput`

**Verify:** `data-testid="schema-table"`, `data-testid="schema-filter-bar"`, `data-testid="schema-page-layout"` all render. Table sort works. Drawer KV grid shows correctly. Run `pnpm test -- src/components/schema src/routes/app/schema`.

---

## Phase 4 — Dashboard, Pipelines, Settings

**Add `ActivityTimeline`, `HierarchyRow`, `QuickAccessTile`, `ConfigTile`, `SegmentedControl`, `WorkspaceSwitcherDialog`.**

**Files to change:**

- `src/routes/app/index.tsx` (Dashboard) — Four changes:
  1. Delete the inline `ActivityTimeline` function (lines 13–73). Import `ActivityTimeline` from Heimdall. Map `ActivityEvent` to `{ id, type, subject, timestamp, kind, kindLabel, dotColor }`.
  2. Replace custom `HierarchyTree` inner rendering with `HierarchyTree` + `HierarchyRow` from Heimdall. Use `HierarchyRow` props: `depth`, `domain`, `kind`, `label`, `meta`, `selected`, `onSelect`, `description` (required — pass empty string `""` for nodes without descriptions).
  3. Add a `QuickAccessTile` grid section below the pipeline panel. Use Heimdall `QuickAccessTile` with `icon: IconName` — map to `"schema"`, `"pipeline"`, `"data"` etc.
  4. Replace `<div class="grid-2">` wrappers with Tailwind `grid grid-cols-2 gap-6`.

- `src/components/ontology/HierarchyTree.tsx` — Refactor to use Heimdall `HierarchyTree` as container with `HierarchyRow` children. Preserve expand/collapse state logic; replace only the presentation layer.

- `src/routes/app/pipelines/index.tsx` — Replace raw `<button role="radio" className="status-filter-chip">` radiogroup with `SegmentedControl`. Pass as child of existing Heimdall `FilterBar`.

- `src/components/settings/ConfigTile.tsx` — Delete. Import `ConfigTile` from Heimdall. Map Lucide icons to `IconName` strings (`Cpu → "pipeline"`, `Folder → "schema"`, `Database → "data"`). Unify `onEdit`/`onNavigate` into a single `onClick` handler.

- `src/routes/app/settings.tsx` — Update to `ConfigTile` from Heimdall. Replace `.config-grid` with Tailwind `grid grid-cols-2 gap-3`. Add `TabBar` above the config grid to match the design's 5-tab layout (General, Pipelines, Storage, Members, Integrations) — currently using a raw `.tabs` CSS class with no Heimdall component. Tab switching drives which config group is visible.

- `src/components/workspace/WorkspaceSwitcher.tsx` — Replace with Heimdall `WorkspaceSwitcherDialog`. API: `{ isOpen, onClose, current, recent, onOpenFolder, onNewWorkspace, onCloneFromGit, onPickRecent }`. The dialog is rendered in `app.tsx` (wired in Phase 1 above) and triggered from the Topbar workspace chip. If Heimdall dialog lacks input slots for the create/clone sub-flows, keep those as secondary modals triggered from the dialog's `onOpenFolder`/`onNewWorkspace`/`onCloneFromGit` callbacks.

**Test ID updates required:**
- `data-testid="activity-timeline"` and `data-testid="activity-timeline-empty"` — preserve via Heimdall `ActivityTimeline` `data-testid` passthrough or wrapper div.
- `data-testid="activity-event-{id}"`, `data-testid="activity-dot-{type}"` — internal to the old inline component; these test IDs will change. Update `src/routes/app/__tests__/dashboard.test.tsx` to query by Heimdall's rendered structure.

**CSS removed:**
- `studio.css` hierarchy block (~lines 1303–1388): `.kg-tree`, `.kg-row`, `.kg-cell`, `.kg-node`, `.swatch`
- `studio.css` quick access block (~lines 1529–1575): `.quick-access`, `.qa-tile`
- `studio.css` config tile block (~lines 1637–1703): `.config-tile`, `.config-tile-content`, `.config-tile-actions`
- `studio.css` status filter chips (~lines 2121–2160): `.status-filter-chip`
- `studio.css` workspace switcher (~lines 1865–1998): `.workspace-switcher-*`, `.ws-row`

**Verify:** Dashboard shows hierarchy tree with domain swatches, activity timeline, pipeline cards, quick access tiles. Settings tiles render. Pipeline status filter uses segmented control. Run `pnpm test -- src/routes/app/__tests__ src/components/settings`.

---

## Phase 5 — Graph View

**Replace `reagraph` with Heimdall `GraphCanvas` + `GraphNode` + `GraphInspector`.**

**Files to change:**

- `src/components/graph/GraphCanvas.tsx` — Remove `import { GraphCanvas } from "reagraph"`. Import `GraphCanvas, GraphNode, forceLayout` from Heimdall. Map existing node/edge shapes to `{ id, label, kind, domainColor }` / `{ id, sourceId, targetId, label }`. Pass `layout="force"` for automatic positioning. Preserve `validateEdgeEndpoints` logic and toast-on-error behavior. Preserve `data-testid="graph-canvas"` via wrapper div.

- `src/routes/app/graph/index.tsx` — Replace `<aside class="graph-inspector">` with Heimdall `GraphInspector`. The existing `TabBar` from Heimdall is already correct. Replace `<div className="graph-shell">` grid with `SplitPane direction="horizontal" first={canvasNode} second={inspectorNode}`.

- `src/design-system/graph.css` — Reduce to CSS variable definitions only (`:root { --graph-bg, --graph-grid, --graph-edge… }` + `body.dark-canvas` overrides). Remove all layout CSS for `.graph-canvas`, `.graph-shell`, `.graph-svg`, `.graph-stage`, and all `.gi-*` inspector CSS.

- `package.json` + `package-lock.json` — Remove `reagraph` dependency after verifying no other file imports from it.

**CSS removed:**
- `graph.css` layout block (~lines 27–200+): `.graph-shell`, `.graph-canvas`, `.graph-canvas__error`, `.graph-grid`, `.graph-stage`, `.graph-svg`, all `.gi-*`

**Verify:** Graph view renders nodes. Force layout positions them. Clicking a node opens `GraphInspector`. Zoom/pan works. Run `pnpm test -- src/components/graph`. Remove `reagraph` from `node_modules` and confirm no import errors.

---

## Phase 6 — Stub Pages

**Bring currently-stubbed routes up to design-spec layouts.**

These routes exist in the router but render minimal or placeholder content. The design shows each with a proper `PageHeader`, `FilterBar`, table or card layout, and where applicable an `InspectorPanel`. Backend APIs are already in place for most; this phase wires the UI to them.

**Files to create or significantly rewrite:**

- `src/routes/app/data/individuals.tsx` — Full `PageHeader` + `FilterBar` + `SplitPane` layout matching the design's Individuals page. Table columns: domain swatch, identifier (mono), title, class, property count. `InspectorPanel` on the right with `KVGrid` for properties. Uses existing `useIndividuals` hook.

- `src/routes/app/data/datasets.tsx` — `PageHeader` + table of datasets (name, source kind, individual count, last sync). No inspector required; row action opens a drawer. Uses existing data sources API.

- `src/routes/app/pipelines/runs.tsx` — `PageHeader` + `FilterBar` (status segmented control: all / running / success / failed) + Heimdall `Table` with columns: pipeline name (mono), status badge, started, duration, records ingested, errors. No inspector; row links to the pipeline detail page.

- `src/routes/app/pipelines/$pipelineId.tsx` (configurations tab) — `PipelineConfiguration` management is part of the pipeline detail view, not a standalone route. The detail drawer exposes LLM provider, model, and prompt settings scoped to that pipeline type. A pipeline type can have many configurations; each configuration's `pipeline` field identifies which type it belongs to.

- `src/routes/app/reference/workflows.tsx` — `PageHeader` + `Table` of grounding workflows (id, name, source, status, last run). Row selection opens a `Drawer` with workflow config. Uses existing grounding workflows API.

**Each page must follow the standard layout contract:**
- `PageHeader` with eyebrow chips, route `IdTag` in title, subtitle, primary action button
- `FilterBar` with search and `SegmentedControl` for status where applicable
- `SplitPane` with `InspectorPanel` for entity detail, OR `Drawer` for edit flows — not both
- Heimdall `Table` with `data-testid` on the table root
- `EmptyState` for zero-data states (complete sentence, period, concrete next action — no exclamation)

**Verify:** Each page renders without console errors. Filter reduces rows. Selecting a row opens the inspector/drawer. Run `pnpm test -- src/routes/app/data src/routes/app/pipelines/runs src/routes/app/reference/workflows`.

---

## Cross-Phase: Inline Style Purge

Throughout all phases, eliminate recurring inline style patterns:

| Pattern | Replace with |
|---|---|
| `style={{ fontFamily: 'var(--font-mono)' }}` | `<code className="font-mono text-xs">` |
| `style={{ color: 'var(--canvas-fg-3)' }}` | Tailwind `text-gray-400` or `opacity-60` |
| `style={{ fontSize: 'var(--text-xs)' }}` | Tailwind `text-xs` |
| `style={{ display: 'flex', gap: 'var(--space-3)' }}` | Tailwind `flex gap-3` |
| `style={{ background: 'var(--status-*)' }}` | Heimdall `Chip tone="*"` or `Pulse tone="*"` |

---

## Cross-Phase: Design Pattern Checklist

These patterns must be applied consistently across every page during implementation. They are not isolated to one phase.

### Eyebrow chips
Every `PageHeader` must have an `eyebrow` string composed of semantic chips. Pattern from the build guide:
- First chip: section context with dot — `<Chip tone="amber" dot>pipelines</Chip>`
- Second chip: entity type as id-tag — `<Chip form="id-tag">6 pipelines</Chip>`
- Trailing mono meta — use `<code className="font-mono text-xs opacity-60">` for counts/stats

### IdTag in page titles
Every page title must include a route `IdTag` immediately after the label:
```tsx
title={<>Classes <code className="font-mono text-xs bg-canvas-bg-2 px-1 rounded">/schema/classes</code></>}
```
The route string is the canonical identifier shown in the design on every page header.

### ModalFootHint
Every modal that triggers a server call must include a `ModalFootHint` in the footer showing the HTTP verb and path:
```tsx
<ModalFoot hint={<ModalFootHint>POST /classes</ModalFootHint>}>
```
This makes side effects explicit. Apply to every create/edit modal across all domains (class, scheme, taxonomy, property, relationship, individual, pipeline configuration, workflow).

### Status color intent
Never use raw hex or CSS variable names directly for status colors. Always use Heimdall semantic tones:
- `tone="ok"` / `tone="warn"` / `tone="error"` / `tone="info"` / `tone="neutral"` on `Chip`, `Pulse`, `Badge`
- Audit all `style={{ background: "..." }}` and `style={{ color: "var(--cyan-...)" }}` patterns and replace with tone props

### VersionPill
Every entity that carries a version number (taxonomy, class, property, relationship) must display it as `<VersionPill>v{entity.version}</VersionPill>` — in table cells, inspector panels, and drawer headers. Never render as raw text or inside a `<Chip>`.

---

## CSS Retained (Intentionally)

After all phases, the following CSS stays:

| File | What stays | Why |
|---|---|---|
| `app-overrides.css` | All 50 lines | Semantic color aliases for Heimdall token integration |
| `studio.css` | Reset/scrollbar block, titlebar CSS, statusbar group/pulse CSS, `Drawer` inner layout | Titlebar covers macOS window chrome; statusbar groups not in Heimdall; Drawer carries app-specific behavior |
| `crud.css` | Password toggle, number input with units, `TypeToConfirmDialog` layout | App-specific patterns not in Heimdall |
| `graph.css` | CSS variable definitions + dark-canvas overrides | Required for Heimdall GraphCanvas theming |

**Target total after all phases: ~800–1,000 lines** (down from 4,410).

---

## Verification Checklist

Run after each phase and after all phases combined:

```bash
# Type check
cd ux && npx tsc --noEmit

# Unit + integration tests
pnpm test

# Visual QA (run /frontend-visual-qa skill after each phase)
# — Screenshots in both light and dark canvas modes
# — Layout composition in split-pane pages
# — Form validation timing in drawers
# — data-testid audit

# CSS audit — confirm custom classes are gone after their phases
grep -r "shell-layout\|split-2\|kg-tree\|qa-tile\|config-tile\|status-filter-chip\|\.tabs\b" src/

# Design pattern audit — confirm no raw hex/inline status colors remain
grep -r "style={{.*color.*var(--cyan\|style={{.*background.*#" src/

# TabBar audit — confirm all 5 schema routes and settings include a TabBar
grep -rL "TabBar" src/routes/app/schema/ src/routes/app/settings.tsx
```

**Full-app page checklist** — every route must have before sign-off:
- [ ] `PageHeader` with eyebrow chips, route `IdTag` in title
- [ ] `TabBar` where the design shows tabs (all 5 schema routes, settings)
- [ ] `VersionPill` on any entity with a version field
- [ ] `ModalFootHint` in any modal that creates or updates a server resource
- [ ] `EmptyState` for zero-data states (sentence case, period, no exclamation)
- [ ] No inline `style={{}}` except for runtime-computed values
