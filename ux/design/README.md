# Context Studio — UX revamp handoff

Self-contained bundle of the redesigned Context Studio prototype, built
against the real `@tinkermonkey/heimdall-ui` React components.

## TL;DR for the dev team

1. **Open `Context Studio.html` in a browser.** No build step — it boots
   an in-browser Babel pipeline and loads the Heimdall library as plain
   `*.jsx`. Click through dashboard, schema, classes, pipelines; try ⌘K.
2. **Read `HEIMDALL_REBUILD.md`** for how the prototype maps to your
   `@tinkermonkey/heimdall-ui` imports and which components are used.
3. **Read `HEIMDALL_DESIGN_SYSTEM_FEEDBACK.md`** for the eight library
   gaps surfaced during the rebuild — each with concrete API + CSS
   suggestions for the Heimdall design system team.
4. **The JSX in `cs/pages.jsx` + `cs/app.jsx` is the spec.** Every tag
   maps 1:1 to a component your app will import. Add one import line
   at the top of each file and the code compiles in your build.

## Contents

```
handoff/
├── README.md                              ← you are here
├── HEIMDALL_REBUILD.md                    ← consumer-side handoff doc (8 findings,
│                                            including 4 from the polish pass)
├── HEIMDALL_DESIGN_SYSTEM_FEEDBACK.md     ← library-team feedback doc (full API
│                                            + CSS recommendations, 5 cross-cutting
│                                            principles for future components)
│
├── Context Studio.html                    ← v2 prototype (real components)
├── cs/
│   ├── app.jsx                            ← <CSApp> — composes ShellLayout, palette,
│   │                                        modal, toast, routing
│   ├── pages.jsx                          ← page components (Dashboard, Schema/*,
│   │                                        Individuals, Pipelines, Stub)
│   └── app.css                            ← CS-namespaced compositions + 4 marked
│                                            CSS overrides "OVERRIDE — pending library fix"
├── data.js                                ← sample workspace data (CS_DATA)
│
├── heimdall/                              ← staged copy of @tinkermonkey/heimdall-ui
│   ├── tokens.css                         ← canonical design tokens
│   ├── fonts.css + fonts/                 ← self-hosted Inter + JetBrains Mono
│   ├── utils/, hooks/                     ← support
│   └── components/                        ← 77 components
│       ├── *.tsx                          ← TypeScript source (READ for source of truth)
│       ├── *.css                          ← per-component styles
│       └── *.jsx                          ← Babel-friendly transforms used at runtime
│                                            — NOT for production
│
├── Context Studio (v1 HTML primitives).html  ← earlier HTML/CSS recreation
└── v1/                                       ← v1 supporting files (app.jsx, components,
                                                 styles, assets). v2 does NOT use these.
```

## What's NOT for production

- `heimdall/components/*.jsx` files exist only so the prototype can render
  the TypeScript source in a browser without a build step. The transform
  strips ES imports and binds runtime values to `window`. Ship the npm
  package (`@tinkermonkey/heimdall-ui`) instead.
- `Context Studio.html`'s `<script src=…@babel/standalone…>` block is
  prototype-only. Production uses Vite + tsx.
- The four CSS overrides in `cs/app.css` (marked `OVERRIDE — pending
library fix`) are explicit prototype-only patches. Once the
  corresponding Heimdall changes land, delete them — see the feedback
  doc for which selectors go away.

## What to read first, by role

- **Designer reviewing the prototype** → open `Context Studio.html`,
  click around. Compare the dashboard with `Context Studio (v1 HTML primitives).html`.
- **Dev porting the UX into the codebase** → `HEIMDALL_REBUILD.md`,
  then `cs/pages.jsx` + `cs/app.jsx`.
- **Design system maintainer (Heimdall)** → `HEIMDALL_DESIGN_SYSTEM_FEEDBACK.md`,
  prioritized by severity (PipelineCard first).

## Open issues to clear before shipping

See `HEIMDALL_DESIGN_SYSTEM_FEEDBACK.md` — findings #1, #2, #5 most
likely to block a clean implementation:

- **#1 PipelineCard** — flow strip can't express per-stage tone or
  even node distribution; CSS overrides are in place but should be
  removed once the library supports `FlowNode.tone` and `flowLayout`.
- **#2 PageHeader actions** — action buttons baseline-align with the
  title, not the bottom of the text block; no workaround applied.
- **#5 Sidebar expansion** — can't auto-expand the section containing
  the active route.
