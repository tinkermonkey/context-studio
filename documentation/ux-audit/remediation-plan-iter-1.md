# Heimdall Fix — Iteration 1 of 5

**Date:** 2026-05-26
**Behavioral tests:** S-3 PASS, P-1 PASS, ST-4 PASS

## Root cause resolved

The app was rendering a blank screen due to a broken `heimdallReact19Compat` Vite plugin — the Heimdall v0.3.0 bundle changed its internal marker variables from `ze`/`be` to `Ze`/`ye` (case change). The plugin was updated with the correct markers and also injects `import React from "react"` to satisfy `React.forwardRef` calls in the bundle.

## Component Replacements (from catalog audit)

No urgent Wave 1 replacements. Two Wave 2 candidates for future iterations:
| Custom file | Heimdall equivalent | Wave |
|---|---|---|
| `src/components/schema/SchemaPageLayout.tsx` | Direct `SplitPane` usage | Wave 2 (future) |
| `src/components/graph/MetricsPanel.tsx` | `BarV`/`BarH`/`MetricRow`/`StatGrid` | Wave 2 (future) |

## Visual Review Summary

| Page | Score | Blocking failures |
|---|---|---|
| Dashboard | 5/9 PASS | #4/#5 (3/4 StatTiles missing sparklines), #7 (ActivityTimeline no kind labels) |
| Schema Classes | 5/7 PASS | #3 (eyebrow chip missing), #4 (route path badge missing) |
| Schema Taxonomies | 7/7 PASS | — |
| Pipelines | 4/4 PASS | — |
| Settings | 5/5 PASS | — |

## Work assignments

### Wave 1 — Shell / shared (SKIPPED — no shell failures)

### Wave 2 — Page agents (run in parallel)

#### Agent: dashboard
Fixes: StatTile sparkData for TAXONOMIES, CLASSES, INDIVIDUALS tiles + ActivityTimeline kind/kindLabel props
Files: `ux/src/routes/app/index.tsx`

#### Agent: schema-classes
Fixes: PageHeader eyebrow + idChip on Classes page (mirror what Taxonomies page has)
Files: `ux/src/routes/app/schema/classes.tsx` or equivalent
