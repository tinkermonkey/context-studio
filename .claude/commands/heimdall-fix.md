---
description: Run a visual-comparison fix loop — audit custom components, capture screenshot pairs, spawn visual review agents, spawn fix agents, and loop until all pages pass or 5 iterations exhausted.
argument-hint: "[max-iterations=5]"
---

You are running the Heimdall visual conformance fix loop for Context Studio. Your job is to make the live implementation *look correct* by comparing it against the prototype (`ux/design/Context Studio.html`). The exit criterion is that a visual review agent returns all-PASS across every page — not that a set of DOM selectors matches.

The max iterations is `$ARGUMENTS` (default: 5).

**Before starting**, read:
- `documentation/ux-audit/heimdall-gap-inventory.md` — gap registry with A/B/C categories
- `.claude/skills/heimdall-ux/SKILL.md` — component recipes and anti-patterns

---

## Prerequisites — servers must be running

The capture script starts servers automatically if they are not already running. Do NOT start them manually. The script checks:

- App dev server: `http://localhost:3100`
- Backend: `http://localhost:8000`
- Prototype file server: `http://localhost:3200` (serves `ux/design/Context Studio.html`)

If the backend is not running at port 8000, the implementation pages will show error states. Note it in the plan — fix agents should not attempt to fix backend issues.

---

## Loop Structure

Repeat the following steps until either:
- Visual review returns all-PASS for all pages, OR
- You have completed the maximum number of iterations

---

## Step 0 — Component catalog audit

**This runs before screenshots, every iteration.** Visual comparison of a wrong component gives misleading results — you must be on the right component before assessing whether it is configured correctly.

Spawn one audit agent (default agent type) with this prompt:

> You are auditing the Context Studio frontend for custom components that duplicate functionality already provided by the Heimdall design system (`@tinkermonkey/heimdall-ui`).
>
> **Step 1 — Build the Heimdall component list.**
> Read `ux/node_modules/@tinkermonkey/heimdall-ui/dist/index.d.ts`. Extract every exported component name.
>
> **Step 2 — Build the custom component list.**
> Run: `find ux/src/components -name "*.tsx" | sort`
> For each file, read it briefly (first 30 lines) to understand its purpose.
>
> **Step 3 — Match and classify.**
> For each custom component, determine:
> - Is there a Heimdall component that provides equivalent or superior functionality?
> - Is the custom component wrapping a Heimdall component (acceptable) or re-implementing one (replace)?
> - Which pages or files import it?
>
> A thin wrapper that only maps app data types to Heimdall props is acceptable. A custom component that renders its own structure for something Heimdall exports (Sidebar, Sparkline, FilterBar, Table, etc.) is a replacement candidate.
>
> **Step 4 — Return a replacement manifest.**
> Format:
>
> ```markdown
> ## Component Replacement Manifest — YYYY-MM-DD
>
> ### Replace (custom re-implementation of a Heimdall component)
> | Custom file | Purpose | Heimdall equivalent | Scope | Priority |
> |---|---|---|---|---|
> | src/components/ontology/Sparkline.tsx | Standalone sparkline | StatTile.sparkData prop | Dashboard only | Wave 2 |
> | src/components/ui/FilterChip.tsx | Filter tag | FilterBar chip slot | Schema, Pipelines | Wave 2 |
>
> ### Acceptable wrappers (do not replace)
> | Custom file | Purpose | Why it's acceptable |
> |---|---|---|
> | src/components/ontology/HierarchyTree.tsx | Maps ontology data to Heimdall HierarchyTree | Thin data-mapping wrapper, not a re-implementation |
>
> ### Not mappable (no Heimdall equivalent — keep custom)
> | Custom file | Purpose | Note |
> |---|---|---|
> | src/components/ui/ErrorBanner.tsx | API error display | No Heimdall equivalent |
> ```
>
> Scope: "Wave 1" if the replacement touches shell or shared layout files. "Wave 2" if it is page-scoped.
> Do NOT make any code changes — return the manifest only.

**After the manifest returns:**
- If the "Replace" table is empty → skip to Step 1.
- If there are replacements → include them in the Wave 1 or Wave 2 work assignments in Step 3, and execute them as part of the fix agents in Step 4.
- Add any newly discovered replacements to `documentation/ux-audit/heimdall-gap-inventory.md` as Category A gaps if they are not already listed.

---

## Step 1 — Capture screenshot pairs

```bash
cd ux && npm run design-audit:capture 2>&1
```

This runs `scripts/capture-design-audit.sh`, which:
1. Starts servers if needed
2. Navigates to each page in both the prototype and the live app
3. Saves pairs to `/screenshots/audit/YYYY-MM-DD/`

Files produced (for today's date):
- `dashboard-prototype.png` / `dashboard-impl.png`
- `schema-classes-prototype.png` / `schema-classes-impl.png`
- `schema-taxonomies-prototype.png` / `schema-taxonomies-impl.png`
- `pipelines-prototype.png` / `pipelines-impl.png`
- `settings-prototype.png` / `settings-impl.png`

Also run the behavioral conformance tests as a fast pre-check:

```bash
cd ux && npm run design-audit 2>&1
```

Note which of S-3, P-1, ST-4 pass or fail — include in the plan.

---

## Step 2 — Spawn visual review agents in parallel

Launch **one visual review agent per page** in a single message. Use the default agent type.

Each agent prompt must be self-contained and include:
1. The absolute paths to both screenshots (prototype and impl)
2. The per-page checklist below (paste the relevant section inline)
3. The instruction to return a structured markdown table with PASS/FAIL per item

**Return format each agent must use:**

```markdown
## Visual Review — [Page] — [Date]

| # | Item | Result | Evidence |
|---|------|--------|----------|
| 1 | Canvas background is dark slate | PASS | Both shell and canvas are dark |
| 2 | StatTiles contain sparkline charts | FAIL | Four tiles visible, numbers only — no chart elements |
...

**Score: N / TOTAL PASS**
**Blocking failures:** [comma-separated item numbers that must be fixed this iteration]
```

A result is "blocking" if it is a Category A or B gap. Category C (missing props) is lower priority but still reported.

---

### Per-page visual checklists

**Dashboard (`/app`)**

| # | Item | Category |
|---|------|----------|
| 1 | Shell and canvas backgrounds are dark slate (not white/light) | A |
| 2 | Sidebar: no visible section header labels between nav groups (no small-caps "SCHEMA", "DATA" text) | B |
| 3 | Topbar: breadcrumb on left, Heimdall search pill on right — no custom workspace chip or branch badge | B |
| 4 | Four StatTile cards are visible in a grid row | A |
| 5 | Each StatTile contains a sparkline chart (small svg line graph), not just a number | C |
| 6 | A HierarchyTree is visible — collapsible rows with expand/collapse arrows, not a flat list | A |
| 7 | An ActivityTimeline is visible — timestamped events with entity-type icons, not a plain bullet list | A |
| 8 | An "Active Pipelines" section heading is visible with at least one PipelineCard below it | A |
| 9 | A QuickAccess grid is visible — icon+label tile cards in a grid layout | A |

**Schema — Classes (`/app/schema/classes`)**

| # | Item | Category |
|---|------|----------|
| 1 | A TabBar is visible at the top with tab labels for schema entities (Taxonomies, Schemes, Classes, etc.) | C |
| 2 | At least one tab has a numeric count badge next to its label | C |
| 3 | An eyebrow chip is visible above the page title | C |
| 4 | A route path badge showing `/schema/classes` is visible in the page title area | C |
| 5 | A FilterBar is visible (chip-based filter row or search bar) below the page header | A |
| 6 | A data table is visible with column headers | A |
| 7 | When a table row is clicked, an InspectorPanel opens to the right in a split layout — NOT a full-screen overlay or drawer that covers the table | A |

**Schema — Taxonomies (`/app/schema/taxonomies`)**

Same checklist as Schema — Classes, with route path `/schema/taxonomies`.

**Pipelines (`/app/pipelines`)**

| # | Item | Category |
|---|------|----------|
| 1 | A TabBar is visible with status-based labels: All, Running, Success, Idle, Failed | B |
| 2 | The tabs do NOT show state-based labels like Enabled or Disabled | B |
| 3 | A FilterBar is visible below the page header | A |
| 4 | PipelineCard components are visible — each shows a pipeline name, a flow visualization (connected step icons), and metrics (last run, counts) | A |

**Settings (`/app/settings`)**

| # | Item | Category |
|---|------|----------|
| 1 | The eyebrow label is lowercase ("● settings" or similar) — NOT all-caps ("ADMINISTRATION") | C |
| 2 | A route path badge showing `/settings` is visible in the page title | C |
| 3 | A TabBar is visible with counts on the tabs | C |
| 4 | The General tab shows form input fields directly (workspace name, path, branch, LLM config) — NOT a navigation grid of clickable tiles | B |
| 5 | A right-side column of ConfigTile summary cards is visible alongside the form fields | C |

---

## Step 3 — Aggregate results and write the remediation plan

Collect the Step 0 manifest and all visual review agent responses. Compute:
- Which components need replacement (from Step 0)
- Total items per page / items passing (from Step 2)
- Which pages have blocking failures

Write (do NOT overwrite) `documentation/ux-audit/remediation-plan-iter-N.md`:

```markdown
# Heimdall Fix — Iteration N of MAX

**Date:** YYYY-MM-DD
**Behavioral tests:** S-3 [PASS/FAIL], P-1 [PASS/FAIL], ST-4 [PASS/FAIL]

## Component Replacements (from catalog audit)
| Custom file | Heimdall equivalent | Wave |
|---|---|---|
| src/components/ontology/Sparkline.tsx | StatTile.sparkData | Wave 2 / dashboard |

## Visual Review Summary
| Page | Score | Blocking failures |
|------|-------|-------------------|
| Dashboard | 4/9 PASS | #5 (sparklines), #6 (HierarchyTree), #8 (Active Pipelines) |
...

## Work assignments

### Wave 1 — Shell / shared replacements (runs first, alone)
Fixes: [component replacements scoped to shell/shared] + [visual items #2, #3 if failing]
Files: ux/src/routes/app.tsx

### Wave 2 — Page agents (run in parallel after Wave 1 completes)

#### Agent: dashboard
Replacements: [list any component replacements for this page]
Visual fixes: [list visual checklist items]
Files: ux/src/routes/app/index.tsx

#### Agent: schema
...

#### Agent: pipelines
...

#### Agent: settings
...
```

Only include wave-2 agent sections for pages with actual failures or replacements. Omit pages that are fully green.

---

## Step 4 — Spawn fix agents in two waves

**Wave 1 — Shell / shared (alone, before Wave 2):**

Launch if ANY of these are true:
- The Step 0 manifest has Wave 1 replacements
- Dashboard visual items #2 or #3 are failing
- Any S-* behavioral test is failing

Shell agent context (current state — no separate shell component files exist):

> The app shell is a single file: `ux/src/routes/app.tsx`. It uses `ShellLayout` from `@tinkermonkey/heimdall-ui` with these props passed inline (no builder functions, no separate component files):
> - `appTitle={{ title: 'Context Studio' }}` — renders the app title in the sidebar top-left
> - `topbar={{ breadcrumbs, searchPlaceholder, onSearch }}` — do NOT pass `children`; use only documented props
> - `sidebar={{ sections, activeItemId, collapsed, onCollapse, onSelectItem }}` — one section, `title: ''`, six items
> - `statusbar={{ left, right }}` — uses Heimdall `statusbar__*` CSS classes in JSX
>
> CSS token rule: `rgb(var(--canvas-fg-1))` not `var(--canvas-fg-1)`.
> `--accent-primary` is amber. Use `--status-cyan` for cyan.
> Layer order in `src/index.css`: `@layer properties, theme, base, components, utilities, heimdall, app, graph;` — do not change.
> After changes: run `cd ux && npm run typecheck` and report errors.

**Wave 2 — Page agents (parallel):**

Use `subagent_type: "context-studio-frontend-expert"` for all.

Each agent prompt must include:
1. The Step 0 replacement manifest entries for this page (if any)
2. The exact failing visual checklist items with evidence from the review
3. The specific files most likely to need changes
4. The verified Heimdall prop APIs (read `.d.ts` files before using any prop — do not rely on documentation)
5. Instructions to run `cd ux && npm run typecheck` before finishing

**Dashboard agent context:**

> - File: `ux/src/routes/app/index.tsx`
> - `StatTile` props: `value`, `label`, `color`, `sparkData?: number[]`, `delta?: { value, label, direction }` — verify against `.d.ts`
> - `HierarchyTree` from Heimdall is a **children container** — use with `HierarchyRow` children; a wrapper at `ux/src/components/ontology/HierarchyTree.tsx` already handles data mapping
> - `ActivityTimeline` items: verify `ActivityEvent` shape in `.d.ts` before wiring
> - `PipelineCard` pipeline prop shape: verify in `.d.ts` — the `pipeline` object contains `id`, `name`, `status`, `flow`, `recent`, `lastRun`, `description`
> - `QuickAccessGrid` / `QuickAccessTile`: verify props in `.d.ts`
> - All imports: `from "@tinkermonkey/heimdall-ui"` — single import, no subpaths
> - Do NOT add sparkline data that is fabricated. If the API has no historical data, omit `sparkData` or use only the single current value.

**Schema agent context:**

> - Pages: `ux/src/routes/app/schema/`
> - `TabBar` tab shape: `{ id, label, count? }` — verify in `.d.ts`
> - `PageHeader` props: `eyebrow`, `title`, `idChip` (not a separate `IdTag` component)
> - `FilterBar`: verify props in `.d.ts`
> - For `InspectorPanel` (SC-5): use `InspectorPanel` from Heimdall in a CSS grid split layout alongside the table — NOT a Drawer overlay

**Pipelines agent context:**

> - Pages: `ux/src/routes/app/pipelines/`
> - `TabBar` tabs: `All`, `Running`, `Success`, `Idle`, `Failed` — filter by run status, not enabled/disabled
> - `PipelineCard` `pipeline` prop shape: verify in `.d.ts`

**Settings agent context:**

> - Page: `ux/src/routes/app/settings.tsx`
> - `PageHeader` eyebrow: pass `"settings"` (lowercase); if the component CSS uppercases it via `text-transform`, add a scoped CSS override in `studio.css`
> - `Field`, `TextInput` (with `mono` prop for paths), `Select`, `ConfigTile`: verify all props in `.d.ts`

---

## Step 5 — Wait for all agents, then verify

After all wave-2 agents return:

1. Run `cd ux && npm run typecheck` — if it fails, spawn a single targeted fix agent with the exact errors.
2. Capture fresh screenshots: `cd ux && npm run design-audit:capture 2>&1`
3. Spawn visual review agents again — compare to Step 2 results.

If any page that was previously passing now has new failures, spawn a targeted fix agent immediately.

---

## Step 6 — Update the gap inventory

Edit `documentation/ux-audit/heimdall-gap-inventory.md` surgically. Do NOT rewrite it from scratch.

**For each gap resolved this iteration:**
- Replace the `Category` cell with `✅ YYYY-MM-DD`
- Example: `| S-3 | ✅ 2026-05-24 | Canvas mode | ... |`

**For component replacements completed this iteration:**
- Mark the corresponding Category A gap as `✅ YYYY-MM-DD`
- If no gap existed for it, add a new row marked `✅ YYYY-MM-DD` immediately

**For any new custom-vs-Heimdall gaps discovered in Step 0 that were NOT fixed this iteration:**
- Add a new Category A row in the correct page section
- Include the custom file path and the Heimdall equivalent in the Issue column

**Update the Priority Order table** — remove fixed rows, add new gaps, re-number.

**Update CSS Cleanup:**
```bash
wc -l ux/src/design-system/studio.css ux/src/design-system/crud.css ux/src/design-system/graph.css
```

---

## Step 7 — Decide whether to loop

- All visual review items pass across all pages AND Step 0 manifest is empty → print final report and stop
- Iteration count < max → go back to Step 0 with iteration + 1
- Iteration count == max → print remaining failures and stop

Note: the loop continues if Step 0 still finds replacements, even if all visual items pass. A visually-passing page built on custom components is not done.

---

## Final report format

```
## Heimdall Fix — Final Report

**Iterations completed:** N / MAX
**Behavioral tests:** S-3 [PASS/FAIL], P-1 [PASS/FAIL], ST-4 [PASS/FAIL]

### Component replacements completed
| Custom file removed | Heimdall equivalent used | Iteration |
|---|---|---|
| src/components/shell/Sidebar.tsx | ShellLayout.sidebar prop | 1 |

### Visual review final scores
| Page | Score | Remaining failures |
|------|-------|--------------------|
| Dashboard | 9/9 PASS | — |
| Schema — Classes | 6/7 PASS | #7 InspectorPanel inline |
...

### Still open
| ID | Description | Blocker |
|----|-------------|---------|
| SC-5 | InspectorPanel inline split | Structural refactor needed |

### CSS reduction
studio.css: BEFORE → AFTER lines
crud.css:   BEFORE → AFTER lines
```
