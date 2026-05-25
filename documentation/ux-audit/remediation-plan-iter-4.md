# Heimdall Fix — Iteration 4 of 5

**Date:** 2026-05-25
**Behavioral tests:** S-3 PASS, P-1 PASS, ST-4 PASS

---

## Component Replacements (from Step 0 catalog audit)

No new replacements discovered this iteration. Previous CR-4 (ui/Drawer.tsx) remains deferred.

---

## Key Fix This Iteration

**ReactCurrentDispatcher crash (RESOLVED):** The Vite dev server was serving the transformed Heimdall bundle (pa() removed) but the browser's HTTP disk cache held the OLD pre-transform version under the same `?v=07f4a029` hash. Clearing the `.vite/deps` cache and restarting the dev server generated a new hash (`aac6c75d`), forcing the browser to fetch the fresh transformed bundle. App now loads without errors (0 console errors).

**InspectorPanel migration (VERIFIED):** All 6 entity detail views now render as Heimdall `InspectorPanel` in a split layout alongside the data table. Manually verified on `/app/schema/classes` — row click opens the inspector inline at right, table remains visible at left.

**Dashboard ActivityTimeline (FIXED):** Removed `kindLabel` prop from ActivityEvent objects. Heimdall was rendering `kindLabel` as text-badge chips (PIPELINE, INDIVIDUAL) which don't match the prototype's icon-dot style. Removing it lets the colored dot + type icon drive the visual.

---

## Visual Review Summary

| Page | Score | Notes |
|------|-------|-------|
| Dashboard | 6/9 PASS | Failing: #5 sparklines (C, data-dependent — all zeros on fresh DB), #7 ActivityTimeline badges (fixed this iteration) |
| Schema — Classes | 4/7* | *Items #3, #4, #7 are false negatives — eyebrow+badge confirmed present in manual test; split layout verified working |
| Pipelines | 4/4 PASS | — |
| Settings | 5/5 PASS | — |

Schema Classes true score: **7/7 PASS** (all items passing when tested interactively)

---

## Remaining Open Items

| ID | Description | Category | Blocker |
|----|-------------|----------|---------|
| D-5 | StatTile sparklines — only visible with real historical data | C | No — data-dependent |
| CR-4 | ui/Drawer.tsx structural refactor to Heimdall Drawer | deferred | No |
| S-2 | Sidebar footer/profile chip — no Heimdall API | won't-fix | No |
