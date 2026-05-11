// Pages — Dashboard, Schema (Taxonomies/Classes/Properties/Relationships),
// Data, Pipelines, Reference, Settings.

function StatTile({ label, value, color, meta }) {
  return (
    <div className="stat" data-color={color}>
      <div className="label">{label}</div>
      <div className="num">{value}</div>
      {meta && <div className="meta">{meta}</div>}
    </div>
  );
}

function DashboardPage({ onNav }) {
  const D = window.CS_DATA;
  const totalClasses = D.classes.length;
  const totalIndividuals = D.individuals.length + 257;
  const totalProps = (D.property_definitions || D.properties || []).length + 21;
  const runningPipelines = D.pipelines.filter((p) => p.status === "running").length;

  return (
    <div className="canvas-inner">
      <div className="page-head">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <span className="chip cyan">
              <span className="dot"></span>workspace · default
            </span>
            <span className="muted mono" style={{ fontSize: 11 }}>
              last sync 2 min ago
            </span>
          </div>
          <h1>
            Dashboard <span className="id-tag">/workspace/default</span>
          </h1>
          <div className="subtitle">
            Curate knowledge graphs for retrieval-augmented generation and agents.
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost">
            <Icon name="refresh" /> Refresh
          </button>
          <button className="btn btn-primary">
            <Icon name="plus" /> New pipeline run
          </button>
        </div>
      </div>

      <div className="stat-grid" style={{ marginBottom: 22 }}>
        <StatTile
          label="Taxonomies"
          value={D.taxonomies.length}
          color="cyan"
          meta={<span className="muted">3 active · 0 archived</span>}
        />
        <StatTile
          label="Classes"
          value={totalClasses}
          color="violet"
          meta={
            <>
              <span className="delta-up">▲ 4</span>
              <span className="muted">this week</span>
            </>
          }
        />
        <StatTile
          label="Individuals"
          value={totalIndividuals}
          color="emerald"
          meta={
            <>
              <span className="delta-up">▲ 38</span>
              <span className="muted">last run</span>
            </>
          }
        />
        <StatTile
          label="Pipelines"
          value={`${runningPipelines}/${D.pipelines.length}`}
          color="amber"
          meta={
            <span className="status-line">
              <span className="pulse"></span>
              <span className="muted">1 running</span>
            </span>
          }
        />
      </div>

      <div className="split-2" style={{ gridTemplateColumns: "1.55fr 1fr", marginBottom: 22 }}>
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">
              <Icon name="schema" size={14} />
              Knowledge Graph Structure
            </div>
            <div className="row gap-12">
              <span className="muted mono" style={{ fontSize: 11, whiteSpace: "nowrap" }}>
                3 tax · {totalClasses} cls
              </span>
              <button className="btn btn-ghost btn-sm" onClick={() => onNav("schema/classes")}>
                Open <Icon name="arrow" />
              </button>
            </div>
          </div>
          <div className="panel-body" style={{ maxHeight: 480, overflow: "auto" }}>
            <HierarchyViewer data={D} />
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">
              <Icon name="history" size={14} />
              Recent activity
            </div>
            <button className="btn btn-ghost btn-sm">View all</button>
          </div>
          <div className="activity-list">
            {D.activity.map((a, i) => (
              <div className={"activity-item " + a.kind} key={i}>
                <div className="dot-col">
                  <span className="d"></span>
                </div>
                <div className="content">
                  <div className="head">
                    <span
                      className="muted mono"
                      style={{
                        textTransform: "uppercase",
                        fontSize: 10,
                        marginRight: 6,
                        letterSpacing: "0.06em",
                      }}
                    >
                      {a.kind}
                    </span>
                    <b>{a.what}</b> — {a.subject}
                  </div>
                  <div className="meta-line">
                    {a.meta} · by {a.who}
                  </div>
                </div>
                <div className="when">{a.when}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: 22 }}>
        <div className="panel-head">
          <div className="panel-title">
            <Icon name="pipeline" size={14} />
            Active pipelines
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => onNav("pipelines/all")}>
            All pipelines <Icon name="arrow" />
          </button>
        </div>
        <div
          className="panel-body"
          style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}
        >
          {D.pipelines.slice(0, 2).map((p) => (
            <PipelineCard key={p.id} pipeline={p} compact />
          ))}
        </div>
      </div>

      <div>
        <div className="between" style={{ marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Quick access</h3>
          <span className="muted" style={{ fontSize: 12 }}>
            Jump to common workflows
          </span>
        </div>
        <div className="qa-grid">
          {[
            [
              "schema/taxonomies",
              "schema",
              "Taxonomies",
              "Manage top-level domains and concept schemes",
            ],
            ["schema/classes", "graph", "Classes", "Define the structure of your knowledge"],
            ["schema/properties", "tag", "Properties", "Object and literal property definitions"],
            ["data/individuals", "data", "Individuals", "Browse instances populated from sources"],
            ["pipelines/all", "pipeline", "Pipelines", "Configure and run Graph RAG pipelines"],
            [
              "reference/sources",
              "reference",
              "Reference sources",
              "External APIs and document corpora",
            ],
          ].map(([r, ic, n, d]) => (
            <div key={r} className="qa" onClick={() => onNav(r)}>
              <div className="qa-icon">
                <Icon name={ic} size={16} />
              </div>
              <div className="qa-body">
                <div className="n">{n}</div>
                <div className="d">{d}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

window.DashboardPage = DashboardPage;
