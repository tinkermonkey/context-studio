# Context Studio v2 — Heimdall React Rebuild

This is the Context Studio prototype **rebuilt against the real `@tinkermonkey/heimdall-ui` React components** pulled from `tinkermonkey/heimdall@main`. Every visible element in the prototype maps 1:1 to a component the dev team will import.

The original HTML/CSS recreation lives at `Context Studio (v1 HTML primitives).html` for comparison.

## What's loaded

The Heimdall library is staged under `heimdall/`:

```
heimdall/
  tokens.css            — design tokens (CSS custom props)
  fonts.css             — @font-face declarations
  fonts/
    inter/*.woff2       — self-hosted Inter
    jetbrains-mono/*.woff2
  utils/
    graph.{ts,jsx}      — bezier path helpers (for GraphCanvas/Edge)
    graphLayout.{ts,jsx}— force-directed layout
  hooks/
    useFocusTrap.{ts,jsx}
    useBodyOverflow.{ts,jsx}
  components/
    *.tsx               — original TypeScript source from the repo
    *.css               — original per-component styles
    *.jsx               — transformed for in-browser Babel
                          (imports stripped, exports bound to window;
                          functionally equivalent to the npm build)
```

77 components loaded at runtime, in topo-sorted order. The transform pipeline that converts `*.tsx` → loadable `*.jsx` lives in `cs/build-notes.md` for reference.

## What I built

| File | Role |
|---|---|
| `Context Studio.html` | New entry — boots the Heimdall library, then loads `cs/pages.jsx` + `cs/app.jsx` |
| `cs/app.jsx` | `<CSApp>` — composes `<ShellLayout>` (Titlebar + AppTitle + Sidebar + Topbar + Statusbar), wires `<CommandPalette>`, `<Modal>` for new-class, `<Toast>` for confirmations, hash-based routing |
| `cs/pages.jsx` | `<CSDashboard>`, `<CSSchemaClasses>` (with `<InspectorPanel>`), `<CSSchemaTaxonomies>`, `<CSSchemaSchemes>`, `<CSSchemaProperties>`, `<CSSchemaRelationships>`, `<CSIndividuals>`, `<CSPipelines>`, `<CSStub>` |
| `cs/app.css` | Tiny set of project-local selectors (`.cs-domain-dot`, `.cs-between`) — everything else comes from Heimdall CSS |
| `Context Studio (v1 HTML primitives).html` | Original prototype, preserved for comparison |

## Component coverage

Real Heimdall components used in the rebuild — these are the JSX imports the dev team can copy-paste:

```jsx
import {
  // Shell
  ShellLayout, Titlebar, AppTitle, Sidebar, Topbar, Statusbar,
  // Page primitives
  PageHeader, Panel, TabBar,
  // Data display
  StatGrid, StatTile, Table, KVGrid, VersionPill, Chip, Badge, Button, Icon,
  HierarchyTree, HierarchyRow, ActivityTimeline, PipelineCard,
  QuickAccessGrid, InspectorPanel,
  // Forms
  Field, TextInput, TextArea, Select, SegmentedControl,
  // Overlays
  Modal, CommandPalette, Toast,
} from '@tinkermonkey/heimdall-ui'
```

## Findings — things the dev team should know

A few things surfaced from porting the *real* components that wouldn't have shown up in the HTML mock:

1. **`Sidebar` expansion is internal state.** When the route is `schema/classes`, the Schema parent should ideally auto-expand to show the active child. The current `<Sidebar>` API doesn't accept a controlled `expandedItems` prop — expansion is managed inside `useState` in the component. *Suggested fix in the library:* add `defaultExpandedIds` and `expandedIds`/`onExpandedChange` for controlled expansion.

2. **`Sidebar` collapse-toggle placement is internal.** The built-in `.sidebar__toggle` button renders at the top of the nav list — there's no prop to hide it, and `<AppTitle>` has no action slot to put one in instead. *Suggested fix in the library:* `<Sidebar>` accepts `showCollapseToggle={false}`, and `<AppTitle>` accepts an `action` (or `right`) slot so the toggle can live in the brand row.

3. **`Pipeline.flow[].icon` is `IconName` keyed.** The icon names in our CS_DATA (`reference`, `sparkle`, `doc`, `database`) aren't in the Heimdall `ICONS` map. The rebuild remaps them to `link`/`zap`/`file`/`hardDrive` in `cs/pages.jsx`. *Suggested fix:* either add these names to `ICONS`, or extend the type to accept arbitrary `IconName | React.ReactElement` consistently and document a folder/tag icon.

4. **No `folder`/`tag` icons.** The original Titlebar workspace pill and Properties tile used `folder` and `tag` glyphs that aren't in the icon set. The rebuild substitutes `hardDrive` and `component`. Probably worth adding `folder` and `tag` to the canonical set.

5. **`PageHeader.actions` can take multiple `<Button>`s as a fragment — works correctly. ✓**

6. **`Modal` is fully controlled (`isOpen` + `onClose`). `useFocusTrap` + `useBodyOverflow` are wired internally. ✓**

7. **`Toast` is controlled (`isOpen`, `onClose`, `duration`). It positions itself inside its parent — to pin it to the bottom-right, wrap in a `position: fixed` container (done in `cs/app.jsx`). *Suggested fix:* an optional `<ToastStack position="bottom-right">` wrapper that does this automatically.**

8. **`CommandPalette` commands are flat. The original prototype grouped them by RECENT/CLASS/GO/ACTION. *Suggested fix:* add an optional `group` field to `Command` so the UI can show section headers.**

## Why this is the handoff

Because every JSX element in `cs/pages.jsx` and `cs/app.jsx` is a real `@tinkermonkey/heimdall-ui` component:

- The dev team reads the prototype source, adds an import line at the top, and the code compiles in their Vite/Next/CRA build.
- Pixel diffs against the prototype are diffs against the canonical components — anything off is a library or token issue, not "the designer drew something custom."
- New design exploration in this project will inherit the same constraint by default; future designs use the same primitives or surface a request to extend them.

## Build pipeline (for the curious)

In-browser Babel-standalone loads the `.tsx` source through this transform per file:

1. Strip `import` lines (single + multi-line)
2. Strip `export` keywords (`export const X` → `const X`)
3. Strip `export { ... }` / `export type { ... }` / `export default X` re-exports
4. Append `window.X = X` for each runtime value (type-only exports skipped)

Then `Babel.transform(..., { presets: [['typescript', { isTSX: true }], 'react'] })` produces vanilla JS, which is `eval`'d in global scope. This is *not* what production runs — production uses the npm package's `prepare`/`vite build` output. The transform is purely so the prototype can render the same source the dev team will ship.
