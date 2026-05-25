---
name: context-studio-design-audit
description: Run a visual design audit comparing the Context Studio implementation against the Heimdall prototype. Captures screenshot pairs, classifies gaps as A/B/C, and updates the gap inventory. Use when implementing a new page, after a refactor, or to validate Heimdall adoption progress.
user-invocable: true
---

You are running a visual design audit for Context Studio. The goal is to compare the running implementation against the Heimdall design prototype and produce a structured gap report. Work through every section in order.

---

## 0. What you are comparing

**Prototype** (visual contract): `ux/design/Context Studio.html`  
**Build guide** (production recipe): `ux/design/CONTEXT_STUDIO_BUILD_GUIDE.md`  
**Gap inventory** (living document): `documentation/ux-audit/heimdall-gap-inventory.md`  
**Screenshots output**: `/screenshots/audit/` (gitignored)

The three gap categories used throughout:
- **A — Replace**: Custom component/CSS when Heimdall has an out-of-box equivalent
- **B — Override**: Heimdall component present but buried under wrong data or custom CSS fighting its defaults
- **C — Underuse**: Heimdall component used but missing props/slots the design requires

---

## 1. Start the servers

```bash
# Check if Vite dev server is running
lsof -i :3100 || (cd ux && npm run dev &> /tmp/vite-dev.log & sleep 5)

# Check if backend is running
lsof -i :8000 || (cd local-server && source .venv/bin/activate && python app.py &> /tmp/backend.log & sleep 5)

# Serve the design prototype
lsof -i :3200 || (cd ux/design && python3 -m http.server 3200 &> /tmp/design-server.log & sleep 2)
```

Verify:
- App: `http://localhost:3101/app` (select the `local.db` recent workspace if the picker appears)
- Prototype: `http://localhost:3200/Context%20Studio.html`

---

## 2. Determine scope

The user will tell you which pages to audit. If not specified, audit in this order:
1. App Shell (sidebar, topbar, statusbar — visible on every page)
2. Dashboard (`/app`)
3. Schema — Classes (`/app/schema/classes`)
4. Pipelines (`/app/pipelines`)
5. Settings (`/app/settings`)
6. Schema — Taxonomies, Schemes, Properties, Relationships
7. Individuals, Datasets
8. Graph view

---

## 3. Capture screenshot pairs

For each page being audited:

**Prototype:** Navigate to the corresponding route using the hash fragment:
- Dashboard → `#r=dashboard`
- Schema-classes → `#r=schema-classes`
- Pipelines → `#r=pipelines`
- Settings → `#r=settings`
- Graph → `#r=graph`

Use Playwright MCP to take full-page screenshots. Save as:
```
/screenshots/audit/[page]-prototype.png
/screenshots/audit/[page]-impl.png
```

Set viewport to 1440×900 for consistency.

---

## 4. Analyze each screenshot pair

View both screenshots and compare systematically. For each visual difference you find:

1. Identify the Heimdall component that should be rendering that area
2. Classify the gap: **A** (should use a Heimdall component but isn't), **B** (Heimdall component is there but CSS or props are wrong), or **C** (Heimdall component is there but missing props/slots)
3. Note the specific prop, CSS class, or component that needs to change

**Shell checklist (check on every page):**
- [ ] Sidebar: no section header labels visible between nav groups
- [ ] Sidebar: user profile chip at bottom
- [ ] Canvas mode: dark canvas active by default
- [ ] Topbar: search bar spans most of the topbar width
- [ ] Topbar: workspace chip shows actual workspace name (not generic "local")
- [ ] Statusbar: shows entity counts, running pipelines, branch, CPU/mem

**Per-page checklist — Dashboard:**
- [ ] `StatTile` — sparkline visible in each tile
- [ ] `ActivityTimeline` — entity icons, action verbs, user attribution, "View all" link
- [ ] `HierarchyTree` — taxonomy → scheme → class hierarchy with collapse/expand
- [ ] Active Pipelines section with `PipelineCard` grid
- [ ] `QuickAccessGrid` at bottom (6 tiles)

**Per-page checklist — Schema pages:**
- [ ] `TabBar` with counts across all 5 schema routes
- [ ] Eyebrow chip present
- [ ] Route path badge on title
- [ ] `FilterBar` with filter chips
- [ ] `SegmentedControl` for view toggle
- [ ] `InspectorPanel` opens inline (not as a Drawer overlay) when row selected

**Per-page checklist — Pipelines:**
- [ ] Tabs are status-based: All / Running / Success / Idle / Failed
- [ ] `FilterBar` present
- [ ] `PipelineCard` shows metrics row (LAST RUN, INGESTED, CREATED, UPDATED, ERRORS)
- [ ] Pipeline description text under name

**Per-page checklist — Settings:**
- [ ] Form fields directly visible on General tab (not a nav-tile grid)
- [ ] `ConfigTile` cards appear as right-sidebar column
- [ ] Route path badge on title
- [ ] Tab counts visible
- [ ] Eyebrow uses lowercase dot-prefixed format ("● settings")
- [ ] `ModalFootHint` shows HTTP verb + path at form bottom

---

## 5. Update the gap inventory

After completing the audit, update `documentation/ux-audit/heimdall-gap-inventory.md`:
- Add new gaps found with the A/B/C category and component name
- Mark resolved gaps with ✅ and the date fixed
- Update the Priority Order table if priorities have shifted

---

## 6. Report

Output a summary in this format:

```
## Design Audit Report — [pages audited] — [date]

### Pages audited
- [list]

### Screenshot pairs saved
- /screenshots/audit/[page]-prototype.png vs [page]-impl.png

### Gaps found
| ID | Cat | Component | Issue |
|----|-----|-----------|-------|
| ... |

### Gaps resolved since last audit
| ID | Component | Fix applied |
|----|-----------|-------------|
| ... |

### CSS line count
studio.css: X lines (delta: ±Y from last audit)

### Next priority fix
[one sentence on what to work on next]
```

---

## 7. Reference

The gap inventory is the living record: `documentation/ux-audit/heimdall-gap-inventory.md`  
The BUILD_GUIDE is the authoritative spec: `ux/design/CONTEXT_STUDIO_BUILD_GUIDE.md`  
For building fixes, use the `/heimdall-ux` skill.
