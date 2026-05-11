# UX Polish Plan — Visual Quality & Test Coverage

## Diagnosis

### Root Cause 1: CSS has diverged — the design reference is ahead of the app

`/ux/design/styles/` (source of truth for the static HTML contact sheet) has 33 dark-mode rules vs. 25 in the app, 379 more lines of studio styles, and two entire files that never made it into the app (`individuals.css` 819 lines, `settings.css` 1311 lines). The app CSS was described as "ported from design" but the port is incomplete and the design has continued to evolve. This is the primary reason the static HTML looks better.

### Root Cause 2: Layout and spacing live in inline styles instead of CSS classes

There are 166 inline `style={{}}` usages across components and 121 in route pages. Things like `display: flex`, `flexDirection: column`, `gap: var(--space-3)` are repeated verbatim across multiple files. The CSS has the semantic classes (`.page-content`, `.page-header`, `.field`, `.filterbar` etc.) but pages bypass them with inline styles — so the CSS polish never lands.

### Root Cause 3: The React contact sheet is not a trustworthy reference

`contact-sheet.tsx` itself uses 31 inline `style={{}}` blocks (e.g., `Section` and `Row` are layout-only wrapper components built entirely with inline styles). It demonstrates components but doesn't show them in the same context as actual pages, so the gap between "contact sheet looks fine" and "page looks wrong" is invisible.

---

## Phase 1 — Establish a CSS sync baseline

**Goal:** Identify every line of design CSS that hasn't landed in the app.

1. Diff all four CSS files systematically and produce an audit of what's missing vs. intentionally excluded (e.g., `.landing-*` classes).
2. Port missing `studio.css` sections — 8 dark-mode rules, scrollbar polish, additional shell chrome classes.
3. Port missing `crud.css` sections — the design has ~69 more lines; audit and port any that correspond to real app components.
4. Decide on `individuals.css` and `settings.css` — either port them or park them in `design/` with a clear note they're not yet active.
5. Resolve `.canvas-scroll` as the canonical class (matching JSX usage). Expand CSS selectors to also accept `.scroll` for forward compatibility. The design reference's `.canvas-area` name is not adopted.

---

## Phase 2 — Add component-level unit tests that act as visual contracts

#### 2a — UI primitive contracts (11 components with no existing tests)

Each test verifies: correct CSS class names for each variant, `data-testid` attributes, proper ARIA roles.

| Component       | Key assertions                                                              |
| --------------- | --------------------------------------------------------------------------- |
| `Button`        | `.btn` + `.btn-{variant}` applied; `.btn-sm` on `size="sm"`; disabled state |
| `Chip`          | `.chip` class; color variant classes                                        |
| `Input`         | `.input` on all three exports; `.mono`; `.textarea` on `Textarea`           |
| `Panel`         | `.panel-head` only when `title` provided; `.panel-body` always              |
| `Tabs`          | Active tab gets active class; click switches active tab                     |
| `StatTile`      | Renders label and value; trend indicator                                    |
| `Skeleton`      | Renders with correct class                                                  |
| `EmptyState`    | `data-testid="empty-state"`; action button conditional                      |
| `ErrorBoundary` | Catches errors and renders fallback                                         |
| `Modal`         | Renders children when open; does not render when closed                     |
| `Drawer`        | `data-testid="drawer-autosave-status"`, revert + delete buttons present     |

#### 2b — Schema component contracts (4 components)

| Component          | Key assertions                                                                                   |
| ------------------ | ------------------------------------------------------------------------------------------------ |
| `FilterBar`        | `data-testid="schema-filter-bar"` + `"schema-search-input"`; chips render; remove callback fires |
| `SchemaTable`      | Renders rows; empty state when no data; column headers present                                   |
| `SchemaPageLayout` | Renders header, content, and optional actions slot                                               |
| `HierarchyTree`    | Renders nodes; expand/collapse works                                                             |

#### 2c — Dark mode token tests

For components referencing canvas tokens, apply `body.dark-canvas` class and verify computed styles change. Cheapest way to catch dark-mode regressions without a visual regression tool.

---

## Phase 3 — E2E contact sheet visual validation

**Goal:** Make `/app/contact-sheet` serve as an automated visual contract.

1. Add `data-testid` to each named section in `contact-sheet.tsx` (e.g., `contact-sheet-buttons`, `contact-sheet-inputs`).
2. Plan the E2E spec with `playwright-test-planner` — navigates to `/app/contact-sheet`, takes a screenshot of each section, toggles dark canvas.
3. Generate the spec with `playwright-test-generator`.
4. Optionally add `toHaveScreenshot()` snapshots for pixel-level regression detection.

---

## Phase 4 — Replace inline styles with CSS classes

Priority order:

1. **High** — layout patterns repeated 5+ times: `display: flex; flex-direction: column; gap: var(--space-3)` → use/add `.stack` or `.field-group`; page header pattern → `.page-header`
2. **Medium** — inline color references (`color: var(--canvas-fg-2)`) → move to CSS classes where semantic meaning exists
3. **Low** — one-off inline styles in pages that are genuinely context-specific

---

## Phase 5 — Make the contact sheet a genuine test harness

1. Remove all inline styles from `contact-sheet.tsx` — `Section` and `Row` helpers should use CSS classes, not inline styles.
2. Cover the dark canvas toggle with an E2E test.
3. Add a comment at top of `contact-sheet.tsx` stating it is the visual regression reference and all component variants must be represented.

---

## Execution order

```
Phase 1 (CSS sync)       → unblocks correct visual baseline
Phase 2a/2b (unit tests) → can run in parallel with Phase 1
Phase 3 (E2E spec)       → needs Phase 1 done for accurate baselines
Phase 4 (fix failures)   → driven by which tests fail
Phase 5 (contact sheet)  → last, once CSS and tests are stable
```

---

## Key file locations

| Thing                          | Path                                   |
| ------------------------------ | -------------------------------------- |
| App design tokens              | `src/design-system/tokens.css`         |
| App shell/canvas CSS           | `src/design-system/studio.css`         |
| App form/table CSS             | `src/design-system/crud.css`           |
| Design reference tokens        | `design/styles/tokens.css`             |
| Design reference studio        | `design/styles/studio.css`             |
| Design reference crud          | `design/styles/crud.css`               |
| Missing from app (settings)    | `design/styles/settings.css`           |
| Missing from app (individuals) | `design/styles/individuals.css`        |
| React contact sheet            | `src/routes/app/contact-sheet.tsx`     |
| Static HTML contact sheet      | `design/Context Studio - Browser.html` |
| Existing UI tests              | `src/components/ui/__tests__/`         |
| E2E tests                      | `e2e/tests/`                           |
| Selector registry              | `selector-registry.yaml`               |
