# Context Studio — UX Architecture

This document defines the frontend architecture for the Context Studio UX rebuild. It is the authoritative reference for tech stack decisions, directory structure, component patterns, API layer conventions, and testing strategy.

The companion document `ux_plan.md` defines the phased implementation plan.

---

## Background

The legacy UX (`legacy/legacy_ux/`) is being replaced with a fresh React frontend built from a new Claude Design system. Design materials are in `ux/design/` and serve as the pixel-perfect visual specification.

The backend rearchitecture is complete: 6 bounded contexts, 76 API endpoints, hexagonal architecture. The UX must support the full domain — ontology authoring, graph analysis, text extraction, pipeline management, versioning, and system administration.

The product is a **local desktop application for building knowledge graphs**: an IDE for ontologies. The visual language reflects this — persistent dark chrome, compact information density, monospace identifiers, a command palette, and a live status bar.

---

## Tech Stack

### Preserved (no changes from legacy)

The legacy stack is modern and well-suited. The following packages are carried forward as-is:

| Package | Version | Role |
|---|---|---|
| React | 19 | UI framework |
| TypeScript | 5.8 | Type safety |
| Vite | 6 | Build tool |
| @tanstack/router-plugin | 1.x | File-based routing with autoCodeSplitting |
| @tanstack/react-router | 1.x | Client-side routing |
| @tanstack/react-query | 5.x | Data fetching and caching |
| @tanstack/react-table | 8.x | Data tables |
| @tanstack/react-form | 1.x | Form management |
| Zustand | 5 | Global UI state |
| Axios | 1.x | HTTP client |
| reagraph | 4.x | Graph visualization (force-directed) |
| openapi-typescript | 7.x | Type generation from OpenAPI spec |
| Lucide React | latest | Icons |
| Vitest | 1.x | Unit + integration testing |
| @testing-library/react | 16.x | Component testing |
| Playwright | 1.48 | E2E testing |
| MSW | 1.x | API mocking in tests |
| ESLint | 10.x | Linting |
| Prettier | 3.x | Formatting |
| prettier-plugin-tailwindcss | latest | Class ordering |
| Tailwind CSS | 4.x | Layout utilities |

### Removed

**Flowbite React** is removed entirely. The new design uses a custom CSS token system that is incompatible with Flowbite's theming model. The specific conflicts:

- Flowbite's dark mode operates on a single `.dark` class applied to `<body>`. The new design uses a **two-surface model** where the shell is always dark and the canvas is independently toggleable via `body.dark-canvas`. These models cannot coexist.
- Flowbite's `createTheme()` API applies overrides at the component level, which fights against the design token cascade.
- Removing Flowbite eliminates the `flowbite-react patch` postinstall step and `.flowbite-react/` config directory.

### Added

**Inter + JetBrains Mono fonts.** The design requires these families explicitly. Inter for all UI text; JetBrains Mono for identifiers, paths, keyboard hints, table headers, eyebrows, and stat numbers. Load via Google Fonts CDN in `index.html` or self-host in `src/design-system/`.

---

## Design System Architecture

### Two-Layer CSS System

The design is implemented through two layers:

**Layer 1 — Design tokens** (`src/design-system/tokens.css`): CSS custom properties for all design decisions — colors (shell, canvas, accent, domain, intent), typography scale, spacing, border radius, shadows, and animation timings. These tokens have no visual output on their own.

**Layer 2 — Component classes** (`src/design-system/studio.css`, `crud.css`, `graph.css`): Semantic CSS class names (`.btn`, `.panel`, `.chip`, `.modal`, `.input`, `.kg-row`, etc.) that consume the tokens from Layer 1. These classes are the primitives used in React components.

Tailwind CSS is retained for layout utilities — `flex`, `grid`, `gap`, `overflow`, `w-`, `h-`, `p-`, `m-` — but not for component styling. The `.btn` class, not `className="px-3 py-2 rounded bg-blue-500"`, is how a button is styled.

This separation allows the design token overrides (dark canvas, future theming) to cascade automatically through all components.

### Two-Surface Dark Mode

The studio has two independently-controlled surfaces:

- **Shell** — Titlebar, Sidebar, Topbar, Statusbar. Always dark (`--shell-bg: #0B0F14`). Never toggleable. Tokens prefixed `--shell-*`.
- **Canvas** — The scrollable work area inside the shell. Light by default (`--canvas-bg: #FFFFFF`). Toggleable to dark via a user preference that adds `body.dark-canvas`. Tokens prefixed `--canvas-*`.

The dark-canvas override is a CSS block in `studio.css` that redefines `--canvas-*` tokens on `body.dark-canvas`. Every component that uses `--canvas-*` tokens re-tints automatically.

**Do not collapse shell and canvas tokens into a single theme.** This is the core architectural constraint of the design system.

### Design Token Files (source → destination)

| Source (design materials) | Destination (production) |
|---|---|
| `ux/design/styles/tokens.css` | `ux/src/design-system/tokens.css` |
| `ux/design/styles/studio.css` | `ux/src/design-system/studio.css` |
| `ux/design/styles/crud.css` | `ux/src/design-system/crud.css` |
| `ux/design/styles/graph.css` | `ux/src/design-system/graph.css` |

The production files are ports, not copies — adapt import paths, remove prototype-specific tweaks (`.landing`, `.tweaks-panel`), and ensure font imports land in `index.css` rather than inline.

### What NOT to Port

Per the design handoff:
- `tweaks-panel.jsx` and the Tweaks UI — prototyping affordance only
- `data.js` — replace with real backend data
- `#r=<route>` URL fragment routing — use TanStack Router
- `.landing` class and styles — dead CSS from an earlier iteration
- Inline SVG icons in `icons.jsx` — use Lucide React (names map 1:1)

---

## Directory Structure

```
/ux/
├── design/                           # Design materials (unchanged, reference only)
├── e2e/                              # Playwright E2E tests
│   ├── tests/                        # Test files (one dir per feature area)
│   ├── documentation/
│   │   └── specs/                    # Planner specs (markdown, per feature)
│   └── fixtures/                     # Shared helpers and page object models
├── src/
│   ├── design-system/                # CSS design system (ported from ux/design/styles/)
│   │   ├── tokens.css                # All CSS custom property tokens
│   │   ├── studio.css                # Shell, canvas, and component classes
│   │   ├── crud.css                  # Forms, modals, dialogs, toasts
│   │   └── graph.css                 # Graph visualization styles
│   ├── api/
│   │   ├── client/
│   │   │   ├── axios.ts              # Axios instance — base URL, timeout, retry config
│   │   │   └── interceptors.ts       # Request/response/error interceptors
│   │   ├── services/                 # One service class per bounded context
│   │   │   ├── base.ts              # Abstract BaseService with typed request helpers
│   │   │   ├── ontology.ts          # Taxonomies, schemes, classes, individuals, properties, relationships
│   │   │   ├── graph.ts             # Graph build, metrics, paths, SPARQL, communities
│   │   │   ├── extraction.ts        # RAG extraction, NLP analysis, reference enrichment
│   │   │   ├── pipeline.ts          # Pipeline configs and executions
│   │   │   ├── versioning.ts        # Change events, changesets, sync
│   │   │   ├── reference.ts         # External reference sources (ConceptNet, DBpedia, etc.)
│   │   │   └── admin.ts             # Health checks, configuration, background tasks
│   │   ├── hooks/                    # TanStack Query hooks — one directory per bounded context
│   │   │   ├── ontology/
│   │   │   ├── graph/
│   │   │   ├── extraction/
│   │   │   ├── pipeline/
│   │   │   ├── versioning/
│   │   │   ├── reference/
│   │   │   ├── admin/
│   │   │   └── index.ts             # Barrel export
│   │   ├── types/                    # openapi-typescript generated types (do not edit by hand)
│   │   ├── utils/
│   │   │   ├── queryClient.ts       # QueryClient instance with staleTime/gcTime
│   │   │   └── logger.ts            # API-layer logger
│   │   ├── config.ts                # QUERY_KEYS, BASE_URL, cache settings
│   │   ├── ApiProvider.tsx          # QueryClientProvider wrapper
│   │   └── index.ts                 # Barrel export
│   ├── components/
│   │   ├── shell/                   # Chrome — always-dark surfaces
│   │   │   ├── Titlebar.tsx
│   │   │   ├── Sidebar.tsx          # Expanded (240px) and collapsed (64px) states
│   │   │   ├── Topbar.tsx
│   │   │   ├── Statusbar.tsx        # Daemon status, CPU/mem, sync state
│   │   │   ├── CommandPalette.tsx   # ⌘K overlay with fuzzy search
│   │   │   └── WorkspaceSwitcher.tsx
│   │   ├── ui/                      # Primitive design system components
│   │   │   ├── Button.tsx           # primary / accent / ghost / danger, sm / md
│   │   │   ├── Chip.tsx             # cyan / amber / violet / emerald / rose / gray variants
│   │   │   ├── Input.tsx            # text, search, with label/hint/error
│   │   │   ├── Select.tsx
│   │   │   ├── Textarea.tsx
│   │   │   ├── Modal.tsx            # sm (440px) / md (560px) / lg (760px)
│   │   │   ├── Drawer.tsx           # Right-side detail panel (400–480px)
│   │   │   ├── Toast.tsx            # Slide-in notifications with optional Undo action
│   │   │   ├── Tabs.tsx             # With mono count badges
│   │   │   ├── StatTile.tsx         # KPI tile with colored left bar
│   │   │   ├── Panel.tsx            # Default content card with head/body
│   │   │   ├── Skeleton.tsx         # Shape-matched loading placeholders
│   │   │   └── EmptyState.tsx       # Centered icon + title + guidance + CTA
│   │   ├── ontology/
│   │   │   ├── HierarchyTree.tsx    # .kg-row / .kg-node hierarchy viewer
│   │   │   ├── ClassEditor.tsx
│   │   │   ├── TaxonomyForm.tsx
│   │   │   ├── SchemeForm.tsx
│   │   │   ├── PropertyForm.tsx
│   │   │   └── RelationshipTable.tsx
│   │   ├── graph/
│   │   │   ├── GraphCanvas.tsx      # reagraph wrapper with domain-colored nodes
│   │   │   ├── MetricsPanel.tsx
│   │   │   ├── PathFinder.tsx
│   │   │   └── SparqlEditor.tsx
│   │   ├── extraction/
│   │   │   ├── ExtractionInput.tsx  # Text paste / upload
│   │   │   ├── LayerResults.tsx     # 4-layer result panels
│   │   │   └── EntityReviewPanel.tsx
│   │   ├── pipeline/
│   │   │   ├── PipelineCard.tsx     # Card with FlowStrip, status chip, foot stats
│   │   │   ├── FlowStrip.tsx        # .flow-node sequence (source→extract→resolve→write)
│   │   │   ├── ExecutionHistory.tsx
│   │   │   └── PipelineForm.tsx
│   │   ├── versioning/
│   │   │   ├── ChangesetPanel.tsx
│   │   │   ├── SyncStatus.tsx
│   │   │   └── ConflictResolver.tsx
│   │   └── admin/
│   │       ├── HealthDashboard.tsx
│   │       ├── ConfigEditor.tsx
│   │       └── TaskMonitor.tsx
│   ├── routes/                       # TanStack Router file-based routes
│   │   ├── __root.tsx               # Root layout — providers, canvas dark mode wiring
│   │   ├── index.tsx                # / — launch WorkspaceSwitcher or redirect to /app
│   │   ├── app.tsx                  # /app — shell layout (Sidebar + Topbar + Outlet)
│   │   └── app/
│   │       ├── index.tsx            # /app — Dashboard
│   │       ├── contact-sheet.tsx    # /app/contact-sheet — design system demo (dev only)
│   │       ├── schema/
│   │       │   ├── index.tsx        # Redirect to /app/schema/taxonomies
│   │       │   ├── taxonomies.tsx
│   │       │   ├── taxonomies.$taxonomyId.tsx
│   │       │   ├── schemes.tsx
│   │       │   ├── schemes.$schemeId.tsx
│   │       │   ├── classes.tsx
│   │       │   ├── classes.$classId.tsx
│   │       │   ├── properties.tsx
│   │       │   └── relationships.tsx
│   │       ├── data/
│   │       │   ├── individuals.tsx
│   │       │   ├── individuals.$individualId.tsx
│   │       │   └── datasets.tsx
│   │       ├── graph.tsx
│   │       ├── extraction.tsx
│   │       ├── pipelines/
│   │       │   ├── index.tsx
│   │       │   ├── $pipelineId.tsx
│   │       │   ├── runs.tsx
│   │       │   └── flavors.tsx
│   │       ├── reference/
│   │       │   ├── sources.tsx
│   │       │   └── workflows.tsx
│   │       ├── versioning.tsx
│   │       └── settings.tsx
│   ├── stores/
│   │   ├── canvas.ts                # Dark-canvas toggle (body.dark-canvas class)
│   │   └── commandPalette.ts        # Palette open/close and action registry
│   ├── hooks/
│   │   ├── useDebounce.ts
│   │   ├── useButterToast.tsx       # Toast notification helper
│   │   └── useKeyboardShortcut.ts   # ⌘K, Esc, ↑↓ for palette
│   ├── utils/
│   │   ├── nodeNavigation.ts
│   │   ├── queryParams.ts
│   │   └── renderers.ts
│   ├── types/                        # Shared TypeScript types (not API types)
│   ├── main.tsx                      # Application entry point
│   └── index.css                     # @import design-system/*.css + Tailwind base
├── index.html                        # Inter + JetBrains Mono font link, root div
├── package.json
├── tsconfig.json
├── vite.config.ts                    # @tanstack/router-plugin, @tailwindcss/vite
├── playwright.config.ts
├── vitest.config.ts
├── vitest.setup.ts                   # DOM mocks (matchMedia, ResizeObserver, etc.)
├── vitest.msw.config.ts
├── vitest.msw.setup.ts
├── selector-registry.yaml            # data-testid contract for test generation
├── eslint.config.js
└── prettier.config.cjs
```

---

## Component Architecture

Data flows in one direction through a defined layering:

```
OpenAPI spec (local-server/documentation/openapi.json)
    ↓  npm run generate-types
src/api/types/         — generated TypeScript types, never edited by hand
    ↓
src/api/services/      — one class per bounded context, wraps Axios, returns domain types
    ↓
src/api/hooks/         — one TanStack Query hook per API operation (useQuery / useMutation)
    ↓
src/components/        — consume hooks, render UI using design system CSS classes
    ↓
src/routes/            — compose components, define page-level layouts
```

### Services

Each service class extends `BaseService` (same pattern as legacy), which provides typed `get`, `post`, `put`, `delete` helpers with standardized error handling. Services are grouped by bounded context, not by individual endpoint:

- `OntologyService` — all ontology CRUD (taxonomies, schemes, classes, individuals, properties, relationships)
- `GraphService` — graph build, metrics, paths, SPARQL, community detection
- `ExtractionService` — RAG pipeline, NLP analysis, reference enrichment
- `PipelineService` — pipeline configurations and execution
- `VersioningService` — change events, changesets, sync push/pull
- `ReferenceService` — external knowledge source search and relations
- `AdminService` — health, configuration, background tasks

### Hooks

One React Query hook per API operation. Grouped into directories matching the service boundary. Each hook file exports a single named hook. Query keys are defined centrally in `api/config.ts` as `QUERY_KEYS` to enable targeted cache invalidation.

Cache configuration (same as legacy):
- `staleTime`: 5 minutes
- `gcTime`: 10 minutes
- Base URL: `http://localhost:8100` via `VITE_API_BASE_URL`
- Timeout: 30 seconds
- Retry: 3 attempts with exponential backoff

### Components

Components consume hooks and render UI using design system CSS classes (`.panel`, `.btn`, `.chip`, `.table-wrap`, etc.) plus Tailwind utilities for layout. Components do not contain inline style decisions — all visual specification comes from the design token system.

Every component that displays data must handle all five states: loading (skeletons), empty, partial, error, and populated. See `ux/design/handoff/UX.md § 3` for per-screen empty state copy.

### Routes

TanStack Router file-based routing with `autoCodeSplitting` enabled. Routes are thin composition layers — they select which components to render at which layout positions. Data loading (via `loader` functions or component-level hooks) lives in the route or directly in the component.

---

## State Management

| Store | File | Responsibility |
|---|---|---|
| Canvas theme | `stores/canvas.ts` | Tracks whether `body.dark-canvas` is applied. Persists to `localStorage`. |
| Command palette | `stores/commandPalette.ts` | Open/close state and the global action registry (navigation, CRUD shortcuts). |
| API cache | TanStack Query (`api/utils/queryClient.ts`) | All server state. No Redux, no custom cache. |
| Form state | TanStack Form or `useState` | Local to the form component. |
| NLP/extraction UI | `stores/extraction.ts` (if needed) | Transient UI state for the multi-step extraction flow. |

---

## Testing Strategy

### Unit tests (Vitest)

- Service classes: one test file per service, covering request formation and error handling
- Utility functions: pure functions tested in isolation
- Components: render tests with `@testing-library/react`, verifying correct DOM output for each state (loading, empty, error, populated)

### Integration tests (Vitest + MSW)

- Hooks tested with a real QueryClient against MSW-mocked responses
- Form submission flows tested end-to-end through component → hook → mock response

### E2E tests (Playwright)

- Full user flows against a running backend
- Sequential execution (single worker, shared backend state)
- Selectors sourced exclusively from `selector-registry.yaml` — no invented selectors

### Selector contract

`selector-registry.yaml` defines the `data-testid` attribute contract between the app and its tests. Every `data-testid` in the codebase must appear in this registry. Test generation (via `playwright-test-planner`) refuses to emit tests that reference unregistered selectors.

### Test development chain

```
playwright-test-planner  → spec at e2e/documentation/specs/<feature>.md
playwright-test-generator → test at e2e/tests/<area>/<feature>.spec.ts
context-studio-tester    → validate-selectors + run test + report
playwright-test-healer   → diagnose failures, propose minimal fix
```

---

## API Update Workflow

When backend APIs change:

1. Run `python local-server/scripts/update_api_specs.py` to refresh `local-server/documentation/openapi.json`
2. Run `npm run generate-types` in `/ux/` to regenerate `src/api/types/`
3. Update affected service methods and hook signatures
4. Update any components consuming the changed types

The OpenAPI spec is the contract. Type generation is mandatory after any backend change.

---

## Navigation Structure

Navigation matches the sidebar `NAV_TREE` from the design:

```
Dashboard           /app
Schema              /app/schema
  Taxonomies        /app/schema/taxonomies
  Concept schemes   /app/schema/schemes
  Classes           /app/schema/classes
  Properties        /app/schema/properties
  Relationships     /app/schema/relationships
Data                /app/data
  Individuals       /app/data/individuals
  Datasets          /app/data/datasets
Graph               /app/graph
Extraction          /app/extraction
Pipelines           /app/pipelines
  All pipelines     /app/pipelines (index)
  Run history       /app/pipelines/runs
  Flavors           /app/pipelines/flavors
External Reference  /app/reference
  Sources           /app/reference/sources
  Workflows         /app/reference/workflows
Versioning          /app/versioning
Configuration       /app/settings
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| ⌘K / Ctrl+K | Toggle command palette |
| Esc | Close palette / dialog / drawer |
| F6 | Cycle focus between shell regions |
| Alt + ← / → | Route history back/forward |
| ? | Open keyboard shortcuts help |
| ⌘↵ | Submit focused dialog |

---

## Accessibility Targets

WCAG 2.2 AA. Specific requirements:
- Every icon-only button has `aria-label`
- Status chips include visually-hidden text suffixes (`(success)`, `(failure)`, etc.)
- Pulsing daemon dot has `aria-label="Graph daemon connected"` / `"disconnected"`
- Tables use `<th scope="col">` and `<caption class="sr-only">`
- Focus trapped inside modals, dialogs, palette, and workspace switcher
- `prefers-reduced-motion: reduce` disables all animations (dot pulse, palette slide, sidebar collapse, toast slide)
- Cyan accent (`#22D3EE`) never used for body text — use `--accent-cyan-deep` (`#0E7EA3`) for text on light backgrounds

---

## Design System Contact Sheet

The route `/app/contact-sheet` is a developer-facing page (excluded from production builds via route guard or build flag) that renders every design system component in every state. It serves as the primary validation tool for Phase 1 — before any functional page is built, the contact sheet must match the 23 reference cards in `ux/design/preview/`.

Contact sheet sections:
- Typography scale (Inter + JetBrains Mono, all sizes)
- Color palette (shell, canvas light + dark, accents, domains, intents)
- Spacing and radius scales
- Buttons (all variants and sizes)
- Chips (all color variants)
- Inputs (resting, focus, error, disabled states)
- Stat tiles
- Panels and drawers
- Tables (populated, empty, loading)
- Modals (sm, md, lg)
- Toasts (all intent variants)
- Navigation and tabs
- Hierarchy tree viewer
- Pipeline flow card
- Command palette
- Skeleton states

---

## Design Token Reference

See `ux/design/handoff/README.md` for the complete token reference. Key architectural tokens:

**Shell (always dark):** `--shell-bg: #0B0F14`, `--shell-fg-1: #E6EDF3`, `--shell-border: #1E2733`

**Canvas (light default):** `--canvas-bg: #FFFFFF`, `--canvas-fg-1: #0B1220`, `--canvas-bd: #E5E9EE`

**Canvas (dark override on `body.dark-canvas`):** `--canvas-bg: #14191F`

**Accent:** `--accent-cyan: #22D3EE` (fills, rings, markers), `--accent-cyan-deep: #0E7EA3` (text, buttons on light)

**Intent:** success `#065F46` / `#ECFDF5`, warning `#92400E` / `#FFFBEB`, failure `#9F1239` / `#FFF1F2`

**Fonts:** `--font-sans: 'Inter', system-ui, sans-serif`, `--font-mono: 'JetBrains Mono', monospace`
