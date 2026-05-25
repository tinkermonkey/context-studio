# Heimdall Fix — Iteration 3 of 5

**Date:** 2026-05-25
**Behavioral tests:** S-3 PASS, P-1 PASS, ST-4 PASS

## Component Replacements (from catalog audit)

| Custom file | Heimdall equivalent | Wave |
|---|---|---|
| `src/components/ui/Drawer.tsx` | `InspectorPanel` (header/actions) + raw Heimdall `Drawer` (shell) | Wave 1 |
| `src/components/schema/SchemaTable.tsx` | Heimdall `Table` with built-in pagination | Wave 2 |
| `src/components/schema/SchemaPageLayout.tsx` | `SplitPane` directly (thin wrapper, low priority) | Wave 2 / low |

**Wave 1 decision:** `ui/Drawer.tsx` is a high-leverage shared component (7+ drawer files import it) but its replacement is a structural refactor that risks regressions. Dashboard visual failures are page-scoped (Wave 2). Deferring Wave 1 Drawer replacement — this iteration focuses on blocking dashboard visual failures.

## Visual Review Summary

| Page | Score | Blocking failures |
|------|-------|-------------------|
| Dashboard | 6/9 PASS | #4 (StatTile card treatment), #7 (ActivityTimeline formatting) |
| Schema — Classes | 5/7 PASS | none (gaps #2, #4 are Category C) |
| Schema — Taxonomies | 6/7 PASS | none |
| Pipelines | 4/4 PASS | — |
| Settings | 5/5 PASS | — |

## Work assignments

### Wave 1 — Shell / shared replacements
Skipped — no shell visual failures, no S-* test failures. `ui/Drawer.tsx` replacement deferred (structural risk, no visual gap causing failures right now).

### Wave 2 — Page agents (run in parallel)

#### Agent: dashboard
**Blocking fixes:**
- Item #4: StatTile cards not clearly visible as distinct cards — investigate `tone`/`color` prop usage in `ux/src/routes/app/index.tsx`
- Item #7: ActivityTimeline rendered as raw log rows — verify `ActivityEvent` shape matches `.d.ts` type (entityType, entityLabel, user, action fields)

**Non-blocking:**
- Item #5: Sparklines (D-7 marked ✅ but review agent reports still missing) — verify `sparkData` actually being passed and arriving from API
