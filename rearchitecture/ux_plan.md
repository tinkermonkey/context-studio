# Context Studio — UX Implementation Plan

This document defines the phased implementation plan for the Context Studio UX rebuild. Each phase has a clear scope, an ordered task list, and a verification step before moving to the next phase.

The companion document `ux_update.md` defines the architecture and tech stack.

**Rule:** Complete and verify each phase before starting the next. Do not build functional pages before the design system is validated. Do not build pages before the API layer is wired.

---

## Source of Truth

Before starting any phase, the implementer should read:
1. `ux/design/handoff/README.md` — visual spec (components, screens, foundations)
2. `ux/design/handoff/UX.md` — behavioral spec (flows, states, copy, accessibility)
3. `rearchitecture/ux_update.md` — architecture decisions

Reference files during implementation:
- `ux/design/styles/tokens.css` — all design tokens
- `ux/design/styles/studio.css` — shell and canvas component classes
- `ux/design/styles/crud.css` — form, modal, and dialog classes
- `ux/design/components/shell.jsx` — shell component reference implementation
- `ux/design/preview/*.html` — 23 visual reference cards (open in browser)
- `local-server/documentation/openapi.json` — API contract
- `legacy/legacy_ux/src/api/` — reference for services/hooks pattern
- `legacy/legacy_ux/src/routes/` — reference for routing patterns

---

## Phase 0 — Project Scaffold

Goal: A working Vite dev server at `localhost:5173` with routing, TypeScript, and test infrastructure configured. No UI yet.

### Tasks

1. **Initialize the project** in `/ux/` (not inside `/ux/design/`)
   - `npm create vite@latest . -- --template react-ts`
   - Delete the Vite starter content (App.tsx, App.css, index.css boilerplate, assets/)

2. **Install dependencies**
   - Copy `package.json` from `legacy/legacy_ux/` as a starting point
   - Remove: `flowbite-react`, `flowbite`, `@flowbite-react/*`
   - Keep all other packages (see `ux_update.md` tech stack table)
   - Add: nothing new beyond what legacy has (fonts load via `index.html`, not npm)

3. **Configure Vite** (`vite.config.ts`)
   - Add `@tanstack/router-plugin` with `autoCodeSplitting: true`
   - Add `@tailwindcss/vite`

4. **Configure TypeScript** (`tsconfig.json`)
   - Copy from legacy, verify `paths` alias `@/` → `./src/`

5. **Configure TanStack Router**
   - Create `src/routes/__root.tsx` (minimal shell — just `<Outlet />` for now)
   - Create `src/routes/index.tsx` (placeholder — "Context Studio")
   - Create `src/main.tsx` with `RouterProvider`
   - Run dev server: confirm routing works with no errors

6. **Configure Vitest**
   - Copy `vitest.config.ts`, `vitest.unit.config.ts`, `vitest.msw.config.ts` from legacy
   - Copy `vitest.setup.ts`, `vitest.msw.setup.ts` from legacy (adapt paths, remove Flowbite mocks)

7. **Configure Playwright**
   - Copy `playwright.config.ts` from legacy (adapt paths)
   - Create `e2e/tests/` and `e2e/documentation/specs/` directories
   - Create empty `selector-registry.yaml`

8. **Configure ESLint and Prettier**
   - Copy `eslint.config.js` and `prettier.config.cjs` from legacy
   - Remove any Flowbite-specific rules

9. **Add `index.html` font links**
   - Google Fonts: Inter (weights 400, 500, 600, 700, 800) + JetBrains Mono (weights 400, 500, 700)
   - Example: `<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">`
   - (Or self-host: download to `src/design-system/fonts/` and reference via `@font-face` in `tokens.css`)

10. **Add npm scripts** to `package.json`
    - `generate-types`: `openapi-typescript local-server/documentation/openapi.json -o src/api/types/index.ts`
    - `validate-selectors`: script from legacy
    - `typecheck`: `tsc --noEmit`
    - All test scripts from legacy

### Verification

- `npm run dev` → dev server starts, no console errors
- `npm run typecheck` → passes
- `npm test` → test runner starts (no tests yet, 0 failures)

---

## Phase 1 — Design System + Contact Sheet

Goal: Every design system component rendered and visually validated at `/app/contact-sheet`. No backend connection.

### Tasks

1. **Port design token CSS**
   - Create `src/design-system/` directory
   - Port `ux/design/styles/tokens.css` → `src/design-system/tokens.css`
   - Port `ux/design/styles/studio.css` → `src/design-system/studio.css`
     - Remove `.landing` class and related styles
     - Remove `.tweaks-panel` styles
   - Port `ux/design/styles/crud.css` → `src/design-system/crud.css`
   - Port `ux/design/styles/graph.css` → `src/design-system/graph.css`
   - Create `src/index.css` that imports all four in order, then `@import "tailwindcss"`

2. **Wire dark-canvas store**
   - Create `src/stores/canvas.ts` (Zustand store, persists to `localStorage`)
   - Store: `{ isDarkCanvas: boolean, toggle: () => void }`
   - `toggle()` adds/removes `body.dark-canvas` class and saves preference

3. **Build shell components** (reference: `ux/design/components/shell.jsx`)
   - `src/components/shell/Titlebar.tsx` — 36px bar, workspace path button, ⌘K chip
   - `src/components/shell/Sidebar.tsx` — 240/64px toggle, brand mark, `NavItem` tree, footer user row
   - `src/components/shell/Topbar.tsx` — 52px bar, breadcrumbs, ⌘K button, env pill
   - `src/components/shell/Statusbar.tsx` — 26px bar, pulsing daemon dot, cpu/mem (static for now)
   - `src/components/shell/CommandPalette.tsx` — 640px overlay, ⌘K toggle, fuzzy filter, ↑↓↵ Esc
   - `src/components/shell/WorkspaceSwitcher.tsx` — 700px overlay, Open/New/Clone tiles, recent list

4. **Build primitive UI components**
   - `Button.tsx` — variants: primary, accent, ghost, danger; sizes: sm (28px), md (34px); icon-only square
   - `Chip.tsx` — variants: cyan, amber, violet, emerald, rose, gray
   - `Input.tsx` — with `label`, `hint`, `error`, `required`, `disabled` props; search variant
   - `Select.tsx` — with same prop interface as Input
   - `Textarea.tsx`
   - `Modal.tsx` — sizes: sm (440px), md (560px), lg (760px); backdrop blur; focus trap; Esc closes
   - `Drawer.tsx` — right-side panel 400–480px; `.kv` grid for detail display; autosave head indicator
   - `Toast.tsx` — success/warning/failure/info variants; optional Undo action; 8s auto-dismiss
   - `Tabs.tsx` — with mono count badges on each tab
   - `StatTile.tsx` — 2px colored left bar, mono uppercase label, 28/700 number, meta line
   - `Panel.tsx` — `.panel` with `.panel-head` (title + actions) and `.panel-body`
   - `Skeleton.tsx` — shape-matched skeletons: row (36px), stat tile, panel, table
   - `EmptyState.tsx` — centered icon (48px, `--canvas-fg-4`) + title + guidance + CTA

5. **Build domain components for contact sheet**
   - `src/components/ontology/HierarchyTree.tsx` — `.kg-row` / `.kg-node`, `data-domain` swatch
   - `src/components/pipeline/PipelineCard.tsx` — head + flow strip + foot stats
   - `src/components/pipeline/FlowStrip.tsx` — `.flow-node` sequence with `.flow-arrow` connectors

6. **Build the app shell route**
   - Update `src/routes/__root.tsx` — `ApiProvider`, canvas dark mode class wiring
   - Create `src/routes/app.tsx` — Sidebar + Topbar + Statusbar + `<Outlet />`

7. **Build the contact sheet route**
   - `src/routes/app/contact-sheet.tsx`
   - Render every component in every state, organized by section (see `ux_update.md` contact sheet section list)
   - Include a dark-canvas toggle button at the top
   - Include a section for each of the 23 `ux/design/preview/` reference cards

### Verification

- Open `ux/design/preview/*.html` reference cards in a browser tab
- Open `/app/contact-sheet` in the dev server
- Side-by-side visual comparison: every component must match its reference card
- Test dark-canvas toggle — every component re-tints correctly
- Test Command Palette: ⌘K opens, Esc closes, ↑↓ navigates, ↵ does nothing (no real commands yet)
- `npm run typecheck` passes
- `npm test` passes (no new failing tests)

---

## Phase 2 — API Layer

Goal: All service classes and React Query hooks wired and returning real data from the backend. No UI pages yet.

### Tasks

1. **Generate types**
   - Run `npm run generate-types`
   - Verify `src/api/types/index.ts` was created and contains the expected API types
   - If the script fails, check that `local-server/documentation/openapi.json` is current

2. **Set up Axios client**
   - `src/api/client/axios.ts` — Axios instance, base URL from `VITE_API_BASE_URL`, 30s timeout
   - `src/api/client/interceptors.ts` — error standardization, conflict handling (port from legacy)

3. **Set up QueryClient**
   - `src/api/utils/queryClient.ts` — `staleTime: 5 * 60 * 1000`, `gcTime: 10 * 60 * 1000`
   - `src/api/ApiProvider.tsx` — `QueryClientProvider` wrapper (add to `__root.tsx`)

4. **Define query keys**
   - `src/api/config.ts` — `QUERY_KEYS` object covering all bounded contexts

5. **Build BaseService**
   - `src/api/services/base.ts` — abstract class with `get<T>`, `post<T>`, `put<T>`, `delete<T>` helpers
   - Port from `legacy/legacy_ux/src/api/services/base.ts`

6. **Build service classes** (one per bounded context)
   - `OntologyService` — methods for all 35 ontology endpoints
   - `GraphService` — methods for all 14 graph endpoints
   - `ExtractionService` — extract, NLP analysis, reference enrichment
   - `PipelineService` — pipeline config CRUD + execution
   - `VersioningService` — changes, changesets, sync
   - `ReferenceService` — search, relations, status
   - `AdminService` — health, metrics, configuration, background tasks

7. **Build React Query hooks** (one hook per operation per domain)
   - `src/api/hooks/ontology/` — `useTaxonomies`, `useTaxonomy`, `useCreateTaxonomy`, `useUpdateTaxonomy`, `useDeleteTaxonomy`, and equivalents for schemes, classes, individuals, properties, relationships
   - `src/api/hooks/graph/` — `useBuildGraph`, `useGraphMetrics`, `useShortestPath`, `useSparqlQuery`, etc.
   - `src/api/hooks/extraction/` — `useExtract`, `useNlpAnalysis`, `useEnrichFromReferences`
   - `src/api/hooks/pipeline/` — `usePipelines`, `usePipeline`, `useCreatePipeline`, `useExecutePipeline`, `usePipelineExecutions`
   - `src/api/hooks/versioning/` — `useChanges`, `useChangesets`, `useCreateChangeset`, `useSyncStatus`, `usePushSync`, `usePullSync`
   - `src/api/hooks/reference/` — `useReferenceSearch`, `useReferenceStatus`
   - `src/api/hooks/admin/` — `useHealthStatus`, `useSystemMetrics`, `useConfiguration`, `useUpdateConfiguration`, `useBackgroundTasks`
   - `src/api/hooks/index.ts` — barrel export

### Verification

- Start the backend: `cd local-server && python app.py`
- Start dev server: `cd ux && npm run dev`
- In browser DevTools, call a hook via a temporary test component or console — verify it returns real data
- `npm run typecheck` passes (no type errors in service or hook files)
- Run unit tests for services: `npm test -- services`

---

## Phase 3 — App Shell + Dashboard

Goal: The full app shell renders with live backend data. The Dashboard shows real stats, recent activity, and pipeline cards.

### Tasks

1. **Wire `__root.tsx`**
   - Add `ApiProvider` wrapper
   - Add canvas dark mode class sync (read from Zustand store, apply `body.dark-canvas`)
   - Add `useButterToast` toast container

2. **Wire `app.tsx`**
   - Sidebar with real navigation links (TanStack Router `<Link>`)
   - Topbar with breadcrumbs wired to current route
   - Statusbar wired to `useHealthStatus` hook — live daemon dot (green/rose), uptime

3. **Build Dashboard** (`src/routes/app/index.tsx`)
   - Stat grid: 4 tiles (Taxonomies, Classes, Individuals, Pipelines) from `useHealthStatus` or individual count queries
   - Two-column panel: Knowledge Graph Structure (hierarchy tree, `HierarchyTree` component) + Recent Activity (from `useChanges`)
   - Active Pipelines: `PipelineCard` grid from `usePipelines`
   - Quick Access: 3 tiles linking to Schema, Pipelines, Extraction
   - All five states implemented: loading (skeletons), empty (3-step setup card for zero-taxonomy workspaces), partial, error, populated

4. **Wire Workspace Switcher**
   - `WorkspaceSwitcher.tsx` — launch on first run (no recent workspace), connect to workspace open/create/clone via `AdminService`
   - `src/routes/index.tsx` — check for active workspace, redirect to `/app` if found, else show switcher

5. **Wire Command Palette**
   - `commandPalette.ts` store — register navigation actions from `NAV_TREE`
   - `CommandPalette.tsx` — fuzzy filter against registered actions, ↵ navigates

### Verification

- Start backend and dev server
- Dashboard loads and shows real data
- Stat tiles show correct counts
- Recent activity list shows real change events
- Switching dark canvas applies across all shell and canvas surfaces
- Statusbar dot is green when backend is running, rose when stopped
- ⌘K opens palette with navigation items; selecting one navigates

---

## Phase 4 — Schema Pages

Goal: Full CRUD for taxonomies, concept schemes, classes, properties, and relationships.

### Page pattern (apply to all schema pages)

Each schema page follows the same structure:
1. Page head: title + ID chip + action buttons (Import ghost + "+ New X" primary)
2. Filter bar: search input + filter chips (Domain, Sort)
3. 8/12 main table + 4/12 sticky drawer layout
4. Table: mono ID | name (cyan row-link) | description | domain chip | count | updated | row actions (kebab)
5. Drawer: `.kv` detail grid + editable fields + related lists + autosave

### Tasks

1. **Taxonomies**
   - `taxonomies.tsx` — list with `useTaxonomies`, create with `useCreateTaxonomy`, delete with `useDeleteTaxonomy`
   - `taxonomies.$taxonomyId.tsx` — detail with scheme tree, publish flow (draft → published)

2. **Concept Schemes**
   - `schemes.tsx`, `schemes.$schemeId.tsx` — same pattern; detail shows class list

3. **Classes**
   - `classes.tsx`, `classes.$classId.tsx` — hierarchy tree panel on detail; move class (`useMove`)
   - `ClassEditor.tsx` — name (snake_case validation), display label, domain select, parent class typeahead, description

4. **Properties**
   - `properties.tsx` — property definitions list; `PropertyForm.tsx` modal

5. **Relationships**
   - `relationships.tsx` — typed edge table; filter by source/target class

6. **Shared components**
   - `HierarchyTree.tsx` — finalize with real data, expand/collapse, `data-domain` routing to domain colors
   - Confirm all five states on every page (loading skeletons, empty state with correct copy from `UX.md § 3`)

7. **Destructive action dialogs**
   - Delete class with instances → type-to-confirm modal
   - Delete property in use → standard confirm
   - Publish taxonomy → confirm with diff summary

### Verification

- Create taxonomy → scheme → class → property → relationship: full chain works
- Delete class with instances shows type-to-confirm dialog
- Drawer autosaves on blur; "Saved Xs ago" appears in drawer head
- Undo toast appears after delete; clicking Undo restores the record
- All five states work (seed empty workspace to test empty states)

---

## Phase 5 — Data Pages

Goal: Individuals and datasets list, detail, create, and delete.

### Tasks

1. **Individuals**
   - `individuals.tsx` — list with class chip + sparkline of recent updates; `useIndividuals`
   - `individuals.$individualId.tsx` — detail: inherited properties panel, linked classes, related individuals
   - Create/edit individual: class typeahead, property value fields
   - Empty state: "No individuals yet" + "Run pipeline" + "Import…" CTAs

2. **Datasets**
   - `datasets.tsx` — list of imported datasets; basic table + actions

### Verification

- Individuals list populates from backend
- Link/unlink class works
- Empty state renders with correct copy

---

## Phase 6 — Graph, Extraction, Pipelines

Goal: Graph visualization, 4-layer text extraction, and full pipeline management.

### Tasks

1. **Graph** (`graph.tsx`)
   - `GraphCanvas.tsx` — reagraph force-directed graph, domain-colored nodes, neutral edges, cyan selection
   - Build graph from current taxonomy via `useBuildGraph`
   - `MetricsPanel.tsx` — centrality scores, community count, degree distribution (from `useGraphMetrics`)
   - `PathFinder.tsx` — source/target node pickers, shortest path result display
   - `SparqlEditor.tsx` — textarea + run button, results table

2. **Extraction** (`extraction.tsx`)
   - `ExtractionInput.tsx` — text paste area + file upload
   - 4-layer results panels: KG context → LLM extraction → NLP gap fill → Reference enrichment
   - `EntityReviewPanel.tsx` — approve/reject suggested entities, create new class or link to existing

3. **Pipelines** (`pipelines/`)
   - `index.tsx` — 2-column `PipelineCard` grid; failed pipelines pin to top
   - `PipelineCard.tsx` — finalize with live run status (chip + animated pulse when running), foot stats
   - `$pipelineId.tsx` — detail drawer: definition editor, last 10 runs, error log, and `PipelineConfiguration` management (LLM provider/model/prompt settings scoped to this pipeline type)
   - `runs.tsx` — full run history table with status chips, duration, record counts
   - Wire "Run" button: call `useExecutePipeline`, update statusbar ("1 pipeline running")
   - Note: pipeline configurations (`PipelineConfiguration`) are managed within the pipeline detail view — there is no standalone `/pipelines/configurations` route. One pipeline type can have many configurations (e.g. different models for the same extraction type); each configuration's `pipeline` field identifies which type it belongs to.

### Verification

- Graph loads and renders with domain-colored nodes
- Path finder returns a route between two classes
- Text extraction returns 4-layer results
- Pipeline runs and status updates in real time (polling or eventual consistency)
- Failed pipeline pins to top of dashboard

---

## Phase 7 — Reference, Versioning, Settings

Goal: Complete remaining functional pages.

### Tasks

1. **External Reference** (`reference/`)
   - `sources.tsx` — table of external knowledge sources; search via `useReferenceSearch`
   - `workflows.tsx` — grounding workflow list; same table + drawer pattern

2. **Versioning** (`versioning.tsx`)
   - `ChangesetPanel.tsx` — list of changes, stage into a changeset, apply changeset
   - `SyncStatus.tsx` — push/pull status from `useSyncStatus`, `usePushSync`, `usePullSync`
   - `ConflictResolver.tsx` — CRDT conflict diff and resolution UI

3. **Settings** (`settings.tsx`)
   - 2-column `.config-tile` grid with prominent icons
   - Tiles: Workspace settings, LLM provider config, embedding model, NLP model, reference sources, sync target
   - Wire to `useConfiguration`, `useUpdateConfiguration`

### Verification

- Reference search returns results
- Changeset create → apply cycle works
- Config changes persist across restart

---

## Phase 8 — Testing Pass

Goal: Comprehensive test coverage across all implemented pages and flows.

### Tasks

1. **Vitest unit tests**
   - Each service class: test all public methods with MSW-mocked responses
   - Utility functions: pure function tests
   - Key components: render tests for all five states (loading, empty, partial, error, populated)

2. **Playwright E2E tests** (using the full test development chain)
   - For each core flow in `UX.md § 2`, run the planner → generator → tester chain:
     - Create a new class (§ 2.1)
     - Resolve a failed pipeline run (§ 2.2)
     - Promote a draft taxonomy (§ 2.3)
     - Run an ad-hoc command via palette (§ 2.5)
   - Additional flows: full CRUD cycle for each schema entity type

3. **Validation gate**
   - Run `/context-studio-check` — domain purity, selector contract, OpenAPI freshness, TypeScript
   - Run `npm run validate-selectors`
   - All gates must pass before the phase is considered complete

### Verification

- `npm test` — all unit tests pass
- `npm run test:e2e` — all E2E tests pass (or failures are confirmed real product bugs, not test bugs)
- `/context-studio-check` — all gates green
- `npm run typecheck` — no type errors

---

## Implementation Notes

### Agents to Use

Per CLAUDE.md, consult the relevant specialist before implementing:

| Work | Agent |
|---|---|
| API layer (routes, schemas, OpenAPI contract) | `context-studio-api-expert` |
| React components, hooks, OpenAPI types | `context-studio-frontend-expert` |
| E2E test specs | `playwright-test-planner` → `playwright-test-generator` |
| Running tests | `context-studio-tester` |
| Diagnosing test failures | `playwright-test-healer` |
| Syncing `selector-registry.yaml` and docs after changes | `context-studio-doc-maintainer` |

### Porting from Legacy

The legacy UX at `legacy/legacy_ux/` is a reference, not a source. Port patterns (services/hooks structure, query key conventions, interceptor logic), not code verbatim. The component hierarchy, routing structure, and CSS system are all different.

### Dark Canvas Testing

Test every new component in both light-canvas (default) and dark-canvas (`body.dark-canvas`) modes. Pay special attention to: chip color variants (must use dark-tinted pastels), primary buttons (flip to cyan accent on dark), and skeleton states (must use `--canvas-bg-2`, not hardcoded colors).

### Tokenize All Strings

Do not embed UI strings inline in JSX. Define them as constants in a `copy.ts` file adjacent to each feature area. This eases future i18n without requiring a full localization system now.

### Mono for Identifiers

Any value that is technically an identifier, path, command, count, or measured value renders in JetBrains Mono with `font-family: var(--font-mono)`. This is the primary visual cue that distinguishes the product as an IDE rather than a generic app.
