# Heimdall Adoption Gap Inventory

**Audit date:** 2026-05-24  
**Prototype:** `ux/design/Context Studio.html` (visual contract)  
**Build guide:** `ux/design/CONTEXT_STUDIO_BUILD_GUIDE.md`  
**Method:** Side-by-side screenshots — prototype vs. running app — categorized as A/B/C below.

**Category key:**
- **A — Replace**: Custom component/CSS when Heimdall has an out-of-box equivalent
- **B — Override**: Heimdall component present but buried under custom CSS or wired with wrong data
- **C — Underuse**: Heimdall component used but not given the props/slots the design calls for

Screenshot pairs are saved in `/screenshots/audit/`.

---

## Shell (every page)

| # | Category | Component | Issue |
|---|----------|-----------|-------|
| S-1 | ✅ 2026-05-24 | `Sidebar` | Section header labels (SCHEMA, DATA, PIPELINES, EXTERNAL REFERENCE) appear in small-caps between nav groups. Prototype shows no header text — items group visually without labels. Check `showGroupLabel` prop or equivalent. |
| S-2 | ⚠️ won't-fix | `Sidebar` | No user profile chip at bottom. Heimdall `Sidebar` source has no `footer` prop or children slot — structurally impossible through the public API without modifying the Heimdall package. |
| S-3 | ✅ 2026-05-24 | Canvas mode | Implementation renders a white canvas. Prototype always uses dark canvas. `body.dark-canvas` needs to be applied as the app default. |
| S-4 | ✅ 2026-05-24 | `Topbar` | Search bar is narrow, right-aligned. Prototype: search spans ~80% of the topbar width. |
| S-5 | ✅ 2026-05-25 | `Topbar` | Workspace name now prepended as first breadcrumb in `app.tsx`. Derives from `config.sections.workspace.display_name`; falls back to path basename. |
| S-6 | ✅ 2026-05-25 | `Statusbar` | Entity counts (cls · ind · pipe) now wired from `useClasses` + `useIndividuals` hooks in `app.tsx`. Renders when at least one entity exists. |

---

## Dashboard

| # | Category | Component | Issue |
|---|----------|-----------|-------|
| D-1 | ✅ 2026-05-24 | `StatTile` | No sparklines. `StatTile` accepts a `sparkData` prop — not passed. Custom `Sparkline.tsx` is unnecessary; delete it. |
| D-2 | ✅ 2026-05-24 | `ActivityTimeline` | Plain bullet-list with dot icons and raw event strings. Prototype uses Heimdall `ActivityTimeline` with entity-type icons, styled action verbs, user attribution, "View all" link. Component exists — wrong data shape or not used. |
| D-3 | ✅ 2026-05-24 | `HierarchyTree` | Knowledge Graph Structure shows a flat CLASS list. Prototype shows `HierarchyTree` with taxonomy → scheme → class hierarchy, collapsible nodes, and count badges. |
| D-4 | ✅ 2026-05-24 | `PipelineCard` | Active Pipelines section confirmed visible in full-canvas screenshot (1 pipeline card rendered). Section was below viewport fold — capture script updated to 2400px viewport height. |
| D-5 | ✅ 2026-05-24 | `QuickAccessGrid` | QuickAccess grid confirmed visible in full-canvas screenshot — 6 icon+label tiles rendered in a horizontal row. |
| D-6 | ✅ 2026-05-25 | Dashboard `PageHeader` | `eyebrow="Main"` and `idChip="/"` were incorrectly set — prototype has no eyebrow on dashboard. Fixed: `eyebrow=""` (required prop, passed empty string). |
| D-7 | ✅ 2026-05-25 | `StatTile` | `GET /api/v1/admin/stats/trends?days=7` endpoint added to backend; `useStatsTrends()` hook wired; `sparkData` now passed to all four tiles. API queries `change_events` (local.db) and `pipeline_configurations` (operations.db) for 7-day rolling daily create counts. |

---

## Schema — Classes

| # | Category | Component | Issue |
|---|----------|-----------|-------|
| SC-1 | ✅ | `TabBar` | Present with counts (Taxonomies 3, Schemes 7, Classes 22, Properties 9, Relationships 11). |
| SC-2 | ✅ | Eyebrow chip | "SCHEMA" present. |
| SC-3 | ✅ | Route badge | "/schema/classes" path badge present. |
| SC-4 | ✅ | `Table` | Columns, domain chips, RowMenu all present. |
| SC-5 | ✅ 2026-05-25 | `InspectorPanel` | `SchemaPageLayout` already uses Heimdall `SplitPane` — row click opens detail panel inline in split layout. Confirmed in code. |
| SC-6 | ✅ 2026-05-25 | `FilterBar` | `FilterBar` with text search and `showingCount`/`totalCount` already wired on all schema pages. |
| SC-7 | ✅ 2026-05-25 | `SegmentedControl` | Domain filter `SegmentedControl` added to Classes page — filters table rows by `concept_scheme_id`. |

---

## Pipelines

| # | Category | Component | Issue |
|---|----------|-----------|-------|
| P-1 | ✅ 2026-05-24 | `TabBar` | Tabs show "All / Enabled / Disabled" (state-based). Prototype: "All / Running / Success / Idle / Failed" (status-based). Wrong axis. |
| P-2 | ✅ 2026-05-25 | `PipelineCard` | 4 executions run against "Test Pipeline QA". Card now shows "just now · 58→437 tokens · 7.3s" with flow metrics. Zero-state resolved. |
| P-3 | ✅ 2026-05-24 | `PipelineCard` | Missing pipeline description text under name. Now wired from provider+model as fallback. |
| P-4 | ✅ 2026-05-24 | `FilterBar` | Missing. Prototype has filter chips for name/tag/target. |
| P-5 | ✅ 2026-05-25 | Count label | `showingCount` and `totalCount` added to pipelines `FilterBar`. |

---

## Settings

| # | Category | Component | Issue |
|---|----------|-----------|-------|
| ST-1 | ✅ 2026-05-24 | Layout | Implementation: 2-column `ConfigTile` navigation grid (click to navigate to sub-form). Prototype: settings form fields **directly visible** on the General tab + right-sidebar `ConfigTile` summary cards. Completely different information architecture. |
| ST-2 | ✅ 2026-05-24 | Title | No route path badge (should show `/settings`). |
| ST-3 | ✅ 2026-05-24 | `TabBar` | Tabs present but no counts (General **6**, Pipelines **4**, etc.). |
| ST-4 | ✅ 2026-05-25 | Eyebrow | Added `.page-header__eyebrow { text-transform: none; }` override to `studio.css` (app layer wins over heimdall layer). Eyebrow now renders casing as passed. Behavioral test (ST-4) confirms. |
| ST-5 | ⚠️ n/a | `Modal` footer | Settings page auto-saves inline (no modal); `EditConfigModal` is unused dead code. The `hintFooter` prop exists on `Modal` but there is no modal to attach it to. Not applicable to current architecture. |

---

## Component Replacements (catalog audit 2026-05-25)

| ID | Status | Custom file | Heimdall equivalent | Notes |
|----|--------|-------------|---------------------|-------|
| CR-1 | ✅ 2026-05-25 | `src/components/ui/ConfirmDialog.tsx` | `ConfirmDialog` from Heimdall | Deleted; 6 drawer call sites updated (ClassDrawer, IndividualDrawer, PropertyDrawer, RelationshipDrawer, SchemeDrawer, TaxonomyDrawer); `TypeToConfirmDialog` rewired to use Heimdall `Modal` directly |
| CR-2 | ✅ 2026-05-25 | `src/components/ui/Skeleton.tsx` | CSS class pattern (`className="skeleton"`) | Deleted; 25 call sites replaced with `<div className="skeleton" style={{...}} />`; `.skeleton` CSS class added to studio.css |
| CR-3 | ✅ 2026-05-25 | Private `Textarea` in `src/components/versioning/CreateChangesetModal.tsx` | Heimdall `TextArea` | Inline wrapper removed; Heimdall `TextArea` now used directly |
| CR-4 | ✅ 2026-05-25 | `src/components/ui/Drawer.tsx` | `InspectorPanel` (header/actions) + raw Heimdall `Drawer` (shell) | All 6 entity detail views (Class, Taxonomy, Scheme, Property, Relationship, Individual) migrated to `InspectorPanel` in a split layout. `SchemaPageLayout.renderDrawerContent` renamed to `renderInspectorContent`. Crash caused by browser HTTP cache serving old bundle; resolved by clearing `.vite/deps` and restarting dev server. |
| CR-5 | ⚠️ not-mappable | `src/components/schema/SchemaTable.tsx` | — | Heimdall `Table` has no `pagination` prop (`TableProps` confirmed) — custom pagination strip is necessary, not a re-implementation |
| CR-6 | ⚠️ won't-fix | `src/components/schema/SchemaPageLayout.tsx` | `SplitPane` directly | Already uses SplitPane internally; thin wrapper, low-priority simplification |

---

## Infrastructure fixes

| ID | Date | Fix |
|----|------|-----|
| INFRA-1 | ✅ 2026-05-26 | `heimdallReact19Compat` Vite plugin updated — Heimdall v0.3.0 bundle changed internal marker vars from `ze`/`be` → `Ze`/`ye` (capital Z). Plugin now handles all 3 known marker sets and also injects `import React from "react"` to satisfy `React.forwardRef` references in the bundle. Without this fix the entire app renders blank. |

## Priority Order

| ID | Status | Notes |
|----|--------|-------|
| D-5 | ✅ 2026-05-26 | StatTile sparklines — `sparkData` wired to all 4 tiles; `meaningfulSparkData()` correctly suppresses all-zero arrays and <2-point arrays. PIPELINES tile shows sparkline (recent execution); others correctly suppress (data >7 days old). |
| CR-4 | ✅ 2026-05-25 | `ui/Drawer.tsx` — all 6 entity drawers replaced with `InspectorPanel` in split layout |
| S-2 | ⚠️ won't-fix | Heimdall `Sidebar` has no footer prop — confirmed in source: `SidebarProps` has no `footer`/`profile`/`renderFooter` field |
| ST-5 | ⚠️ n/a | Settings page auto-saves inline (no modal); `hintFooter` has nowhere to attach |

---

## CSS Cleanup (tracked separately)

Current total: **2,843 lines** across studio.css (1,358), crud.css (875), graph.css (610). _(Unchanged — no CSS added/removed in 2026-05-26 iteration 5.)_
Target: **≤1,200 lines** (retaining tokens, graph-specific, and titlebar CSS only).

Suspect blocks to audit:
- `.palette-*` (~85 lines studio.css) — likely superseded by Heimdall `CommandPalette`
- `.pipeline-card*` (~120 lines studio.css) — Heimdall `PipelineCard` owns this
- `body.dark-canvas *` overrides (~80 lines) — most should be deleted once tokens use `rgb()` wrapping correctly
- `.table-*`, `.tabs`, `.drawer` — pre-Heimdall, fighting component defaults
