# Context Studio — Design Handoff

This document hands off the full Context Studio visual design to the team building the production app. It describes **what to build**, **what design assets exist**, and **how to use the design system** for any screen, surface, or future feature.

If you only read one thing, read [§ 4 The two-surface model](#4-the-two-surface-model) and [§ 7 How to use the design system](#7-how-to-use-the-design-system).

---

## Table of contents

1. [Product overview](#1-product-overview)
2. [What's in this project](#2-whats-in-this-project)
3. [Brand & voice](#3-brand--voice)
4. [The two-surface model](#4-the-two-surface-model)
5. [Foundations — color, type, spacing, motion](#5-foundations--color-type-spacing-motion)
6. [Components](#6-components)
7. [How to use the design system](#7-how-to-use-the-design-system)
8. [Screens](#8-screens)
9. [Interactions & keyboard](#9-interactions--keyboard)
10. [What NOT to port from the prototype](#10-what-not-to-port-from-the-prototype)
11. [Open questions](#11-open-questions)

---

## 1. Product overview

Context Studio is a **local desktop application** for building and curating knowledge graphs to power retrieval-augmented generation and agent workflows. It is an **IDE for ontologies**: persistent dark chrome, a workspace-rooted file/data model, a command palette, and a status bar showing live system state.

The redesign covers seven primary screens:

1. **Dashboard** — workspace overview, hierarchy preview, active pipelines, recent activity
2. **Schema** — Taxonomies / Classes / Properties / Relationships (the schema authoring surface)
3. **Data** — Individuals / Datasets (instances of classes)
4. **Pipelines** — extraction + ingestion flows with run history
5. **External Reference** — sources and grounding workflows
6. **Configuration** — workspace settings
7. **Workspace switcher** + **Command palette** — overlays available from anywhere

**Fidelity is hi-fi.** Hex values, sizes, motion timings, and component anatomy in this document are final. Recreate pixel-perfectly using the target codebase's primitives.

---

## 2. What's in this project

```
Context Studio.html        Entry point — script tags + root div
app.jsx                    Router + tweak/preference application
data.js                    Hardcoded sample data (replace in prod)
tweaks-panel.jsx           Prototyping affordance — DO NOT PORT

components/
  shell.jsx                Titlebar, Sidebar, Topbar, Statusbar,
                           CommandPalette, WorkspaceSwitcher, NAV_TREE
  hierarchy.jsx            KGRow / KGNode — the graph hierarchy viewer
  pipeline-card.jsx        PipelineCard
  page-dashboard.jsx       Dashboard composition
  page-schema.jsx          Schema (taxonomies / classes / properties / relationships)
  page-individuals.jsx     Data → Individuals
  page-settings.jsx        Configuration
  page-rest.jsx            Pipelines, External Reference, etc.
  graph-view.jsx           Graph visualization
  modal.jsx, dialogs.jsx   Dialog primitives
  store.jsx                State container
  icons.jsx                Inline-SVG icon set (Lucide-style outline)

styles/
  tokens.css               FOUNDATION — color, type, spacing, radius, shadow tokens
  studio.css               Shell, canvas, components, dark-canvas mode
  crud.css                 Modals, forms, toasts
  graph.css                Graph view
  individuals.css          Individuals page
  settings.css             Settings page

preview/                   23 visual reference cards — open any in a browser
                           to see a token, palette, or component in isolation

README.md                  Voice + visual foundations + iconography overview
SKILL.md                   Skill definition (allows this system to be invoked
                           from other projects)
```

**Read order for an implementer:**

1. This handoff
2. `README.md` — design system reference
3. `styles/tokens.css` top to bottom — every variable
4. `styles/studio.css` — shell + canvas + every component class
5. `components/shell.jsx` — chrome composition
6. Pages in order: dashboard → schema → individuals → pipelines

---

## 3. Brand & voice

**Mark.** Cyan→deep-cyan 135° gradient (`#22D3EE` → `#0E7EA3`) with a 3-dot stamped pattern. Used as a 28–44px rounded square in chrome (sidebar brand row, splash). On dark only — never place the mark on white.

**Wordmark.** "Context Studio", Inter 600/-0.01em. Optional eyebrow `CTX · v1.4` in JetBrains Mono, uppercase, 0.1em tracking.

**Voice.**

- Terse, technical, sentence case.
- State the consequence; never apologize. "Pipeline failed: connection refused." Not "Oops, something went wrong."
- Use real domain terms (class, property, taxonomy, individual). Don't soften them.
- Mono for any identifier, path, or count: `cls_organism · 1,247`.
- No emoji anywhere. Outline icons only.

---

## 4. The two-surface model

The studio is built on **two concentric surfaces**:

- **Shell** — always dark (`#0B0F14`). The titlebar, sidebar, topbar, statusbar, command palette, and dialogs. This is the desktop chrome and **never inverts.**
- **Canvas** — the work surface inside the shell. Defaults to **light** for focused authoring; can be flipped to **dark** via a user preference (`body.dark-canvas`). When dark, the canvas is `#14191F` — a slate tone that sits between the shell and shell-surface so the entire studio reads as a single dark surface.

**This is the most important architectural idea.** Tokens are split into `--shell-*` (constant chrome) and `--canvas-*` (work surface, with a dark-mode override). **Do not collapse them into one theme.**

**Defaults (production):** cyan accent, neutral-dark shell, light canvas, titlebar visible, statusbar visible.

```
┌─ titlebar (36px, --shell-bg gradient) ────────────────────────────┐
│  ⚪⚪⚪  Context Studio  —  ~/Projects/molgraph-research ▾   ⌘K  │
├──────────────┬────────────────────────────────────────────────────┤
│              │  topbar (52px, --shell-bg-2)                       │
│  sidebar     │  • molgraph-research / Schema / Classes      ⌘K   │
│  (240px,     ├════════════════════════════════════════════════════┤
│  --shell-bg) │                                                    │
│              │  CANVAS (light by default, scrollable)             │
│              │  --canvas-bg / --canvas-fg-1                       │
│              │                                                    │
│              ├────────────────────────────────────────────────────┤
│              │  statusbar (26px, --shell-bg-2)                    │
└──────────────┴────────────────────────────────────────────────────┘
```

---

## 5. Foundations — color, type, spacing, motion

All tokens live in `styles/tokens.css`. Import that first, then `studio.css`. Visual references are in `preview/colors-*.html`, `preview/type-*.html`, `preview/spacing-scale.html`, `preview/radius-scale.html`, `preview/elevation.html`.

### Color — shell (constant dark chrome)

| Token               | Value     | Use                                                   |
| ------------------- | --------- | ----------------------------------------------------- |
| `--shell-bg`        | `#0B0F14` | Titlebar base, sidebar                                |
| `--shell-bg-2`      | `#0F141B` | Topbar, statusbar                                     |
| `--shell-surface`   | `#131A23` | Hover/active surface inside shell, palette background |
| `--shell-surface-2` | `#1A2230` | Deeper hover, palette item active                     |
| `--shell-border`    | `#1E2733` | Subtle dividers                                       |
| `--shell-border-2`  | `#2A3645` | Visible borders, focused inputs                       |
| `--shell-fg-1`      | `#E6EDF3` | Primary text                                          |
| `--shell-fg-2`      | `#A6B1BD` | Secondary text                                        |
| `--shell-fg-3`      | `#6E7A87` | Muted text, icon resting                              |
| `--shell-fg-4`      | `#475569` | Disabled / placeholder                                |

### Color — canvas (light, default)

| Token           | Value     | Use                        |
| --------------- | --------- | -------------------------- |
| `--canvas-bg`   | `#FFFFFF` | Main work surface          |
| `--canvas-bg-2` | `#F7F9FB` | Table headers, inset zones |
| `--canvas-card` | `#FFFFFF` | Panels, stat tiles, drawer |
| `--canvas-bd`   | `#E5E9EE` | Hairline borders           |
| `--canvas-bd-2` | `#D6DCE3` | Visible borders            |
| `--canvas-fg-1` | `#0B1220` | Primary text               |
| `--canvas-fg-2` | `#475569` | Secondary text, body copy  |
| `--canvas-fg-3` | `#64748B` | Muted text, captions       |
| `--canvas-fg-4` | `#94A3B8` | Placeholder, disabled      |

### Color — canvas (dark, `body.dark-canvas`)

| Token                             | Value     |
| --------------------------------- | --------- |
| `--canvas-bg`                     | `#14191F` |
| `--canvas-bg-2` / `--canvas-card` | `#1B222A` |
| `--canvas-bd`                     | `#2A323C` |
| `--canvas-bd-2`                   | `#3A4452` |
| `--canvas-fg-1`                   | `#E6EDF3` |
| `--canvas-fg-2`                   | `#B0BAC5` |
| `--canvas-fg-3`                   | `#7E8A98` |
| `--canvas-fg-4`                   | `#5A6573` |

In dark-canvas mode the topbar pulls down to `--shell-bg` (so chrome doesn't read as "lit up" against the darker canvas), chips swap to dark-tinted pastels, and primary buttons flip to the cyan accent on dark text.

### Color — accent

**Cyan is the only accent that signals action and state.** Use it sparingly — in normal screens it should be on **one** focused element at a time (active nav, focus ring, primary button on dark, env pill).

| Token                | Value     | Use                                                |
| -------------------- | --------- | -------------------------------------------------- |
| `--accent-cyan`      | `#22D3EE` | The accent — focus rings, active markers, env pill |
| `--accent-cyan-2`    | `#06B6D4` | Slightly deeper variant                            |
| `--accent-cyan-deep` | `#0E7EA3` | Buttons on light canvas, links, deep emphasis      |

For tinted backgrounds, derive via `color-mix(in oklab, var(--accent-cyan) 12%, transparent)` rather than hand-mixing.

### Color — primary scale (cyan 50→900)

`#E7F2F6` · `#CFE5ED` · `#B7D8E3` · `#9FCBDA` · `#87BFD1` · `#3E98B5` · `#268BAC` · `#0E7EA3` · `#084C62`

### Color — studio accents (state & domain only)

These exist for status (success/warning/error/info) and for domain-coding the hierarchy. **Never use them as a brand action color.**

| Name      | Hex       | Reserved for                                               |
| --------- | --------- | ---------------------------------------------------------- |
| `cyan`    | `#22D3EE` | Default domain, action accent                              |
| `violet`  | `#A78BFA` | software domain (in a 4-color palette) — also extract step |
| `emerald` | `#10B981` | success intent · life domain                               |
| `amber`   | `#F59E0B` | warning intent · climate domain · resolve step             |
| `rose`    | `#F43F5E` | failure intent                                             |
| `indigo`  | `#818CF8` | software domain                                            |

### Color — domain palette (4 domains, used as a 2.5–3px swatch on hierarchy nodes)

| Domain     | Hex                 |
| ---------- | ------------------- |
| `life`     | `#34D399` (emerald) |
| `climate`  | `#FBBF24` (amber)   |
| `software` | `#818CF8` (indigo)  |
| `default`  | `#22D3EE` (cyan)    |

### Color — semantic intents

| Intent    | Text      | Background | Border    |
| --------- | --------- | ---------- | --------- |
| success   | `#065F46` | `#ECFDF5`  | `#A7F3D0` |
| warning   | `#92400E` | `#FFFBEB`  | `#FDE68A` |
| failure   | `#9F1239` | `#FFF1F2`  | `#FECDD3` |
| info      | `#0E7490` | `#ECFEFF`  | `#A5F3FC` |
| secondary | `#5B21B6` | `#F5F3FF`  | `#DDD6FE` |

In dark-canvas mode chips invert to a dark-tinted pastel — see `studio.css` `.chip` overrides.

### Typography

| Family             | Tokens        | Use                                                          |
| ------------------ | ------------- | ------------------------------------------------------------ |
| **Inter** (sans)   | `--font-sans` | All UI: body, headings, buttons, labels                      |
| **JetBrains Mono** | `--mono`      | IDs, paths, kbd, eyebrows, table headers, stat numbers, code |

Mono is **load-bearing**, not decorative. Anything that is technically an identifier, path, command, key, or measured value goes in mono. This is what makes the product read as an IDE rather than an app.

**Scale** (see `preview/type-scale.html`):

| Token         | Size | Weight | Use                 |
| ------------- | ---- | ------ | ------------------- |
| `--text-6xl`  | 60   | 800    | Hero (rare)         |
| `--text-5xl`  | 48   | 800    | Display             |
| `--text-4xl`  | 36   | 800    | H2                  |
| `--text-3xl`  | 30   | 700    | H3                  |
| `--text-2xl`  | 24   | 700    | Page title          |
| `--text-xl`   | 20   | 500    | Modal title         |
| `--text-lg`   | 18   | 600    | Section header      |
| `--text-base` | 16   | 400    | Emphasized body     |
| `--text-sm`   | 14   | 400    | **Default UI text** |
| `--text-xs`   | 12   | 500    | Caption / button-xs |

Body text: 13–14px Inter. Page titles: 24px / 700 / -0.015em. Headings tighten letter-spacing as size grows (-0.01em at 30, -0.02em at 36+).

### Spacing

Tailwind 4px scale. `--space-1` (4) · `--space-2` (8) · `--space-3` (12) · `--space-4` (16) · `--space-5` (20) · `--space-6` (24, default card padding) · `--space-8` (32) · `--space-10` (40) · `--space-12` (48) · `--space-16` (64).

**Card padding:** 16–24px. **Gap between sections:** 16–24px. **Sidebar width:** 240px expanded, 64px collapsed. **Titlebar:** 36px. **Topbar:** 52px. **Statusbar:** 26px.

### Radius

| Token           | px   | Use                                        |
| --------------- | ---- | ------------------------------------------ |
| `--radius-sm`   | 2    | Divider chips, hairline indicators         |
| (4)             | 4    | Chips, table corners, hierarchy node-pills |
| `--radius-md`   | 6    | Buttons, inputs, icon buttons, nav items   |
| `--radius-lg`   | 8    | Panels, cards, drawers                     |
| `--radius-xl`   | 12   | Modals, command palette                    |
| `--radius-full` | 9999 | Avatars, env pill, status dots             |

### Shadows

Used sparingly. The studio leans on **borders for separation, not elevation.**

- Cards/panels: 1px border, **no shadow**
- `--shadow`: `0 1px 3px 0 rgba(0,0,0,0.10), 0 1px 2px -1px rgba(0,0,0,0.10)` — subtle hover lift
- `--shadow-md`: `0 4px 6px -1px rgba(0,0,0,0.10), 0 2px 4px -2px rgba(0,0,0,0.10)` — menus, popovers
- Modal/palette only: `0 30px 60px rgba(0,0,0,0.6)` — overlay over backdrop blur

### Motion

- Sidebar collapse, panel open/close: 120–160ms ease
- Command palette / dialogs: 140–160ms ease-out with a 6px slide-in
- Button/icon hover: 120ms ease
- Statusbar dot pulse: 1.6s ease-out infinite, `transform: scale(0.6→1.4)` + opacity 0.5→0

---

## 6. Components

Every component below has a visual reference card in `preview/`. CSS lives in `styles/studio.css` (and `crud.css` for forms/modals). All are realized as JSX in `components/` for the prototype.

### Chrome (always dark)

| Component | File                              | Anatomy                                                                          |
| --------- | --------------------------------- | -------------------------------------------------------------------------------- |
| Titlebar  | `shell.jsx` `Titlebar`            | 36px tall · traffic lights · workspace path button · ⌘K chip                     |
| Sidebar   | `shell.jsx` `Sidebar` + `NavItem` | 240/64px · brand row · nav tree with cyan-bar active state · footer user row     |
| Topbar    | `shell.jsx` `Topbar`              | 52px · workspace chip · breadcrumbs · ⌘K palette button · bell · docs · env pill |
| Statusbar | `shell.jsx` `Statusbar`           | 26px · two groups separated by 1×12 dividers · pulsing daemon dot · live cpu/mem |

### Overlays

| Component          | File                            | Anatomy                                                                        |
| ------------------ | ------------------------------- | ------------------------------------------------------------------------------ |
| Command palette    | `shell.jsx` `CommandPalette`    | 640px · 12px radius · dark · search row · 56px-wide kind tag · ↵ ↑↓ esc footer |
| Workspace switcher | `shell.jsx` `WorkspaceSwitcher` | 700px · "Open folder…" / "New…" / "Clone from git…" · recent list              |
| Modal / dialog     | `modal.jsx`, `dialogs.jsx`      | 12px radius · backdrop `rgba(2,5,9,0.55)` + 6px blur                           |
| Toast              | `crud.css`                      | 7px radius · 22px circular icon mark · 220ms slide-in                          |

### Surfaces & primitives

| Selector                                                                    | Use                                                                   |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `.panel`, `.panel-head`, `.panel-title`, `.panel-body`                      | Default content card                                                  |
| `.stat`, `.stat .label`, `.stat .value`, `.stat .meta`                      | Stat tile (2px colored left bar, mono uppercase label, 28/700 number) |
| `.drawer`, `.drawer-head`, `.drawer-body`, `.drawer-body .kv`               | Right-side detail drawer                                              |
| `.table-wrap`, `table.t`, `.mono`, `.row-link`, `.row-actions`              | Table — mono ID column, cyan row links, 5%-cyan selected row          |
| `.chip` + `.cyan` `.amber` `.violet` `.emerald` `.rose` `.gray`             | Inline pill — mono 11px, 3px radius                                   |
| `.tabs`, `.tab`, `.tab.active`, `.tab .count`                               | 13px medium · 2px black underline on active · mono count              |
| `.btn`, `.btn-primary`, `.btn-accent`, `.btn-ghost`, `.btn-icon`, `.btn-sm` | 34px default · 28px small · 6px radius                                |
| `.input`, `.search-input`, `<select>`, `<textarea>`                         | 5px radius · `#F7F9FB` resting · `#fff + cyan ring` focused           |
| `.kbd`, `.kbd-mini`                                                         | Keyboard hint chip                                                    |

### Domain & graph

| Selector                                | Use                                                     |
| --------------------------------------- | ------------------------------------------------------- | ------- | ------- | ------- |
| `.kg-row`, `.kg-node` (`hierarchy.jsx`) | Hierarchy viewer — domain swatch via `data-domain` attr |
| `.flow-node` (`pipeline-card.jsx`)      | Pipeline step — `data-kind="source                      | extract | resolve | write"` |
| `.flow-arrow`                           | 24×1px line with right-angle arrowhead                  |

### Iconography

Inline SVG defined in `components/icons.jsx`, drawn Lucide-style: 24×24 viewBox, 1.75 stroke, `currentColor`, `stroke-linecap: round`, `stroke-linejoin: round`. **In production, swap for the codebase's icon library (Lucide React is the closest match — every icon name in `ICONS` maps 1:1).** Sizing convention: 14px (button-inline), 16px (nav, palette), 18px (large icon button).

### Buttons — anatomy

```
Primary    bg #0B1220   fg #fff      use sparingly — 1 per surface
Accent     bg #0E7EA3   fg #fff      "Run pipeline", confirm in dialog
Ghost      transparent  fg #475569   border #E5E9EE   default action
Danger     bg #F43F5E   fg #fff      destructive only
```

Heights: 34 default, 28 sm, 24 xs. Padding: 0 12 (default), 0 10 (sm), 0 8 (xs). Icon-only: square the height. Icons are 14px and color-inherit.

---

## 7. How to use the design system

This is the operator manual for the design system. Follow these rules and any new screen will look correct without further direction.

### Adding a new screen

1. **Place it on the canvas, not the shell.** Every screen lives inside the canvas region — the shell (titlebar/sidebar/topbar/statusbar) is global and the screen never overlaps it.
2. **Page head pattern** — every screen's first canvas-row is a page head with: workspace pill + last-sync (mono, eyebrow), then H1 (24/700/-0.015em), then a 13px subtitle in `--canvas-fg-2`. Right-aligned action area: ghost secondary + primary action.
3. **Use `.panel` as the default content container.** Stack panels with 16–24px gap. A panel has a `.panel-head` (title + actions) and a `.panel-body`. Don't invent new card chrome.
4. **Two-column layouts**: 1.4fr / 1fr is the default split (main content / drawer). Use 8/12 + 4/12 for a sticky drawer pattern.
5. **Tables go inside `.table-wrap`.** First column is the mono ID. Cyan `.row-link` for the human-readable name. Status as a `.chip`. Last column is right-aligned mono timestamp.

### Choosing a color

- **Anything actionable** (focused field, primary button on dark, active nav, env pill, "click me" affordance) → cyan accent.
- **Anything stateful** (status, run result, intent) → semantic intent palette (success / warning / failure / info).
- **Anything domain-coded** (hierarchy node, schema row tag) → domain palette (life / climate / software / default).
- **Anything decorative** → don't. Use neutral fg/bd tokens.

If you find yourself reaching for a sixth color, you probably want a sixth chip variant — not a new color. Add it to the studio-accent palette, not as a one-off hex.

### Choosing a font/weight/size

- Default UI text → **`--text-sm` (14/400) Inter.** Most copy.
- Identifier, path, count, kbd, eyebrow, table header → **mono.** No exceptions.
- Page title → 24/700 Inter, -0.015em.
- Section header inside a panel → 13px / 600 Inter (panel-title).
- Stat number → 28/700 Inter, tabular numerals (`font-feature-settings: "tnum"`).

### Composing a new component

Before writing CSS, scan `studio.css` for a similar pattern. The four most-reused archetypes:

1. **Chip** — `.chip` + variant. Inline tag for status, env, or category. Mono 11/500, 3px radius, tinted bg + matching border.
2. **Pill** — `.env`-style. Larger than a chip, cyan-tinted, used once per chrome region.
3. **Node** — `.kg-node`-style. A bordered rectangle with a 3–4px colored left swatch. Used for hierarchy and any "typed" record.
4. **Tile** — `.stat`-style. Bordered card with a 2px colored left strip and a large number. Used for KPIs.

Most "new" components are one of these four with content swapped.

### Dark canvas

Wrap the canvas region in `body.dark-canvas`. The token overrides cascade — every component re-tints automatically. Test every new component in both modes. Watch for: chips (must use the dark chip variants), primary buttons (flip to cyan-on-dark), shadows (often invisible in dark — borders carry the weight).

### When to ask vs. extend

- **Ask** before adding: a new accent color, a new radius value, a new font, a new shadow, a sixth domain.
- **Extend without asking**: a new screen, a new panel arrangement, a new chip variant from the existing palette, a new icon (Lucide-style outline).

### Mistakes to avoid

- Putting the action accent on >1 element per surface
- Using a shadow where a 1px border would do
- Inventing a hex value not in `tokens.css`
- Sentence-casing "ID" column values (`Cls Organism`) — IDs are mono and verbatim
- Adding emoji
- Using gradients on app surfaces (only the brand mark uses one)
- Collapsing shell + canvas into one theme

---

## 8. Screens

Screen-specific notes. Anatomy lives in the corresponding `components/page-*.jsx`.

### Dashboard (`page-dashboard.jsx`)

1. Page head — workspace pill, last-sync, mono path; H1 "Dashboard"; subtitle "Curate knowledge graphs for retrieval-augmented generation and agents."; right-side: Refresh ghost + "+ New pipeline run" primary.
2. **Stat grid** — 4 columns × 14px gap: Taxonomies, Classes, Individuals, Pipelines. See `preview/components-stats.html`.
3. **Two-column** (1.4fr / 1fr):
   - **Knowledge Graph Structure** panel — `.kg-row` per node, `data-domain` drives the swatch color, indentation reflects hierarchy depth.
   - **Recent activity** panel — status dot (CREATE green, UPDATE amber, RUN cyan, DELETE rose) + tag + description + meta line + relative timestamp.
4. **Active pipelines** — header + 2-column grid of `pipeline-card`s.
5. **Quick access** — three `qa` tiles linking to common workflows.

### Schema (`page-schema.jsx`)

Tabs: Taxonomies / Classes / Properties / Relationships, each with a mono count.

- Page head with title + ID tag + actions
- Filter row: search input + filter chips
- 8/12 main + 4/12 sticky drawer
- Table: id (mono), name, description, domain chip, count, updated, row actions
- Drawer: `.kv` grid (mono uppercase keys → values), inline-editable fields, related lists

### Data → Individuals (`page-individuals.jsx`)

Same surface pattern as Schema. Individuals are instances; the table foregrounds the class chip and a sparkline of recent updates.

### Pipelines (`page-rest.jsx`, `pipeline-card.jsx`)

Cards in a 2-column grid. Each card:

- **Head** — name (truncates) + description, status chip, source-data tags, kebab, "Run" button.
- **Flow strip** (gradient inside the card) — sequence of `.flow-node`s connected by 24px arrow lines. Four kinds: `source` (cyan), `extract` (violet), `resolve` (amber), `write` (emerald).
- **Foot** — 5-stat row (last run, ingested, created, updated, errors).

### External Reference / Configuration (`page-rest.jsx`, `page-settings.jsx`)

Schema-style table+drawer for External Reference. Configuration uses a 2-column `.config-tile` grid with prominent icons.

### Graph view (`graph-view.jsx`, `graph.css`)

Interactive node-link diagram. Domain-colored nodes, neutral edges, accent-cyan selection. See `graph.css` for the canvas styling.

### Overlays

- **Command palette** — see `preview/components-palette.html`. ⌘K toggles. ESC closes. Pre-highlight first result.
- **Workspace switcher** — see `preview/brand-mark.html` for color treatment of the brand row.

---

## 9. Interactions & keyboard

| Action               | Behavior                                                                     |
| -------------------- | ---------------------------------------------------------------------------- |
| ⌘K / Ctrl+K          | Toggle command palette                                                       |
| Esc                  | Close palette / dialog / drawer                                              |
| Click workspace chip | Open workspace switcher                                                      |
| Click sidebar parent | Navigate to first child + auto-expand                                        |
| Click collapse arrow | Toggle sidebar 240 ↔ 64px                                                    |
| Hover row in palette | Highlight + show → arrow                                                     |
| Click pipeline "Run" | Trigger run + reflect in statusbar "1 pipeline running"                      |
| Toggle dark canvas   | Add/remove `body.dark-canvas`                                                |
| Tab / Shift-Tab      | Walk focusable elements in DOM order                                         |
| Focus                | Cyan ring `box-shadow: 0 0 0 3px rgba(34,211,238,0.13)` on the input/control |

Routing in the prototype uses `#r=<route>` URL fragments. The real app should use whatever the host framework provides (React Router, Tauri's router, etc.). Route IDs are documented in `components/shell.jsx` `NAV_TREE` and `ROUTE_LABELS`.

---

## 10. What NOT to port from the prototype

- **`tweaks-panel.jsx`** + the Tweaks UI in `app.jsx` — prototyping affordance only. The production app should ship cyan accent, neutral-dark shell, light canvas as fixed defaults. Dark-canvas may remain a user preference.
- **Hardcoded data in `data.js`** — replace with real workspace state from the daemon / local files.
- **`#r=<route>` URL routing** — replace with the host framework's router.
- **Any `landing` body class and related styles in `studio.css`** — leftover dead CSS from an earlier iteration.
- **Inline-SVG icons in `components/icons.jsx`** — swap to Lucide (or your library). Names map 1:1.

---

## 11. Open questions

1. **Window chrome on Windows/Linux** — draw our own titlebar (matching macOS) or use the platform's native chrome? Prototype draws macOS traffic lights.
2. **Mono font** — confirm and license JetBrains Mono / Geist Mono / IBM Plex Mono.
3. **Daemon protocol** — what does the graph daemon expose for the statusbar? CPU/mem are easy; "synced N min ago" needs a real signal.
4. **Workspace concept** — confirm "workspace = local folder containing schema + data + pipelines" is the right model and the file layout the picker should expect.
5. **Dark-canvas as a user preference?** — keep or fix to light only. Recommend keep.

---

## Reference cards

23 visual reference cards in `preview/`. Open any in a browser:

**Type** — `type-pairing.html` · `type-scale.html` · `type-mono-roles.html`
**Colors** — `colors-shell.html` · `colors-canvas.html` · `colors-accents.html` · `colors-domains.html` · `colors-intents.html`
**Spacing** — `spacing-scale.html` · `radius-scale.html` · `elevation.html`
**Components** — `components-buttons.html` · `components-chips.html` · `components-inputs.html` · `components-stats.html` · `components-hierarchy.html` · `components-pipeline.html` · `components-nav.html` · `components-table.html` · `components-palette.html` · `components-toasts.html`
**Brand** — `brand-mark.html` · `iconography.html`

Also surfaced in the project's Design System tab.
