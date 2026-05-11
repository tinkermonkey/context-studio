# Context Studio — UX Handoff

Companion to `README.md`. The README is the **visual** spec — tokens, components, screens at a structural level. This document is the **behavioral** spec — flows, states, copy, accessibility, and the rules that govern how surfaces respond to user action.

If the README answers _"what does it look like?"_, this answers _"what happens when…?"_.

---

## Table of contents

1. [User model & vocabulary](#1-user-model--vocabulary)
2. [Core flows](#2-core-flows)
3. [State coverage per screen](#3-state-coverage-per-screen)
4. [Forms & CRUD behavior](#4-forms--crud-behavior)
5. [Destructive actions & confirmations](#5-destructive-actions--confirmations)
6. [Onboarding & first-run](#6-onboarding--first-run)
7. [Accessibility](#7-accessibility)
8. [Responsive / window-size behavior](#8-responsive--window-size-behavior)
9. [Copy specifications](#9-copy-specifications)
10. [Pipeline mental model](#10-pipeline-mental-model)

---

## 1. User model & vocabulary

The user is a **technical curator**: data engineer, ML engineer, ontologist, or research scientist building a knowledge graph to ground an LLM or agent. They're comfortable with IDEs, git, and structured data. Treat them as one.

**Always-true vocabulary:**

| Term         | Meaning                                                                                 |
| ------------ | --------------------------------------------------------------------------------------- |
| Workspace    | A local folder containing a schema, data, pipelines, and config. The unit of "project." |
| Taxonomy     | A namespaced hierarchy of classes (`life`, `climate`, `software`).                      |
| Class        | A type definition. Has properties, relationships, a domain, and instances.              |
| Property     | A typed attribute on a class.                                                           |
| Relationship | A typed edge between two classes.                                                       |
| Individual   | An instance of a class. The leaf data.                                                  |
| Pipeline     | A named extraction + ingestion flow that produces individuals.                          |
| Run          | One execution of a pipeline. Has a status, duration, counts, and a log.                 |
| Daemon       | The local graph process. Owns the index. Lives at `:7474`.                              |

These terms are load-bearing — UI labels, error messages, and docs all use them verbatim. Never substitute "type" for "class" or "record" for "individual."

---

## 2. Core flows

Each flow is a step-by-step path through the product. Every step names the **surface** (screen / overlay / dialog) and the **success transition.**

### 2.1 Create a new class

1. **Sidebar → Schema → Classes** (or ⌘K → "new class" → Action). Lands on Classes page.
2. Click **"+ New class"** (primary button, page head). Opens the **New Class dialog** (modal, 560px, 12px radius).
3. Dialog fields, in order: Name (mono, snake_case, required, autofocus), Display label, Domain (select, defaults to current taxonomy's domain), Parent class (typeahead over existing classes, optional), Description (textarea, markdown).
4. Inline validation: Name must match `/^[a-z][a-z0-9_]*$/`. Show validation error below the field on blur, not on every keystroke.
5. Submit: ⌘↵ or click **"Create class"** (primary). The dialog stays open with a spinner on the button for ≤300ms; on success it closes.
6. Success → Classes table refreshes, the new row is selected, the drawer opens to its detail. Toast: "Class created · `cls_<id>`" (success intent, 4s, dismissible).
7. Failure → dialog stays open, error banner above the form: `"Could not create class: <reason>"` in failure-intent style. Form values preserved.

### 2.2 Resolve a failed pipeline run

1. Statusbar shows red dot + "1 pipeline failed" (clickable, opens Pipelines).
2. Pipelines page → failed card has a `failed` chip and the latest run line shows the error count.
3. Click the card body to open the **Pipeline detail drawer** (right side, 480px). Drawer shows: definition, last 10 runs, last error log.
4. Click the failed run row → log panel scrolls into view, showing the structured error (step, code, message, stack-frame for code steps).
5. User edits the pipeline definition (e.g. fix the source URL). Save (⌘S or Save button). Form is dirty-aware — see § 4.
6. Click **"Run"** on the card. Status chip flips to `running`, statusbar dot flips to amber pulse, "1 pipeline running."
7. On success: status chip flips to `success`, toast "Pipeline ran · 12,480 records ingested."

### 2.3 Promote a draft taxonomy

(Taxonomies have a `draft` / `published` state. Drafts are local-only; publishing makes them part of the workspace's official schema.)

1. Schema → Taxonomies → select the draft. Drawer shows status chip `draft`.
2. Drawer head action: **"Publish…"** (ghost button). Opens **Publish dialog** with a diff summary (X classes added, Y modified, Z removed) and a required commit-style message field.
3. Submit: status chip flips to `published`, drawer closes, toast "Taxonomy published — `life · v1.4`."

### 2.4 Open / switch / create workspace

See [§ 6 Onboarding & first-run](#6-onboarding--first-run).

### 2.5 Run an ad-hoc command (⌘K)

1. ⌘K from anywhere. Palette opens. First slot is auto-focused; first result is pre-highlighted.
2. As the user types, results filter by fuzzy match against label, kind, and ID. Recents lead when the query is empty.
3. ↑↓ navigates. ↵ executes. Tab does **not** confirm — it inserts the highlighted item's label into the input as a continuation (so the user can refine).
4. ESC closes. The palette never blocks the underlying surface from re-opening.

---

## 3. State coverage per screen

Every screen must implement five states. The default specs in the README cover the **populated** state; this section pins the other four.

### General rules

| State   | Trigger                                    | Treatment                                                                                                                                                                                                           |
| ------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Loading | Initial fetch, refresh, after a mutation   | Skeletons (1px borders, `--canvas-bg-2` fill, 1.4s wave). Never blank space. ≤300ms — show skeleton; >300ms — keep skeleton; <100ms — skip skeleton.                                                                |
| Empty   | No data exists yet                         | Centered illustration _placeholder_ (line-icon, 48px, `--canvas-fg-4`), one-line title, two-line guidance, single primary CTA.                                                                                      |
| Partial | Some data, but a critical piece is missing | Render what's there; show an inline banner above the missing region with a remediation CTA.                                                                                                                         |
| Error   | Fetch failed, daemon down, network         | Page-level error card: failure-intent border-left, technical message in mono, "Retry" + "Open daemon log" actions.                                                                                                  |
| Offline | Daemon connection lost                     | Statusbar dot turns rose, statusbar text "graph daemon disconnected." Mutations disabled across the app — primary buttons disabled with tooltip "Daemon disconnected." Reads remain available from the local cache. |

### Per-screen empty states

| Screen                 | Empty title                   | Empty guidance                                                                  | CTA                                                                                                |
| ---------------------- | ----------------------------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Dashboard              | "Empty workspace"             | "Add a taxonomy to start defining what your knowledge graph contains."          | "+ New taxonomy"                                                                                   |
| Schema → Taxonomies    | "No taxonomies yet"           | "A taxonomy groups related classes. Most workspaces start with one or two."     | "+ New taxonomy"                                                                                   |
| Schema → Classes       | "No classes in this taxonomy" | "Classes are the types your individuals will conform to."                       | "+ New class"                                                                                      |
| Schema → Properties    | "No properties on this class" | "Properties are typed attributes — name, latitude, accuracy, etc."              | "+ Add property"                                                                                   |
| Schema → Relationships | "No relationships defined"    | "Relationships are typed edges between classes."                                | "+ New relationship"                                                                               |
| Data → Individuals     | "No individuals yet"          | "Run a pipeline or import a dataset to populate this class."                    | "+ New individual" CTA (with "Run pipeline" and "Import…" added when those features are available) |
| Pipelines              | "No pipelines configured"     | "A pipeline extracts individuals from a source and writes them to a class."     | "+ New pipeline"                                                                                   |
| External Reference     | "No reference sources"        | "Connect documents, datasets, or APIs to ground your graph in real-world data." | "+ Add source"                                                                                     |

### Skeletons — what counts

Skeletons mirror the **shape** of the populated content. A table renders 6 skeleton rows (each row is a 36px high `--canvas-bg-2` rectangle). A stat tile renders the colored bar + a 14px and 28px gray bar. A panel renders its head bar + 3 skeleton lines. **Never use a generic spinner** in the canvas — only on buttons mid-action.

### Error states — categories & treatment

| Category   | Examples                       | Treatment                                                           |
| ---------- | ------------------------------ | ------------------------------------------------------------------- |
| Validation | Form field invalid             | Inline below field, failure-intent text, mono if echoing identifier |
| Action     | "Could not save class"         | Banner inside the open dialog/drawer; preserves form state          |
| Resource   | Class not found, run not found | Page-level — replace canvas with error card, keep chrome            |
| System     | Daemon down, network down      | Global statusbar treatment + per-action disabling                   |

---

## 4. Forms & CRUD behavior

### Field-level

- **Validation timing:** never on keystroke; on blur for sync rules; on submit for async (uniqueness, server-side). Submit-time validation marks every offending field at once.
- **Error display:** 11.5px failure-intent text directly below the field, max one line. Long messages truncate with a tooltip.
- **Required fields:** show `*` after the label in `--failure` color. Don't add "(required)" text.
- **Hint text:** 10.5px `--canvas-fg-3` on the label row, right-aligned. e.g. `snake_case`, `markdown supported`.
- **Disabled fields:** `opacity: 0.5`, `cursor: not-allowed`, no focus ring. If disabled because of a dependency, show a tooltip explaining why.

### Dirty state & autosave

- **Drawers** (right-side detail editors): autosave on field blur, 250ms debounce. Show "Saved 2s ago" mono in the drawer head. On error, revert to last-good and show inline failure.
- **Dialogs / page-level forms:** explicit save. Submit button disabled until dirty. Closing the dialog with unsaved changes triggers a confirm (see § 5).
- **Multi-step / wizard forms:** only Pipeline definition. Step state persists across navigations until explicitly canceled or saved.

### Undo

- Every destructive mutation that succeeds emits a toast with **"Undo"** as a secondary action. Undo window: 8 seconds. After expiry the toast fades, undo unavailable.
- Undo applies to: delete class, delete property, delete relationship, delete individual, archive taxonomy, delete pipeline, delete pipeline run.
- Undo does **not** apply to: pipeline runs (use cancel instead), publish (immutable), file system mutations outside the workspace.

### Save / discard semantics

| Surface                  | Save trigger         | Discard trigger                                         |
| ------------------------ | -------------------- | ------------------------------------------------------- |
| Drawer                   | autosave on blur     | revert button in drawer head (only visible while dirty) |
| Dialog                   | explicit Save button | Cancel button or ESC (with confirm if dirty)            |
| Inline edit (table cell) | blur or ↵            | ESC reverts                                             |

---

## 5. Destructive actions & confirmations

**Confirmation policy:** require an explicit confirmation when an action is **(a) destructive AND (b) affects more than the immediately visible record OR (c) cannot be undone within 8s.**

### What requires confirmation

| Action                         | Reason                            | Treatment                                  |
| ------------------------------ | --------------------------------- | ------------------------------------------ |
| Delete class with ≥1 instance  | Cascades to individuals           | Type-to-confirm: user types the class name |
| Delete property in use         | Cascades to data                  | Standard confirm                           |
| Delete pipeline                | Removes run history               | Standard confirm                           |
| Delete workspace from "Recent" | Removes only the entry, not files | None — undoable via toast                  |
| Publish taxonomy               | Immutable                         | Standard confirm with diff summary         |
| Reset workspace                | Wipes local cache                 | Type-to-confirm: user types `reset`        |
| Force-close daemon             | Interrupts running pipelines      | Standard confirm listing affected runs     |

### What does NOT require confirmation

- Delete a class with no instances (undoable via toast)
- Delete an individual (undoable)
- Cancel a running pipeline (cancellable is non-destructive in our model)
- Archive (reversible)
- Discard form changes when no other side effects

### Confirmation dialog anatomy

- **Standard confirm** — 440px modal, title (sentence case verb-phrase: "Delete class?"), body (one paragraph plain English, then one mono line listing the affected resource), primary destructive button (rose/danger), Cancel ghost. ESC cancels.
- **Type-to-confirm** — same chrome, plus a mono input `Type "<name>" to confirm`. Destructive button stays disabled until exact match. No copy-paste hints.

### Copy patterns

- Title: "Delete class?", "Reset workspace?", "Publish taxonomy?"
- Primary CTA: same verb as title, no exclamation: "Delete class", "Reset workspace", "Publish"
- Body: state the consequence in one sentence, then the scope in mono on a new line. Don't apologize, don't soften.

Example:

> **Delete class?**
> This will remove the class and all 1,247 individuals that reference it. This cannot be undone.
> `cls_organism · life`
> [Cancel] [**Delete class**]

---

## 6. Onboarding & first-run

### First run — no workspace open

The app launches into the **Workspace switcher overlay**, not the Dashboard. No chrome behind it (or behind it is the empty shell with a single brand mark centered, 96px, faded to 30%).

Switcher head copy:

> **Open a workspace**
> A workspace is a local folder containing your schema, data, pipelines, and config.

Three primary actions, large tiles in a row:

- **Open folder…** — opens the OS file picker. The selected folder is checked for a `.context-studio/` directory; if missing, prompt to initialize.
- **New workspace…** — same picker, plus a name field. Creates `.context-studio/` and a starter taxonomy.
- **Clone from git…** — URL field + destination folder. Clones, then opens.

Below: **Recent** list (only populated on second-run+). Each row: name, mono path, mono cls/ind counts, "last opened 2h ago." ESC does not dismiss the switcher on first-run.

### Second run — workspace already chosen

App launches into the last-used workspace at the last-visited route. If the workspace folder is missing or the daemon can't connect, show a page-level error card with options to **Retry**, **Choose another workspace**, or **Reset**.

### First-time-in-an-empty-workspace tutorial

When a workspace has zero taxonomies, the Dashboard renders a **3-step setup card** instead of the stat grid:

1. **Define a taxonomy** → "+ New taxonomy" (active)
2. Add classes (disabled until step 1 done)
3. Run a pipeline (disabled until step 2 done)

Each step is a single line with a check / number indicator. Once all three are complete, the card auto-collapses into a "Setup complete" mono line that the user can dismiss.

No modals, tours, or tooltips. The product is its own tutorial.

---

## 7. Accessibility

### Targets

- WCAG **2.2 AA**.
- Keyboard parity: every action reachable by keyboard.
- Screen-reader: NVDA + VoiceOver tested on the 7 primary screens + palette + workspace switcher.

### Color contrast

Verify each pairing meets AA (4.5:1 for body, 3:1 for large/UI):

| Pair                                                   | Result                    | Action if fails                                                                                                      |
| ------------------------------------------------------ | ------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `--canvas-fg-1` (`#0B1220`) on `--canvas-bg` (`#FFF`)  | ✅ pass                   | —                                                                                                                    |
| `--canvas-fg-2` (`#475569`) on `--canvas-bg`           | ✅ pass                   | —                                                                                                                    |
| `--canvas-fg-3` (`#64748B`) on `--canvas-bg`           | ✅ pass                   | —                                                                                                                    |
| `--canvas-fg-4` (`#94A3B8`) on `--canvas-bg`           | ⚠️ borderline (3.0:1)     | Use only for non-essential placeholder/disabled                                                                      |
| `--accent-cyan-deep` (`#0E7EA3`) on `--canvas-bg`      | ✅ pass for buttons/links | —                                                                                                                    |
| `--accent-cyan` (`#22D3EE`) on `--canvas-bg`           | ❌ fails for text         | Never set body text in `--accent-cyan`. Use `--accent-cyan-deep`. Cyan is for **fills, dots, and strokes** on light. |
| `--shell-fg-1` (`#E6EDF3`) on `--shell-bg` (`#0B0F14`) | ✅ pass                   | —                                                                                                                    |
| `--shell-fg-3` (`#6E7A87`) on `--shell-bg`             | ⚠️ borderline             | Avoid for body text; OK for icons + disabled                                                                         |

### Focus

- Every focusable element shows a **3px cyan focus ring** (`box-shadow: 0 0 0 3px rgba(34,211,238,0.40)`). 0.40 alpha (not 0.13) for AA.
- Tab order follows DOM order. Skip-link not required (no top banner).
- Focus is **trapped** inside modals, dialogs, command palette, and workspace switcher. ESC releases.
- Visible focus is **never** removed via `outline: none` without a replacement.

### Keyboard shortcuts

Documented in README § 9. Additional accessibility-only:

- `F6` — cycle focus between sidebar / topbar / canvas / statusbar regions
- `Alt + ←` / `Alt + →` — back / forward in route history
- `?` — open keyboard shortcuts help dialog (lists all bindings)

### Screen-reader labels

- Every icon-only button has an `aria-label` matching its tooltip.
- Status chips include a visually-hidden `(success)` / `(failure)` / `(warning)` suffix.
- The pulsing daemon dot in the statusbar has `aria-label="Graph daemon connected"` / `…disconnected`.
- Tables use `<th scope="col">` and `<caption class="sr-only">`.

### Motion

- Honor `prefers-reduced-motion: reduce` — disable: dot pulse, palette slide-in, sidebar collapse animation, toast slide-in. Replace with instant transitions.

### Color independence

- Status is **never** conveyed by color alone. Every status chip has both a dot and a text label. Every domain swatch on a hierarchy node is paired with the class name (mono, not color-coded).

---

## 8. Responsive / window-size behavior

Desktop-only product. Minimum supported window size: **1024 × 720**. Below this, render a "Window too small" overlay with a single line: "Context Studio needs at least 1024 × 720."

### Breakpoints

| Width     | Behavior                                                                                                              |
| --------- | --------------------------------------------------------------------------------------------------------------------- |
| ≥ 1440    | Default. All layouts as specified.                                                                                    |
| 1280–1440 | Sidebar stays expanded. Dashboard 2-column area becomes 1.2fr / 1fr.                                                  |
| 1024–1280 | Sidebar auto-collapses to 64px. User can re-expand; preference persists per-window. Dashboard stat grid wraps to 2×2. |
| < 1024    | "Window too small" overlay.                                                                                           |

### Drawers vs. dialogs

- Detail drawer always 400–480px regardless of window width — it caps content rather than scaling.
- Modals cap at 720px wide.

### Tables

- Tables horizontally scroll inside their `.table-wrap` rather than reflowing.
- The mono ID column is sticky-left.

---

## 9. Copy specifications

### Voice rules (from README § 3, expanded)

- Sentence case for everything UI: titles, buttons, menu items, dialog headers.
- Imperative for primary actions: "Create class," not "Create a new class."
- Identifiers, file paths, counts, version strings → mono, verbatim.
- No emoji. No exclamation points. No "Oops."

### String inventory — primary actions

Standardize these strings. Use them verbatim across the product.

| Concept    | Button            | Confirmation title               | Toast on success                                |
| ---------- | ----------------- | -------------------------------- | ----------------------------------------------- |
| Create     | "+ New \<thing\>" | n/a                              | "\<Thing\> created · \<id\>"                    |
| Save       | "Save"            | n/a                              | "Saved" (only if not autosaved)                 |
| Delete     | "Delete"          | "Delete \<thing\>?"              | "\<Thing\> deleted · Undo"                      |
| Archive    | "Archive"         | "Archive \<thing\>?"             | "\<Thing\> archived · Undo"                     |
| Publish    | "Publish…"        | "Publish \<thing\>?"             | "\<Thing\> published · \<version\>"             |
| Run        | "Run"             | n/a (running is non-destructive) | "Pipeline started" → "Pipeline ran · N records" |
| Cancel run | "Cancel run"      | n/a                              | "Run canceled"                                  |
| Refresh    | "Refresh"         | n/a                              | (no toast)                                      |

### Error message patterns

`<verb-phrase> failed: <reason>`

- "Could not create class: name `organism` is already used in `life`."
- "Pipeline failed: connection refused at step `extract`."
- "Daemon disconnected: cannot reach `:7474`."

Reasons should reference the offending identifier in mono. Never expose stack traces to the user — those go in the daemon log linked from the error card.

### Empty-state copy

See § 3. Two-line maximum. Don't be clever.

### Tooltips

- ≤ 6 words.
- Sentence case. No period.
- Used only when the visible label is insufficient (icon-only buttons, truncated text, disabled-with-reason).

---

## 10. Pipeline mental model

The pipeline is the trickiest UX in the product. Pin the model explicitly so the team builds it the same way every time.

### Concepts

- A **pipeline** is a definition: source + transforms + write target. It lives in the workspace, version-controlled.
- A **run** is one execution. Has a start/end timestamp, a status, per-step counts, and a log.
- Runs are **not** stored on the pipeline indefinitely — last 50 are kept, older are archived to disk.

### Lifecycle of a run

```
queued → running → (success | failed | canceled)
```

- `queued` — daemon accepted the request, waiting for a worker. Statusbar shows "1 pipeline queued." ≤2s typical.
- `running` — animated pulse on the status chip; current step highlighted in the flow strip; per-step counts increment live.
- `success` — green chip; foot row updates with final counts; toast.
- `failed` — red chip; error log scrolls into view in the drawer; statusbar shows "1 pipeline failed" (red dot).
- `canceled` — gray chip; partial counts retained; no toast.

### What triggers a run

- Click the **"Run"** button on a pipeline card or in the drawer head.
- ⌘K → "run pipeline \<name\>".
- A scheduled run (cron-style; configured in the pipeline definition).
- An external trigger via the daemon API.

User-initiated runs and scheduled runs are visually identical in the run history but have a small mono badge: `manual` / `scheduled` / `api`.

### What cancels a run

- Click **"Cancel run"** on the running card. Confirmation: none — cancellation is reversible (just re-Run).
- Closing the workspace cancels in-flight runs and emits "Run canceled — workspace closed" log entries.
- Force-quitting the app marks runs as `canceled` with reason `app-terminated` on next launch.

### What happens when a run fails mid-flight

- The pipeline halts at the failed step. **Partial writes are not rolled back** — Context Studio is intentionally append-only. The error log records exactly which records were written before the failure (e.g. "wrote 8,302 of estimated 12,480 individuals before failure at step `resolve`").
- A failed run never auto-retries. The user must click Run again, after editing the definition or fixing the underlying source.
- "Resume from step" is **not** in the v1 design — every run starts from the source. If the team plans to add it later, reserve a "resume" affordance slot in the run row.

### What the user sees on the dashboard

- Active pipelines panel shows up to 4 cards. If more, a "View all" link routes to Pipelines.
- A failed pipeline always pins to the top of the list until acknowledged (clicked into).

---

## Appendix — what's still open

These items are deliberate gaps in the UX that the implementation team will need to resolve, with my recommendation:

1. **Multi-user / collaborative editing** — out of scope for v1 (the README footer "Maya Chen / local · main" is placeholder). Recommend punt.
2. **Permissions** — workspace-level only in v1 (you opened it, you can edit it). Recommend punt.
3. **Search across the workspace** — the palette covers most of this. A dedicated full-text search across descriptions/properties/individuals is not in v1. Recommend defer to v1.1.
4. **Localization** — English only for v1. Tokenize strings now to ease later i18n (no inline strings in JSX).
5. **Telemetry / analytics events** — not specified here. Coordinate with the data team; suggest event names mirror the action verbs in § 9.

End of UX handoff.
