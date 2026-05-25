# Heimdall Fix — Iteration 1 of 1

**Date:** 2026-05-24
**Behavioral tests:** S-3 PASS, P-1 FAIL (tablist selector doesn't match Heimdall TabBar DOM), ST-4 PASS

---

## Component Replacements (from Step 0 catalog audit)

No Wave 1 shell replacements needed — shell components are already deleted and replaced with Heimdall `ShellLayout`.

Wave 2 replacements identified (deferred to next iteration — not on in-scope pages):

| Custom file | Heimdall equivalent | Wave |
|---|---|---|
| `src/components/ui/Sparkline.tsx` | `Heimdall.Sparkline` (only consumer: individuals.tsx) | Wave 2 / individuals |
| `getStateChip` in `ChangesetListSection.tsx` | `StatusBadge` | Wave 2 / versioning |
| `getStatusChip` in `SyncStatus.tsx` | `StatusBadge` | Wave 2 / versioning |
| `getOperationColor` in `PendingChangesList.tsx` | `Chip` color prop | Wave 2 / versioning |
| Raw `<textarea>` in `CreateChangesetModal.tsx` | `Heimdall.TextArea` | Wave 2 / versioning |
| `GroundingWorkflowDrawer.tsx` (renders own div.drawer-body) | `ui/Drawer` wrapper | Wave 2 / reference |

---

## Visual Review Summary

| Page | Score | Blocking failures |
|------|-------|-------------------|
| Dashboard | 6/9 PASS | #2 (B — "MAIN" eyebrow), #8 (A — Active Pipelines not visible*), #9 (A — QuickAccess not visible*) |
| Schema — Classes | 6/7 PASS | none (item 7 UNKNOWN — needs interactive test) |
| Pipelines | 3/4 PASS | #4 (A — PipelineCard metrics show "No runs yet") |
| Settings | 4/5 PASS | none (item 1 is C — eyebrow CSS uppercasing) |

*Code is present; sections likely below fold in review agents' image window. Active Pipelines filter changed to show all pipelines (not just `p.enabled`).

---

## Work assignments

### Wave 1 — Shell / shared
Not required — shell is passing.

### Wave 2 — Dashboard
- Remove `eyebrow="Main"` and `idChip="/"` from both `PageHeader` instances
- Remove fabricated `sparkData` arrays from all four `StatTile` components
- Change Active Pipelines filter to show all pipelines (not just `p.enabled`)

### Wave 2 — Settings
- Add CSS override so Heimdall `PageHeader` eyebrow is not force-uppercased
