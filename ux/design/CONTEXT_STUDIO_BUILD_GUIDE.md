# Building Context Studio with `@tinkermonkey/heimdall-ui`

**For:** Engineers shipping the production Context Studio app
**From:** UX prototype (`Context Studio.html` in this project) + the updated Heimdall design system

This is the recipe for assembling Context Studio from the production component package. It assumes:

- `@tinkermonkey/heimdall-ui` has been updated per `HEIMDALL_HANDOFF.md` (Sparkline, PipelineCard, InspectorPanel, KVGrid, HierarchyTree, FilterDropdown, SegmentedControl, QuickAccessTile, ConfigTile, VersionPill, WorkspaceSwitcherDialog, plus the extensions to StatTile / FilterBar / ActivityTimeline / Statusbar).
- You're using React 18+, TypeScript, and a build that allows ESM imports.
- The package exports the tokens layer (`@tinkermonkey/heimdall-ui/tokens.css`) and the self-hosted Inter + JetBrains Mono fonts as side-effects.

The prototype in this project is the **visual contract** — when a question comes up, open `Context Studio.html` and look at the live screen. Pixel-level dimensions, copy, and densities all come from there.

---

## 0 · Pre-flight

### Voice & content rules

Everything in the UI follows the rules in the design system README. Quick recap so they're at hand:

- **Sentence case** for headings; **UPPER + monospace** for eyebrow labels (`SCHEMA`, `LAST RUN`).
- Identifiers are always **monospace, lowercase, snake_case** (`cls_gene`, `pipeline.run.completed`).
- Empty states and errors are terse and technical, no apology. _"No individuals match these filters."_ not _"Oops!"_
- **No emoji. No unicode glyphs as icons.** Add to the Lucide-style icon map instead.
- Numbers in tables / tiles are tabular, mono, right-aligned.

### Color discipline

The shell is **always dark slate navy**. The canvas is **light by default**; toggle dark with `body.dark-canvas`. The primary accent is **amber** — used sparingly, never as a fill on the canvas.

---

## 1 · Project skeleton

```bash
pnpm add @tinkermonkey/heimdall-ui react react-dom
```

`src/main.tsx`:

```tsx
import { createRoot } from 'react-dom/client';
import { HeimdallProvider } from '@tinkermonkey/heimdall-ui';
import '@tinkermonkey/heimdall-ui/tokens.css';   // CSS-var token layer + fonts
import '@tinkermonkey/heimdall-ui/styles.css';   // component styles

import { App } from './App';

createRoot(document.getElementById('root')!).render(
  <HeimdallProvider>
    <App />
  </HeimdallProvider>
);
```

`HeimdallProvider` mounts the toast portal and the command-palette portal — both are required for `useToast()` and `useCommandPalette()` to work.

### Dark canvas

Context Studio defaults to **dark canvas** (the studio is monitoring-adjacent). Add the class once on `<body>`:

```tsx
useEffect(() => {
  document.body.classList.add('dark-canvas');
  return () => document.body.classList.remove('dark-canvas');
}, []);
```

The same body class flips canvas tokens — every component on the canvas re-reads `--canvas-*` vars automatically.

---

## 2 · App shell

The shell is the same on every page. Wire it once.

```tsx
import {
  Desktop, AppShell, Sidebar, Topbar, Statusbar, CanvasArea,
  ToastStack, CommandPalette
} from '@tinkermonkey/heimdall-ui';

function App() {
  const [route, setRoute] = useRoute();             // your router; hash or react-router
  const [collapsed, setCollapsed] = useState(false);

  return (
    <Desktop>
      <AppShell>
        <Sidebar
          collapsed={collapsed}
          onToggleCollapsed={() => setCollapsed(v => !v)}
          brand={{ name: 'Context Studio', version: 'v0.2.0', mark: 'heimdall' }}
          nav={NAV_TREE}
          activeRoute={route}
          onNavigate={setRoute}
          user={{ name: 'Maya Chen', email: 'maya@studio', branch: 'main' }}
        />
        <Workspace>
          <Topbar
            workspace={workspace}
            onSwitchWorkspace={() => setWsOpen(true)}
            crumbs={CRUMBS[route]}
            paletteShortcut="⌘K"
            onOpenPalette={() => setPaletteOpen(true)}
            env="workspace · default"
            notificationCount={2}
          />
          <CanvasArea>
            <RoutedPage route={route} />
          </CanvasArea>
        </Workspace>
      </AppShell>
      <Statusbar groups={STATUSBAR_GROUPS} />
      <ToastStack />
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        sources={paletteSources}
      />
      <WorkspaceSwitcherDialog
        open={wsOpen}
        onClose={() => setWsOpen(false)}
        current={workspace}
        recent={recentWorkspaces}
        onOpenFolder={…}
        onNewWorkspace={…}
        onCloneFromGit={…}
        onPickRecent={openWorkspace}
      />
    </Desktop>
  );
}
```

**Key invariants:**

- `Sidebar` is **256px expanded / 64px collapsed**. Active nav items get the 2px amber bar on the left automatically.
- `Topbar` is **52px**; the palette field flexes to fill.
- `Statusbar` is **26px**; each group caps at **4 items**, overflow goes into a popover (handled by the component).
- `CanvasArea` paints the 8px `border-top-left-radius` notch — the system's signature seam. **Do not put anything else with a corner radius on the canvas root.**

### `NAV_TREE` shape

```ts
export const NAV_TREE: NavNode[] = [
  { id: 'dashboard', label: 'Dashboard', icon: 'dashboard' },
  { id: 'schema',    label: 'Schema',    icon: 'schema', children: [
      { id: 'schema/taxonomies',     label: 'Taxonomies' },
      { id: 'schema/schemes',        label: 'Concept schemes' },
      { id: 'schema/classes',        label: 'Classes' },
      { id: 'schema/properties',     label: 'Properties' },
      { id: 'schema/relationships',  label: 'Relationships' },
  ]},
  { id: 'data',      label: 'Data', icon: 'data', children: [
      { id: 'data/individuals', label: 'Individuals' },
      { id: 'data/sources',     label: 'Sources' },
  ]},
  { id: 'pipelines', label: 'Pipelines', icon: 'pipeline', children: [
      { id: 'pipelines/all', label: 'All pipelines' },
      { id: 'pipelines/runs', label: 'Run history' },
      { id: 'pipelines/flavors', label: 'Flavors' },
  ]},
  { id: 'reference', label: 'External Reference', icon: 'reference', children: [...] },
  { id: 'graph',     label: 'Graph view', icon: 'graph' },
  { id: 'settings',  label: 'Configuration', icon: 'settings' },
];
```

---

## 3 · Domain model

Same as the prototype's `data.js`. Type sketch:

```ts
type Domain = 'life' | 'climate' | 'software' | 'default';
type Status = 'running' | 'success' | 'idle' | 'failed';

interface Taxonomy      { id: string; title: string; domain: Domain; description: string; version: number; classes: number; individuals: number; }
interface ConceptScheme { id: string; taxonomy_id: string; title: string; domain: Domain; description: string; version: number; classes: number; }
interface Class         { id: string; concept_scheme_id: string; taxonomy_id: string; domain: Domain; parent_class_id: string | null; title: string; description: string; individuals: number; version: number; }
interface Individual    { id: string; class_id: string; multi_class_ids?: string[]; title: string; description: string; properties: Record<string, unknown>; }
interface Pipeline      { id: string; name: string; description: string; status: Status; target: string; flow: PipelineStep[]; recent: PipelineRunStats; tags: string[]; }
interface Relationship  { id: string; source_id: string; target_id: string; property_definition_id: string; source: string; }
```

All identifiers are mono. Wrap them in `<Mono>` (or `<KGNode>` for the colored swatch variant) — never inline `<span style={{fontFamily: 'monospace'}}>`.

---

## 4 · Page recipes

### 4.1 Dashboard

```tsx
import {
  PageHead, StatGrid, StatTile, Panel, Split,
  HierarchyTree, HierarchyRow, KGNode,
  ActivityTimeline, PipelineCard, QuickAccessTile,
  Chip, IdTag, Button, Icon
} from '@tinkermonkey/heimdall-ui';

export function DashboardPage({ data, onNav }: { data: Workspace; onNav: (r: string) => void }) {
  return (
    <>
      <PageHead
        eyebrow={[
          <Chip key="ws" tone="amber" dot>workspace · default</Chip>,
          <Mono key="sync" muted size={11}>last sync 2m ago</Mono>,
          <Mono key="sep" muted size={11}>·</Mono>,
          <Mono key="dae" muted size={11}>graph daemon healthy</Mono>,
        ]}
        title={<>Dashboard <IdTag>/workspace/{data.workspace.name}</IdTag></>}
        subtitle="Curate knowledge graphs for retrieval-augmented generation and agents. Taxonomies group concept schemes; concept schemes hold classes; classes hold individuals."
        actions={
          <>
            <Button icon="refresh">Refresh</Button>
            <Button variant="primary" icon="plus">New pipeline run</Button>
          </>
        }
      />

      <StatGrid>
        <StatTile label="Taxonomies"  icon="schema"   color="cyan"    value={3}
                  meta={<Muted>3 active · 0 archived</Muted>}
                  sparkData={data.sparks.taxonomies}  sparkColor="#22D3EE" />
        <StatTile label="Classes"     icon="schema"   color="violet"  value={20}
                  meta={<><Delta dir="up">▲ 4</Delta> <Muted>this week</Muted></>}
                  sparkData={data.sparks.classes}     sparkColor="#A78BFA" />
        <StatTile label="Individuals" icon="data"     color="emerald" value={267}
                  meta={<><Delta dir="up">▲ 38</Delta> <Muted>last run · 412 ingested</Muted></>}
                  sparkData={data.sparks.individuals} sparkColor="#10B981" />
        <StatTile label="Pipelines"   icon="pipeline" color="amber"   value="1/6"
                  meta={<><Pulse size="sm" tone="amber" /><Muted>1 running · 1 failed</Muted></>}
                  sparkData={data.sparks.ingestRate}  sparkColor="#FBBF24" />
      </StatGrid>

      <Split cols={[1.55, 1]} gap={14}>
        <Panel
          title={<><Icon name="schema" size={14} />Knowledge graph structure</>}
          actions={
            <Row gap={12}>
              <Mono muted size={11}>3 tax · 8 sch · 20 cls</Mono>
              <Button variant="ghost" size="sm" onClick={() => onNav('schema/classes')}>Open <Icon name="arrow" size={11} /></Button>
            </Row>
          }
          bodyFlush
        >
          <HierarchyTree>
            {flattenHierarchy(data).map(r => (
              <HierarchyRow
                key={r.id}
                depth={r.depth}
                domain={r.domain}
                kind={r.kind}                       // 'taxonomy' | 'scheme' | 'class'
                label={r.title}
                meta={`${r.count} ${r.unit}`}       // "3 cls" / "8 cls" / "5 ind"
                description={r.description}
                selected={r.id === selectedId}
                onSelect={() => setSelectedId(r.id)}
              />
            ))}
          </HierarchyTree>
        </Panel>

        <Panel
          title={<><Icon name="history" size={14} />Recent activity</>}
          actions={<Button variant="ghost" size="sm">View all</Button>}
          bodyFlush
        >
          <ActivityTimeline
            items={data.activity.slice(0, 7).map(a => ({
              kind:      a.kind,                            // 'create' | 'update' | 'run' | 'delete'
              dotColor:  ACTIVITY_DOT[a.kind],              // 'emerald' | 'cyan' | 'amber' | 'rose'
              kindLabel: a.kind.toUpperCase(),              // CREATE / UPDATE / RUN / DELETE
              headline:  <><b>{a.what}</b> — <Mono>{a.subject}</Mono></>,
              meta:      `${a.meta} · by ${a.who}`,
              when:      a.when,
            }))}
          />
        </Panel>
      </Split>

      <Panel
        title={<><Icon name="pipeline" size={14} />Active pipelines</>}
        actions={<Button variant="ghost" size="sm" onClick={() => onNav('pipelines/all')}>All pipelines <Icon name="arrow" size={11} /></Button>}
      >
        <Grid cols={2} gap={14}>
          {data.pipelines.slice(0, 2).map(p => (
            <PipelineCard key={p.id} pipeline={p} compact />
          ))}
        </Grid>
      </Panel>

      <SectionHead title="Quick access" hint="Jump to common workflows" />
      <Grid cols={3} gap={10}>
        {QUICK_ACCESS.map(q => (
          <QuickAccessTile
            key={q.route} icon={q.icon} title={q.title} description={q.desc}
            onClick={() => onNav(q.route)}
          />
        ))}
      </Grid>
    </>
  );
}
```

**Notes:**

- `StatTile` takes `sparkData` directly — it owns the Sparkline placement (bottom-right, 88×28). Don't try to position one manually inside `meta`.
- `HierarchyRow` renders the dashed connector and the indent automatically based on `depth`. Don't pad children yourself.
- `ActivityTimeline` handles the kind-tag + intent dot + mono meta layout — pass plain content, not styled spans.

### 4.2 Schema · Classes (table + inspector)

```tsx
import {
  PageHead, Tabs, FilterBar, SegmentedControl, Table,
  InspectorPanel, KVGrid, KGNode, VersionPill, Button, Icon
} from '@tinkermonkey/heimdall-ui';

export function ClassesPage({ data }: { data: Workspace }) {
  const [selectedId, setSelectedId] = useState<string | null>('cls_cell');
  const [query, setQuery] = useState('');
  const [domainFilter, setDomainFilter] = useState<Domain | 'all'>('all');

  const rows = useMemo(() => filterClasses(data.classes, { query, domainFilter }), [query, domainFilter]);
  const selected = data.classes.find(c => c.id === selectedId);

  return (
    <>
      <PageHead
        eyebrow={[
          <Chip key="s" tone="violet" dot>schema</Chip>,
          <Chip key="t" form="id-tag">node_type · class</Chip>,
          <Muted key="n" mono size={11}>20 classes · 8 schemes · 3 taxonomies</Muted>,
        ]}
        title={<>Classes <IdTag>/schema/classes</IdTag></>}
        subtitle="Classes are the structural nodes of the graph. Each belongs to a concept scheme, inherits from a parent class, and carries data-property definitions populated by pipelines or curators."
        actions={
          <>
            <Button icon="ext">Export</Button>
            <Button variant="primary" icon="plus" onClick={() => openNewClassModal()}>New class</Button>
          </>
        }
      />

      <Tabs
        items={[
          { id: 'taxonomies',  label: 'Taxonomies',     count: 3 },
          { id: 'schemes',     label: 'Concept schemes', count: 8 },
          { id: 'classes',     label: 'Classes',         count: 20, active: true },
          { id: 'properties',  label: 'Properties',      count: 8 },
          { id: 'relationships', label: 'Relationships', count: 9 },
        ]}
        activeId="classes"
        onChange={id => navigateTo(`schema/${id}`)}
      />

      <FilterBar searchPlaceholder="Search classes, descriptions, ids…" onSearchChange={setQuery}>
        <SegmentedControl
          value={domainFilter}
          onChange={setDomainFilter}
          options={[
            { value: 'all',     label: 'All' },
            { value: 'life',    label: 'life' },
            { value: 'climate', label: 'climate' },
            { value: 'software',label: 'software' },
          ]}
        />
      </FilterBar>

      <SplitMasterDetail>
        <Table
          columns={[
            { id: 'swatch', header: '', width: 28, render: c => <KGNode size="sm" domain={c.domain} /> },
            { id: 'id',     header: 'identifier', mono: true, render: c => c.id },
            { id: 'title',  header: 'title', render: c => <Link>{c.title}</Link> },
            { id: 'desc',   header: 'description', muted: true, render: c => c.description },
            { id: 'scheme', header: 'scheme', render: c => <KGNode size="sm" domain={c.domain}>{schemeOf(c).title}</KGNode> },
            { id: 'ind',    header: 'ind.', align: 'right', mono: true, render: c => c.individuals },
            { id: 'ver',    header: 'ver',  align: 'right', render: c => <VersionPill>v{c.version}</VersionPill> },
          ]}
          rows={rows}
          getRowId={c => c.id}
          selectedRowId={selectedId}
          onSelectRow={setSelectedId}
        />

        {selected ? (
          <InspectorPanel
            eyebrow={`class · ${selected.domain}`}
            title={selected.title}
            id={selected.id}
            actions={
              <>
                <VersionPill>v{selected.version}</VersionPill>
                <Button variant="ghost" size="icon" icon="edit" />
                <Button variant="ghost" size="icon" icon="more" />
              </>
            }
          >
            <KVGrid
              rows={[
                { key: 'Description', value: selected.description },
                { key: 'Domain',      value: <KGNode size="sm" domain={selected.domain}>{selected.domain}</KGNode> },
                { key: 'Scheme',      value: <Row gap={6}><KGNode size="sm" domain={selected.domain}>{schemeOf(selected).title}</KGNode><Mono muted>{selected.concept_scheme_id}</Mono></Row> },
                { key: 'Taxonomy',    value: <Row gap={6}><KGNode size="sm" domain={selected.domain}>{taxOf(selected).title}</KGNode><Mono muted>{selected.taxonomy_id}</Mono></Row> },
                { key: 'Parent class', value: parentOf(selected) ? <KGNode size="sm" domain={selected.domain}>{parentOf(selected)!.title}</KGNode> : <EmptyValue>— root —</EmptyValue> },
                { key: 'Children',    value: childrenList(selected) },
              ]}
            />

            <InspectorPanel.Section
              title="Property definitions"
              count={selected.properties.length}
              actions={<Button size="xs" icon="plus">Add</Button>}
            >
              <PropertyTable properties={selected.properties} />
            </InspectorPanel.Section>

            <InspectorPanel.Section title="Sample individuals" count={selected.individuals}>
              <SampleIndividuals classId={selected.id} />
            </InspectorPanel.Section>
          </InspectorPanel>
        ) : (
          <EmptyState
            icon="schema"
            title="No class selected"
            description="Pick a class from the table to see its definition."
          />
        )}
      </SplitMasterDetail>
    </>
  );
}
```

**Notes:**

- `Tabs` count chips: the count is just a number on the `Tabs.Item`. The mono chip styling is internal.
- `SplitMasterDetail` is a 1fr + 1.5fr grid. The Inspector lives inline, never as an overlay (use `Drawer` for overlay flows).
- `KVGrid` keys are mono caps; the component handles 130px column width, tracking, and color. Don't style the keys yourself.

### 4.3 Pipelines

```tsx
import { PageHead, Tabs, FilterBar, PipelineCard } from '@tinkermonkey/heimdall-ui';

export function PipelinesPage({ data }: { data: Workspace }) {
  const [statusFilter, setStatusFilter] = useState<Status | 'all'>('all');
  const visible = useMemo(
    () => statusFilter === 'all' ? data.pipelines : data.pipelines.filter(p => p.status === statusFilter),
    [statusFilter, data.pipelines]
  );

  return (
    <>
      <PageHead
        eyebrow={[
          <Chip key="p" tone="amber" dot>pipelines</Chip>,
          <Chip key="c" form="id-tag">6 pipelines</Chip>,
          <Muted key="m" mono size={11}>1 running · 2 idle · 2 ok · 1 failed</Muted>,
        ]}
        title={<>Pipelines <IdTag>/pipelines/all</IdTag></>}
        subtitle="A pipeline is a source → extract → resolve → write chain. Each run materializes individuals (or schema) from a reference source. Runs are append-only — partial writes are kept on failure."
        actions={
          <>
            <Button icon="reference">Catalog</Button>
            <Button variant="primary" icon="plus">New pipeline</Button>
          </>
        }
      />

      <FilterBar searchPlaceholder="Filter by name, target, or step…">
        <SegmentedControl
          value={statusFilter}
          onChange={setStatusFilter}
          options={[
            { value: 'all',     label: 'All' },
            { value: 'running', label: 'Running', badge: 1 },
            { value: 'success', label: 'Success', badge: 2 },
            { value: 'idle',    label: 'Idle',    badge: 2 },
            { value: 'failed',  label: 'Failed',  badge: 1 },
          ]}
        />
      </FilterBar>

      <Stack gap={14}>
        {visible.map(p => <PipelineCard key={p.id} pipeline={p} />)}
      </Stack>
    </>
  );
}
```

The `PipelineCard` produces the head + flow strip + 5-col foot row in one element. Pass the whole pipeline object — don't reach inside to render the flow yourself.

### 4.4 Graph view

```tsx
import { PageHead, FilterDropdown, GraphCanvas, GraphNode, KGNode, Panel, KVGrid, InspectorPanel } from '@tinkermonkey/heimdall-ui';

export function GraphViewPage({ data }: { data: Workspace }) {
  const [domains, setDomains] = useState({ life: true, climate: true, software: true });
  const [show, setShow] = useState({ classes: true, individuals: false, edges: true, edge_labels: false });
  const [layout, setLayout] = useState<'columns' | 'force' | 'tree'>('columns');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>('cls_gene');

  const nodes = computeGraph(data, { domains, show, layout });
  const selected = data.classes.find(c => c.id === selectedNodeId);

  return (
    <>
      <PageHead
        eyebrow={[
          <Chip key="g" tone="violet" dot>graph</Chip>,
          <Muted key="m" mono size={11}>20 nodes · 9 edges · 3 domains</Muted>,
        ]}
        title={<>Graph view <IdTag>/graph</IdTag></>}
        subtitle="Force-directed layout of classes (large nodes) and individuals (small nodes). Edges are typed relationships. Drag to reposition, scroll to zoom."
        actions={
          <>
            <Button icon="refresh">Re-layout</Button>
            <Button variant="primary" icon="ext">Export PNG</Button>
          </>
        }
      />

      <FilterBar>
        <FilterDropdown label="Domain" summary={summarize(domains, 3)}>
          <FilterDropdown.Section>Domains</FilterDropdown.Section>
          {(['life','climate','software'] as Domain[]).map(d => (
            <FilterDropdown.Checkbox
              key={d}
              checked={domains[d]}
              onChange={v => setDomains(s => ({ ...s, [d]: v }))}
              meta={countByDomain(data, d)}
            >
              <KGNode size="sm" domain={d}>{d}</KGNode>
            </FilterDropdown.Checkbox>
          ))}
        </FilterDropdown>

        <FilterDropdown label="Show" summary={`${Object.values(show).filter(Boolean).length} of 4`}>
          <FilterDropdown.Section>Nodes</FilterDropdown.Section>
          <FilterDropdown.Checkbox checked={show.classes}      onChange={v => setShow(s => ({...s, classes: v}))}>Classes</FilterDropdown.Checkbox>
          <FilterDropdown.Checkbox checked={show.individuals}  onChange={v => setShow(s => ({...s, individuals: v}))}>Individuals</FilterDropdown.Checkbox>
          <FilterDropdown.Section>Edges</FilterDropdown.Section>
          <FilterDropdown.Checkbox checked={show.edges}        onChange={v => setShow(s => ({...s, edges: v}))}>Edges</FilterDropdown.Checkbox>
          <FilterDropdown.Checkbox checked={show.edge_labels}  onChange={v => setShow(s => ({...s, edge_labels: v}))}>Edge labels</FilterDropdown.Checkbox>
        </FilterDropdown>

        <FilterDropdown label="Layout" summary={LAYOUT_LABELS[layout]}>
          {(['columns','force','tree'] as const).map(k => (
            <FilterDropdown.Radio key={k} checked={layout === k} onChange={() => setLayout(k)}>
              {LAYOUT_LABELS[k]}
            </FilterDropdown.Radio>
          ))}
        </FilterDropdown>

        <FilterBar.Spacer />
        <Muted mono size={11}>{nodes.length} nodes · {edgesCount} edges visible</Muted>
      </FilterBar>

      <Split cols={['1fr', 320]} gap={14}>
        <GraphCanvas
          toolbar={[
            { id: 'pan',  icon: 'expand',    active: true,  title: 'Pan' },
            { id: 'in',   icon: 'plus',                     title: 'Zoom in' },
            { id: 'out',  icon: 'x',                        title: 'Zoom out' },
            { id: 'fit',  icon: 'dashboard',                title: 'Fit' },
          ]}
          legend={[
            { color: '#10B981', label: 'life' },
            { color: '#FBBF24', label: 'climate' },
            { color: '#818CF8', label: 'software' },
            { kind: 'solid',  label: 'manual' },
            { kind: 'dashed', label: 'inferred' },
          ]}
          minimap                                        // boolean — built-in
        >
          {nodes.map(n => (
            <GraphNode
              key={n.id}
              x={n.x} y={n.y}
              label={n.title}
              domain={n.domain}
              selected={n.id === selectedNodeId}
              onSelect={() => setSelectedNodeId(n.id)}
            />
          ))}
          {/* edges rendered automatically from the parent layout, or pass <GraphEdge> children */}
        </GraphCanvas>

        {selected && (
          <InspectorPanel
            eyebrow="class"
            title={selected.title}
            id={selected.id}
          >
            <KVGrid rows={[
              { key: 'Identifier',  value: <Mono>{selected.id}</Mono> },
              { key: 'Domain',      value: <KGNode size="sm" domain={selected.domain}>{selected.domain}</KGNode> },
              { key: 'Individuals', value: <Mono>{selected.individuals}</Mono> },
              { key: 'Version',     value: <VersionPill>v{selected.version}</VersionPill> },
            ]} />
          </InspectorPanel>
        )}
      </Split>
    </>
  );
}
```

### 4.5 Configuration

```tsx
import { PageHead, ConfigTile } from '@tinkermonkey/heimdall-ui';

export function ConfigurationPage() {
  return (
    <>
      <PageHead
        title={<>Configuration <IdTag>/settings</IdTag></>}
        subtitle="Workspace-scoped settings. Most changes apply immediately; pipeline-affecting changes require a restart of the graph daemon."
      />

      <Grid cols={2} gap={12}>
        <ConfigTile
          icon="shield"
          title="Backups"
          description="Automatic snapshots are stored alongside the workspace."
          summary={[
            { label: 'last',   value: '4h ago' },
            { label: 'retain', value: '7d' },
          ]}
          action={<Button size="sm">Manage</Button>}
        />
        <ConfigTile
          icon="cpu"
          title="Graph daemon"
          description="Local Neo4j-compatible daemon serving the workspace."
          summary={[
            { label: 'port', value: ':7474' },
            { label: 'mem',  value: '423 MB' },
          ]}
        />
        {/* … */}
      </Grid>
    </>
  );
}
```

---

## 5 · Overlays

### Command palette

```tsx
const paletteSources = [
  { kind: 'Recent',  items: recentItems },         // chip color: amber
  { kind: 'Class',   items: classHits },           // chip color: cyan
  { kind: 'Individual', items: individualHits },   // chip color: cyan
  { kind: 'Pipeline',items: pipelineHits },        // chip color: cyan
  { kind: 'Go',      items: navItems },            // chip color: cyan
  { kind: 'Action',  items: actionItems },         // chip color: emerald
];

<CommandPalette
  open={open}
  onClose={…}
  sources={paletteSources}
  groupOrder={['Recent', 'Class', 'Individual', 'Pipeline', 'Go', 'Action']}
  placeholder="Search nodes, run a command, jump to…"
  shortcut="⌘K"
/>
```

The palette handles ⌘K open, ↑/↓ navigation, Enter, and Esc. Each `item` is `{ label, hint?, icon?, route?, onSelect? }`. If a `route` is set, the palette calls the app's navigator on Enter.

### Modal (new class, edit, etc.)

```tsx
import { Modal, ModalHead, ModalBody, ModalFoot, ModalFootHint, Field, Input, Select } from '@tinkermonkey/heimdall-ui';

<Modal open={open} onClose={close} width={560}>
  <ModalHead
    title="New class"
    subtitle="Classes belong to a concept scheme and inherit property definitions from their parent."
  />
  <ModalBody>
    <Field
      label="Identifier"
      hintRight={<Mono>snake_case · required</Mono>}
      hint={<>Must match <Mono>/^cls_[a-z][a-z0-9_]*$/</Mono></>}
    >
      <Input mono defaultValue="cls_neuron_motor" autoFocus />
    </Field>
    <Field label="Display title">
      <Input defaultValue="Motor neuron" />
    </Field>
    <Field label="Concept scheme">
      <Select mono options={schemeOptions} />
    </Field>
    <Field label="Parent class" hintRight="optional">
      <Select mono options={parentOptions} placeholder="— none —" />
    </Field>
    <Field label="Description">
      <Textarea rows={3} defaultValue="…" />
    </Field>
  </ModalBody>
  <ModalFoot hint={<ModalFootHint>POST /classes</ModalFootHint>}>
    <Button variant="ghost" onClick={close}>Cancel</Button>
    <Button variant="primary" onClick={create}>Create class</Button>
  </ModalFoot>
</Modal>
```

`ModalFootHint` is the mono `POST /classes` API-verb hint pinned to the left of the action row. Always include one when the modal triggers a server call — it makes the side-effect explicit.

### Toast

```ts
import { useToast } from '@tinkermonkey/heimdall-ui';

const toast = useToast();

toast.success({ title: 'Class created', subtitle: <Mono>cls_neuron_motor · sch_cell_bio</Mono> });
toast.fail({ title: 'Pipeline failed', subtitle: <Mono>pipeline.run failed — connection refused at step 2</Mono> });
```

Toasts auto-dismiss after 4.5s. Errors are terse; include the failure point as mono code in `subtitle`.

---

## 6 · Patterns to follow

### Identifier rendering

```tsx
// ✅ canonical
<KGNode size="sm" domain="life">{cls.title}</KGNode>
<Mono>{cls.id}</Mono>
<VersionPill>v{cls.version}</VersionPill>

// ❌ avoid — produces inconsistent type metrics
<span className="mono">{cls.id}</span>
<code>v{cls.version}</code>
```

### Status colors

Use the semantic intents, never raw hex:

| Intent       | Token            | Use case                            |
| ------------ | ---------------- | ----------------------------------- |
| `ok`         | `--status-ok`    | running, healthy                    |
| `warn`       | `--status-amber` | degraded, attention                 |
| `error`      | `--status-rose`  | failed, errored, unhealthy          |
| `updating`   | `--status-cyan`  | pulling, updating, partial          |
| `info`       | `--status-violet`| info-secondary                       |
| `neutral`    | `--status-neutral`| stopped, idle                       |

Pass `tone="ok"` etc. to `Chip`, `Pulse`, `Badge` — don't open the CSS to set a background.

### Empty states

```tsx
<EmptyState
  icon="data"
  title="No individuals match these filters."
  description="Adjust the domain or scheme filters above to broaden the search."
/>
```

Title is a complete sentence, period included. Description gives a concrete next action. No exclamation.

### Density

| Context                  | Padding (V/H)     |
| ------------------------ | ----------------- |
| Compact (table row, nav) | 8–10 / 12–14      |
| Standard (panel head)    | 12–14 / 14–16     |
| Generous (modal head)    | 18–22 / 20        |

All components above use the right density by default. **Don't override paddings on shipped components** — if the spacing's wrong, that's a kit bug.

---

## 7 · Common pitfalls

| Anti-pattern                                                | What to do                                                                                                          |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Wrapping `<Tabs>` in your own bottom border                 | `<Tabs>` ships its own — remove the wrapper                                                                          |
| Nesting `<Drawer>` inline alongside a list                  | Use `<InspectorPanel>` — `<Drawer>` is overlay only                                                                  |
| Adding `<Sparkline>` manually inside `<StatTile>`'s `meta`   | Pass `sparkData` directly to `<StatTile>`                                                                            |
| Inventing a new domain color (e.g. `pink`)                   | Stick to the 4 domain tokens — extend `--dom-*` if you genuinely need a new one, with design review                  |
| Floating shadow on a card                                    | Cards are **border-only**. Shadows are reserved for `Modal` and `Toast`                                              |
| Topbar without the palette field                             | Always show the palette — it's the studio's primary navigation surface                                               |
| Pill-shaped buttons                                          | Buttons use `--radius-md` (6px). Pill shape is reserved for the env pill and round dots                              |
| Emoji in headings / chips                                    | No. Use the icon map.                                                                                                 |

---

## 8 · Reference

- **Visual contract:** `Context Studio.html` in this project — every screen, every interaction, fully working.
- **Design system source:** `tinkermonkey/heimdall` repo, `design-reference/example-context-studio/`.
- **Component gaps to close:** `HEIMDALL_HANDOFF.md` (this project).
- **Design system updates from the prototype review:** `DESIGN_SYSTEM_UPDATE_HANDOFF.md` (this project).
- **Live validation:** open `Design System Validation.html` to see all 14 new + 3 extended preview cards side-by-side.

When a question comes up that the doc doesn't answer, **open the prototype** and inspect the exact element. The prototype is the spec.
