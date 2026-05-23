// =========================================================================
// Dashboard page — workspace overview
//   • Stat grid with mono labels + sparklines
//   • Hierarchy panel (taxonomy → scheme → class)
//   • Recent activity feed (mono, intent dots)
//   • Active pipelines (full cards with flow strips)
//   • Quick access tiles
// =========================================================================

function StatTile({ label, value, color, meta, sparkData, sparkColor, icon }) {
  return (
    <div className="stat" data-color={color}>
      <div className="label">
        {icon && <Icon name={icon} size={11} />}
        {label}
      </div>
      <div className="num">{value}</div>
      {meta && <div className="meta">{meta}</div>}
      {sparkData && (
        <div className="spark">
          <Sparkline data={sparkData} color={sparkColor || "#FBBF24"} />
        </div>
      )}
    </div>
  );
}
window.StatTile = StatTile;

function DashboardPage({ onNav }) {
  const D = window.CS_DATA;
  const totalClasses = D.classes.length;
  const totalIndividuals = D.individuals.length + 251; // sample subset on page
  const totalProps = D.property_definitions.length;
  const runningPipelines = D.pipelines.filter((p) => p.status === "running").length;
  const failedPipelines = D.pipelines.filter((p) => p.status === "failed").length;

  return (
    <div className="canvas-inner" data-screen-label="01 Dashboard">
      <div className="page-head">
        <div>
          <div className="page-head-meta">
            <span className="chip amber"><span className="dot"></span>workspace · default</span>
            <span className="muted mono" style={{fontSize: 11}}>last sync {D.workspace.last_sync}</span>
            <span className="muted mono" style={{fontSize: 11}}>·</span>
            <span className="muted mono" style={{fontSize: 11}}>graph daemon healthy</span>
          </div>
          <h1>Dashboard <span className="id-tag">/workspace/{D.workspace.name}</span></h1>
          <div className="subtitle">
            Curate knowledge graphs for retrieval-augmented generation and agents.
            Taxonomies group concept schemes; concept schemes hold classes; classes hold individuals.
          </div>
        </div>
        <div className="page-actions">
          <button className="btn"><Icon name="refresh" size={13} /> Refresh</button>
          <button className="btn btn-primary"><Icon name="plus" size={13} /> New pipeline run</button>
        </div>
      </div>

      {/* ---- Stat grid with sparklines ---- */}
      <div className="stat-grid" style={{marginBottom: 18}}>
        <StatTile label="Taxonomies" value={D.taxonomies.length} color="cyan" icon="schema"
          meta={<><span className="muted">3 active · 0 archived</span></>}
          sparkData={D.sparks.taxonomies} sparkColor="#22D3EE" />
        <StatTile label="Classes" value={totalClasses} color="violet" icon="schema"
          meta={<><span className="delta-up">▲ 4</span> <span className="muted">this week</span></>}
          sparkData={D.sparks.classes} sparkColor="#A78BFA" />
        <StatTile label="Individuals" value={totalIndividuals} color="emerald" icon="data"
          meta={<><span className="delta-up">▲ 38</span> <span className="muted">last run · 412 ingested</span></>}
          sparkData={D.sparks.individuals} sparkColor="#10B981" />
        <StatTile label="Pipelines" value={`${runningPipelines}/${D.pipelines.length}`} color="amber" icon="pipeline"
          meta={<><span className="pulse sm amber"></span><span className="muted">1 running · {failedPipelines} failed</span></>}
          sparkData={D.sparks.ingestRate} sparkColor="#FBBF24" />
      </div>

      {/* ---- Hierarchy + Activity ---- */}
      <div className="split-2" style={{marginBottom: 18}}>
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title"><Icon name="schema" size={14}/>Knowledge graph structure</div>
            <div className="row gap-12">
              <span className="muted mono" style={{fontSize: 11, whiteSpace: "nowrap"}}>
                {D.taxonomies.length} tax · {D.concept_schemes.length} sch · {totalClasses} cls
              </span>
              <button className="btn btn-ghost btn-sm" onClick={() => onNav("schema/classes")}>Open <Icon name="arrow" size={11}/></button>
            </div>
          </div>
          <div className="panel-body flush" style={{maxHeight: 520, overflow: "auto"}}>
            <HierarchyViewer data={D} />
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div className="panel-title"><Icon name="history" size={14}/>Recent activity</div>
            <button className="btn btn-ghost btn-sm">View all</button>
          </div>
          <div className="activity-list">
            {D.activity.slice(0, 7).map((a, i) => (
              <div className="activity-row" data-kind={a.kind} key={i}>
                <div className="dot-col"><span className="d"></span></div>
                <div>
                  <div className="headline">
                    <span className="kind-tag">{a.kind}</span>
                    <b>{a.what}</b>
                    <span className="subj">{a.subject}</span>
                  </div>
                  <div className="meta">{a.meta} · by {a.who}</div>
                </div>
                <div className="when">{a.when}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ---- Active pipelines ---- */}
      <div className="panel" style={{marginBottom: 18}}>
        <div className="panel-head">
          <div className="panel-title"><Icon name="pipeline" size={14}/>Active pipelines</div>
          <div className="row gap-12">
            <span className="muted mono" style={{fontSize: 11}}>{runningPipelines} running · {D.pipelines.length - runningPipelines} idle</span>
            <button className="btn btn-ghost btn-sm" onClick={() => onNav("pipelines/all")}>All pipelines <Icon name="arrow" size={11}/></button>
          </div>
        </div>
        <div className="panel-body" style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14}}>
          {D.pipelines.slice(0, 2).map((p) => <PipelineCard key={p.id} pipeline={p} compact />)}
        </div>
      </div>

      {/* ---- Quick access ---- */}
      <div>
        <div className="between" style={{marginBottom: 12}}>
          <h3 style={{margin: 0, fontSize: 14, fontWeight: 600}}>Quick access</h3>
          <span className="muted" style={{fontSize: 12}}>Jump to common workflows</span>
        </div>
        <div className="qa-grid">
          {[
            ["schema/taxonomies",  "schema",    "Taxonomies",        "Manage top-level domains and concept schemes"],
            ["schema/classes",     "graph",     "Classes",           "Define the structure of your knowledge"],
            ["schema/properties",  "tag",       "Properties",        "Object and literal property definitions"],
            ["data/individuals",   "data",      "Individuals",       "Browse instances populated from sources"],
            ["pipelines/all",      "pipeline",  "Pipelines",         "Configure and run Graph-RAG pipelines"],
            ["reference/sources",  "reference", "Reference sources", "External APIs and document corpora"],
          ].map(([r, ic, n, d]) => (
            <div key={r} className="qa-tile" onClick={() => onNav(r)}>
              <div className="icon"><Icon name={ic} size={16}/></div>
              <div className="body">
                <div className="n">{n}</div>
                <div className="d">{d}</div>
              </div>
              <Icon name="arrow" size={13} className="chev" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
window.DashboardPage = DashboardPage;
