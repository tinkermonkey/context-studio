# Context Studio — Design System

A graph-native knowledge studio. Dark IDE-style chrome wraps a light "canvas" work surface where users build hierarchies, run pipelines, and inspect data. The system reads as a developer tool: dense, mono-accented, heavy on tabular layouts and inline metadata.

## Sources

- `Context Studio.html` — entry point, loads the full app.
- `styles/tokens.css` — Flowbite/Tailwind-derived foundations (color scales, spacing, radii, shadows, type).
- `styles/studio.css` — Studio-specific overlay: shell chrome, canvas, hierarchy tree, pipelines, command palette, dark canvas mode.
- `styles/crud.css` — modals, forms, tri-states, entity pickers, toasts, row menus.
- `styles/individuals.css`, `styles/settings.css`, `styles/graph.css` — page-specific styling.
- `components/*.jsx` — React component implementations (Lucide-style outline icons in `icons.jsx`).

## Index

| File                   | Purpose                                                           |
| ---------------------- | ----------------------------------------------------------------- |
| `README.md`            | This document                                                     |
| `SKILL.md`             | Skill manifest (cross-compatible with Claude Code skills)         |
| `styles/tokens.css`    | Foundation tokens — colors, type, spacing, radius, shadow         |
| `styles/studio.css`    | Shell, canvas, components                                         |
| `styles/crud.css`      | Modals, forms, toasts                                             |
| `components/icons.jsx` | Icon set (Lucide-style outline, 1.75 stroke)                      |
| `preview/`             | Design-system preview cards (registered in the Design System tab) |

---

## Content Fundamentals

**Voice.** Calm, technical, terse. Reads like a CLI man page, not marketing copy. Short labels, no exclamation, no hand-holding. The product trusts the user to know what a "schema", "individual", or "pipeline" is.

**Casing.**

- Sentence case for headings ("Knowledge graph", not "Knowledge Graph"), with a few proper-noun exceptions (REST, JSON, ID).
- UPPER + monospace for section labels (`SCHEMA`, `LAST RUN`, `WORKSPACE`) — used as eyebrows above values.
- Identifiers always in monospace, lowercase, snake_case (`life.organism`, `cls_4f3a`, `pipeline.run.completed`).

**Pronouns.** Mostly impersonal — "Add a class", "Run pipeline", "No data yet". Occasionally "you" in empty states ("You haven't created any schemas"). Never "we", "us", or "our".

**Numbers and counters.** Tabular numerals, monospace, right-aligned in tables. Counters like `12 / 480` or `+3 today`.

**Tone examples.**

- Empty state: _"No individuals match these filters."_ (not _"Looks like there's nothing here yet — try adjusting your filters!"_)
- Error toast: _"`pipeline.run` failed — connection refused at step 2"_ (mono code, no apology)
- Success toast: _"Saved"_ / _"Class created"_ — one or two words.
- Confirmation: _"Delete `cls_organism`? 47 individuals will be unlinked."_ (states the consequence, doesn't ask "Are you sure?")

**Emoji.** Never. The visual language is line-icon and monospace.

---

## Visual Foundations

### Two surfaces

The defining structural choice. The **shell** (sidebar, topbar, statusbar, titlebar) is a deep slate dark. The **canvas** (main work surface) is white in light mode, slate in dark mode. The canvas attaches to the shell with a single 8px top-left radius — a visual seam that says "this is the document, that is the IDE".

| Surface       | Light     | Dark      |
| ------------- | --------- | --------- |
| Shell bg      | `#0B0F14` | `#0B0F14` |
| Shell surface | `#131A23` | `#131A23` |
| Canvas bg     | `#FFFFFF` | `#14191F` |
| Canvas card   | `#FFFFFF` | `#1B222A` |
| Canvas border | `#E5E9EE` | `#2A323C` |

### Color

- **Primary accent: cyan.** `#22D3EE` (bright) → `#0E7EA3` (deep). Used for: active nav indicator (2px left bar), focus rings, primary CTAs in dark mode, status pulses, env pills, version badges, tab underlines.
- **Domain palette** (used to color taxonomies / classes in the hierarchy): emerald `#34D399` (life), amber `#FBBF24` (climate), indigo `#818CF8` (software), cyan `#22D3EE` (default).
- **Semantic intents:** emerald success, amber warning, rose error, violet info-secondary.
- **Neutrals:** Tailwind gray scale. Foreground is layered fg-1 → fg-4 (primary text → quaternary/icons-disabled).
- **Saturation discipline.** No bright pastels on dark canvas — chip backgrounds drop to ~10% alpha tints. No gradient backgrounds on cards. The ONE exception: the brand mark (cyan→deep-cyan) and the hero headline gradient (cyan→violet).

### Type

- **Sans:** Inter — UI, body, headings.
- **Mono:** JetBrains Mono — IDs, paths, keyboard shortcuts, eyebrow labels, table headers, code, tabular numerals.
- **Scale:** Tailwind's text-xs (12) through text-6xl (60). Body is 14px (`--text-sm`); page H1 is 24px (smaller than typical web — IDE density). Mono UI labels are 10–11px with `letter-spacing: 0.06–0.12em` and uppercase.
- **Weights:** 400 normal, 500 medium (most UI), 600 semibold (headings), 700 bold (page H1, stat numbers), 800 extrabold (landing hero only).
- **Headings letter-spacing:** -0.015 to -0.025em (tight).

### Shape

- **Radius:** small. 4–6px on most things (chips, buttons, inputs, nodes). 8px on cards and panels. 10–12px on modals only. No pill shapes except the env pill and round dots.
- **Borders:** 1px hairline at low contrast (`--canvas-bd`, `--shell-border`). Borders do most of the structural work — shadows are reserved.
- **Shadows:** very rare. Modal: `0 24px 64px -16px rgba(0,0,0,0.55)`. Toast: `0 14px 40px -16px rgba(0,0,0,0.5)`. Cards = no shadow, just border.

### Spacing

Tailwind 4px scale. UI density ranges:

- Compact (table rows, nav items): 8–10px vertical padding.
- Standard (panel headers, buttons): 12–14px.
- Generous (modal heads, page heads): 18–20px.

Page canvas padding is 28px × 32px. Stat-grid gap is 14px. Card internals 16px.

### Animation

Sparse and short. 80–180ms ease for hovers and modals. The only continuous animation is the green status pulse (1.6s ease-out infinite scale + fade) — used to signal "live" / "connected". No bouncy easing, no parallax, no scroll-driven motion.

### Hover & press states

- Nav items / table rows / chips: background lifts to `--shell-surface` or `--canvas-bg-2` — a single neutral step, never a tint.
- Buttons: darken by ~10–15% (light bg) or move toward the brighter cyan (dark bg).
- Active nav: 2px cyan bar on the left edge, surface bg.
- No transforms on press. No scale-down. No ripples.

### Iconography

**Lucide-style outline.** 24×24 viewBox, `stroke-width: 1.75`, `currentColor`, `stroke-linecap: round`, `stroke-linejoin: round`. Defined inline in `components/icons.jsx`. No filled icons except `play`, `pause`, `zap`, `dot`. Sizes: 13–16px in UI, 18–22px in tile heads.

Never use emoji. Never use unicode glyphs as icons. The single arrow rendered as a CSS pseudo-element (pipeline flow `→`) is the lone exception.

### Backgrounds & textures

- No images, no gradients, no noise, no patterns on app surfaces.
- Hero (landing only): two soft radial-gradient blooms (cyan top-left, violet bottom-right) at 12–18% alpha, behind a card.
- Brand mark: cyan-to-deep-cyan 135° linear gradient, with a stamped 3-dot pattern.

### Layout primitives

- **Two-pane** (`.split-2`): main content + 380px right drawer.
- **Three-pane** (`.split-3`): 220px left + flex middle + 320px right.
- **Stat grid:** 4 columns × variable rows of stat tiles, each with a 2px colored left bar.
- **Pipeline card:** flow strip with rounded nodes connected by 1px lines + 45°-rotated tip arrows.
- **Hierarchy tree:** mono node-pills with a 2.5–3px colored swatch on the left, dashed row dividers, indent steps of 18px.

### Borders, focus, selection

- Focus ring: `0 0 0 3px rgba(34, 211, 238, 0.13–0.15)` on inputs and buttons.
- Selection background (text): `rgba(34, 211, 238, 0.25)`.
- Row selection: `rgba(34, 211, 238, 0.05)` bg + tint border.
- Selected node: 1px cyan border + 1px cyan glow ring.

---

## Iconography (deeper)

Single source: `components/icons.jsx`. Adding an icon = adding a key + path string to the `ICONS` map. Names are short and lowercase: `dashboard`, `schema`, `pipeline`, `graph`, `settings`, `search`, `bell`, `plus`, `chevDown`, `chevRight`, `play`, `pause`, `bot`, `brain`, `zap`, `globe`, `shield`, `cpu`, `layers`, `doc`, `folder`, `database`, `tag`, `table`, `flask`, `refresh`, `more`, `edit`, `check`, `x`, `expand`, `workflow`, `branch`, `history`, `sparkle`, `dot`.

Always render via `<Icon name="…" size={16} />`. Never paste raw SVG into a component. If an icon is missing, add it to the map first.

---

## How to use this system

- **For production code:** import `styles/tokens.css` first, then `styles/studio.css` (or just the layers you need). Use the CSS classes documented in `studio.css` (`.btn`, `.btn-primary`, `.panel`, `.stat`, `.kg-node`, `.chip.cyan`, etc.) — they're already named for the system.
- **For mocks / decks / prototypes:** copy `styles/tokens.css` and the relevant pieces of `studio.css` + `crud.css` into your file. Use `Inter` + `JetBrains Mono` from Google Fonts (already imported in tokens.css). Stick to the two-surface rule.
- **For new components:** keep radii small (4–8px), avoid shadows, prefer borders, use mono for any identifier-shaped string, and pick a single domain or accent color rather than mixing multiple.

---

## Caveats

- Foundations were originally derived from Flowbite/Tailwind primitives — `tokens.css` keeps that lineage so the app can interop with off-the-shelf Flowbite components if needed. Studio's overlay tokens (`--shell-*`, `--canvas-*`, `--accent-*`) are the day-to-day surface.
- The icon set is hand-rolled in the Lucide style but is not the Lucide package. If you switch to Lucide-react, names match for ~90% of the set.
- Inter and JetBrains Mono are loaded from Google Fonts at runtime; for offline/print, swap to local font files.
