---
name: context-studio-design
description: Use this skill to generate well-branded interfaces and assets for Context Studio, either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI components for prototyping.
user-invocable: true
---

Read the README.md file within this skill, and explore the other available files.
If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.

Key files:
- `README.md` — full design system reference (content voice, visual foundations, iconography)
- `styles/tokens.css` — foundation tokens (color, type, spacing, radius, shadow). Import first.
- `styles/studio.css` — shell, canvas, components, dark canvas mode. Import second.
- `styles/crud.css` — modals, forms, toasts.
- `components/icons.jsx` — Lucide-style outline icon set.
- `preview/*.html` — visual reference cards.

Core rules:
- Two-surface architecture: dark "shell" (`#0B0F14`) wraps a white or slate "canvas" — never blur the boundary.
- Cyan (`#22D3EE` / `#0E7EA3`) is the only accent that signals action and state. Use it sparingly.
- Mono (JetBrains Mono) for any identifier, ID, path, eyebrow label, table header, kbd, stat number.
- Small radii (4–8px). Borders over shadows. No gradients on app surfaces.
- No emoji. Outline icons only, 1.75 stroke, currentColor.
- Voice: terse, technical, sentence case. State the consequence; never apologize.

If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.
