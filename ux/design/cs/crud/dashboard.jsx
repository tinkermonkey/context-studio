// =========================================================================
// Context Studio — Dashboard (store-aware)
// Overrides the base CSDashboard so the overview reflects LIVE CRUD edits:
// stat counts, the knowledge-graph hierarchy, and the activity feed all read
// from the CRUD store (useCS) instead of the static CS_DATA snapshot.
// Pipelines / sparklines / workspace remain from CS_DATA (not CRUD'd here).
// Loaded after cs/pages.jsx so this window.CSDashboard wins.
// =========================================================================

function CSDashboard({ onNav }) {
  const data = useCS();                 // live entities + activity
  const STATIC = window.CS_DATA;        // pipelines, sparks, workspace

  const totalTaxonomies = data.taxonomies.length;
  const totalSchemes = data.concept_schemes.length;
  const totalClasses = data.classes.length;
  // headline individuals: live sample count + the indexed baseline, so the
  // number stays realistic yet moves by ±1 as individuals are created/deleted.
  const INDEXED_BASELINE = 251;
  const totalIndividuals = data.individuals.length + INDEXED_BASELINE;
  const running = STATIC.pipelines.filter((p) => p.status === "running").length;
  const failed = STATIC.pipelines.filter((p) => p.status === "failed").length;

  const [open, setOpen] = useState(() => ({
    [data.taxonomies[0]?.id]: true,
    [data.concept_schemes[0]?.id]: true,
  }));
  const [selClass, setSelClass] = useState("cls_gene");
  const toggle = (id) => setOpen((o) => ({ ...o, [id]: !o[id] }));
  const asDom = (d) => d || "default";

  // activity → ActivityTimeline events (handles the store's "now" entries)
  const tsFor = (when) => {
    const now = Date.now();
    if (!when || /now|just/i.test(when)) return new Date(now);
    const m = when.match(/(\d+)\s*(m|h|d)/i);
    if (!m) return new Date(now);
    const n = parseInt(m[1], 10);
    const u = m[2].toLowerCase();
    return new Date(now - n * (u === "m" ? 60000 : u === "h" ? 3600000 : 86400000));
  };
  const activityEvents = data.activity.slice(0, 8).map((a, i) => ({
    id: `act-${i}-${a.subject}`,
    type: a.kind === "create" ? "create" : a.kind === "update" ? "update" : a.kind === "delete" ? "delete" : "run",
    kind: a.kind, kindLabel: a.kind,
    subject: `${a.what} ${a.subject}`,
    meta: `${a.meta || ""}${a.meta ? " · " : ""}by ${a.who}`,
    timestamp: tsFor(a.when),
  }));

  const ICON_REMAP = { reference: "link", sparkle: "zap", doc: "file", database: "hardDrive" };
  const toHeimdallPipeline = (p) => ({
    id: p.id, name: p.name, description: p.description, status: p.status, target: p.target, tags: p.tags, lastRun: p.lastRun,
    flow: p.flow.map((s, i) => ({ id: `${p.id}-${i}`, name: s.name, label: s.kind, icon: ICON_REMAP[s.ic] || s.ic })),
    recent: p.recent || { ingested: 0, created: 0, updated: 0, errors: 0 },
  });

  return (
    <div data-screen-label="01 Dashboard">
      <div className="cs-page-meta">
        <Chip variant="amber">workspace · {STATIC.workspace.name}</Chip>
        <span>last sync {STATIC.workspace.last_sync}</span>
        <span className="cs-page-meta__sep">·</span>
        <span className="cs-page-meta__health">graph daemon healthy</span>
      </div>

      <PageHeader
        title="Dashboard"
        idChip={`/workspace/${STATIC.workspace.name}`}
        subtitle="Curate knowledge graphs for retrieval-augmented generation and agents. Taxonomies group concept schemes; concept schemes hold classes; classes hold individuals."
        actions={
          <>
            <Button variant="ghost" onClick={() => {}}><Icon name="reload" size={13} /> Refresh</Button>
            <Button variant="primary" onClick={() => onNav("pipelines/all")}><Icon name="plus" size={13} /> New pipeline run</Button>
          </>
        }
      />

      <div style={{ height: 18 }} />

      <StatGrid columns={4}>
        <StatTile label="TAXONOMIES" value={totalTaxonomies} color="cyan" icon="schema" meta={`${totalSchemes} schemes`} sparkData={STATIC.sparks.taxonomies} />
        <StatTile label="CLASSES" value={totalClasses} color="violet" icon="schema" delta={{ value: 4, label: "this week", direction: "up" }} sparkData={STATIC.sparks.classes} />
        <StatTile label="INDIVIDUALS" value={totalIndividuals.toLocaleString()} color="emerald" icon="data" delta={{ value: 38, label: "last run · 412 ingested", direction: "up" }} sparkData={STATIC.sparks.individuals} />
        <StatTile label="PIPELINES" value={`${running}/${STATIC.pipelines.length}`} color="amber" icon="pipeline" meta={`${running} running · ${failed} failed`} sparkData={STATIC.sparks.ingestRate} />
      </StatGrid>

      <div style={{ height: 18 }} />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 14 }}>
        <Panel
          title="Knowledge graph structure"
          headerAction={
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "rgb(var(--canvas-fg-3))", whiteSpace: "nowrap" }}>
                {totalTaxonomies} tax · {totalSchemes} sch · {totalClasses} cls
              </span>
              <Button variant="ghost" size="sm" onClick={() => onNav("schema/classes")}>Open <Icon name="arrowRight" size={11} /></Button>
            </div>
          }
          noPadding
        >
          <div style={{ padding: "6px 0" }}>
            <HierarchyTree>
              {data.taxonomies.map((tax) => {
                const schemes = data.concept_schemes.filter((s) => s.taxonomy_id === tax.id);
                const taxOpen = open[tax.id];
                return (
                  <React.Fragment key={tax.id}>
                    <HierarchyRow depth={0} domain={asDom(tax.domain)} kind="taxonomy" label={tax.title} meta={tax.id} description={tax.description} onSelect={() => toggle(tax.id)} />
                    {taxOpen && schemes.map((sch) => {
                      const cls = data.classes.filter((c) => c.concept_scheme_id === sch.id);
                      const schOpen = open[sch.id];
                      return (
                        <React.Fragment key={sch.id}>
                          <HierarchyRow depth={1} domain={asDom(sch.domain)} kind="scheme" label={sch.title} meta={sch.id} description={sch.description} onSelect={() => toggle(sch.id)} />
                          {schOpen && cls.map((c) => (
                            <HierarchyRow key={c.id} depth={2} domain={asDom(c.domain)} kind="class" label={c.title} meta={c.id} description={c.description} selected={selClass === c.id} onSelect={() => setSelClass(c.id)} />
                          ))}
                        </React.Fragment>
                      );
                    })}
                  </React.Fragment>
                );
              })}
            </HierarchyTree>
          </div>
        </Panel>

        <Panel title="Recent activity" headerAction={<Button variant="ghost" size="sm">View all</Button>} noPadding>
          <div style={{ padding: "4px 4px 8px" }}>
            <ActivityTimeline events={activityEvents} />
          </div>
        </Panel>
      </div>

      <div style={{ height: 18 }} />

      <Panel
        title="Active pipelines"
        headerAction={
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "rgb(var(--canvas-fg-3))" }}>{running} running · {STATIC.pipelines.length - running} idle</span>
            <Button variant="ghost" size="sm" onClick={() => onNav("pipelines/all")}>All pipelines <Icon name="arrowRight" size={11} /></Button>
          </div>
        }
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          {STATIC.pipelines.slice(0, 2).map((p) => (
            <PipelineCard key={p.id} pipeline={toHeimdallPipeline(p)} compact onOptions={() => {}} onRun={() => {}} />
          ))}
        </div>
      </Panel>

      <div style={{ height: 24 }} />

      <div className="cs-between" style={{ marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "rgb(var(--canvas-fg-1))" }}>Quick access</h3>
        <span style={{ color: "rgb(var(--canvas-fg-3))", fontSize: 12 }}>Jump to common workflows</span>
      </div>
      <QuickAccessGrid tiles={[
        { id: "tax", icon: "schema", title: "Taxonomies", description: "Manage top-level domains and concept schemes" },
        { id: "cls", icon: "graph", title: "Classes", description: "Define the structure of your knowledge" },
        { id: "prop", icon: "component", title: "Properties", description: "Object and literal property definitions" },
        { id: "ind", icon: "data", title: "Individuals", description: "Browse instances populated from sources" },
        { id: "pipe", icon: "pipeline", title: "Pipeline types", description: "Curate configurations for each pipeline" },
        { id: "ref", icon: "link", title: "Reference sources", description: "External APIs and document corpora" },
      ]} onAction={(id) => onNav({ tax: "schema/taxonomies", cls: "schema/classes", prop: "schema/properties", ind: "data/individuals", pipe: "pipelines/types", ref: "reference/sources" }[id])} />
    </div>
  );
}
window.CSDashboard = CSDashboard;
