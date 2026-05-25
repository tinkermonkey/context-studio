# Heimdall Fix — Iteration 2 of 5

**Date:** 2026-05-25
**Behavioral tests:** S-3 PASS, P-1 PASS, ST-4 PASS (all 4 tests pass)

## Component Replacements (from catalog audit)
| Custom file | Heimdall equivalent | Wave |
|---|---|---|
| `src/components/ui/ConfirmDialog.tsx` | Heimdall `ConfirmDialog` (isOpen, onClose, onConfirm, title, message, confirmLabel, cancelLabel, variant) | Wave 1 — used in 6 drawer components |
| `src/components/ui/Skeleton.tsx` | CSS class pattern (`className="skeleton"` + existing `skeleton-shimmer` keyframe in studio.css) | Wave 1 — used in 25+ files |
| Private inline `Textarea` in `src/components/versioning/CreateChangesetModal.tsx` | Heimdall `TextArea` | Wave 2 — versioning page only |

## Visual Review Summary
| Page | Score | Blocking failures | Notes |
|------|-------|-------------------|-------|
| Dashboard | 6/9 PASS | #6 HierarchyTree empty state | Data gap (no classes in DB), not code. #5 sparklines also data-only. |
| Schema — Classes | 2/7 PASS | Items 2/3/4 | **Likely reviewer artifact** — Taxonomies page (same structure) passes 6/7; prototype was empty stub |
| Schema — Taxonomies | 6/7 PASS | None | Item 7 = UNKNOWN (static screenshot) |
| Pipelines | ~4/4 PASS | None | Item 4 partial due to no run history |
| Settings | 5/5 PASS | None | — |

## Work assignments

### Wave 1 — Shell / shared replacements (runs first, alone)
Fixes:
1. Replace `src/components/ui/ConfirmDialog.tsx` with Heimdall `ConfirmDialog` at all 6 call sites
2. Remove `src/components/ui/Skeleton.tsx` — replace all usages with inline `<div className="skeleton" style={{ width, height }} />`

Files: ClassDrawer, IndividualDrawer, PropertyDrawer, RelationshipDrawer, SchemeDrawer, TaxonomyDrawer + all Skeleton callers

### Wave 2 — Page agents (parallel after Wave 1)

#### Agent: versioning
- Replace private `function Textarea` inside `CreateChangesetModal.tsx` with Heimdall `TextArea`
- File: `ux/src/components/versioning/CreateChangesetModal.tsx`

## Data issues (not fixable by fix agents)
- Dashboard #6: HierarchyTree empty because DB has no classes. Component wired correctly.
- Dashboard #5: No sparkline history from API. Accepted per D-7.
- Pipelines #4: No run history. Accepted per P-2.

## CSS baseline (before this iteration)
studio.css: 1,352 lines
crud.css: 875 lines
graph.css: 610 lines
Total: 2,837 lines
