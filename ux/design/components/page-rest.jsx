// Data, Pipelines, Reference, Settings, Landing pages
// IndividualsPage moved to page-individuals.jsx.

function _DeprecatedIndividualsPage_unused() {
  const { state, actions } = useStore();
  const [search, setSearch] = useState("");
  const [classFilter, setClassFilter] = useState("all");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(null);
  const [confirm, setConfirm] = useState(null);

  const filtered = state.individuals.filter((i) => {
    if (classFilter !== "all" && !i.class_ids.includes(classFilter)) return false;
    return i.title.toLowerCase().includes(search.toLowerCase());
  });

  return (
    <div className="canvas-inner">
      <PageHeader
        title={
          <>
            Individuals{" "}
            <span className="id-tag">
              {filtered.length} of {state.individuals.length}
            </span>
          </>
        }
        subtitle="Concrete instances. Class membership is an ordered list — first parent wins on conflicts."
        actions={
          <>
            <button className="btn btn-ghost">
              <Icon name="ext" /> Export CSV
            </button>
            <button className="btn btn-primary" onClick={() => setCreating(true)}>
              <Icon name="plus" /> New individual
            </button>
          </>
        }
      />
      <FilterBar search={search} onSearch={setSearch} placeholder="Filter by label…">
        <select
          className="input"
          style={{ width: 220, height: 30, fontSize: 12.5 }}
          value={classFilter}
          onChange={(e) => setClassFilter(e.target.value)}
        >
          <option value="all">All classes</option>
          {state.classes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title}
            </option>
          ))}
        </select>
      </FilterBar>
      <div className="panel">
        <table className="t">
          <thead>
            <tr>
              <th style={{ width: 36 }}>
                <span className="check"></span>
              </th>
              <th>Label</th>
              <th>Class membership (ordered)</th>
              <th>Source</th>
              <th>Confidence</th>
              <th style={{ width: 70 }}>Ver</th>
              <th style={{ width: 80 }}></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((i) => (
              <tr key={i.id}>
                <td>
                  <span className="check"></span>
                </td>
                <td>
                  <span style={{ fontWeight: 500 }}>{i.title}</span>
                  <span className="mono muted" style={{ fontSize: 10.5, marginLeft: 6 }}>
                    {i.id}
                  </span>
                </td>
                <td>
                  <div className="row" style={{ flexWrap: "wrap", gap: 4 }}>
                    {i.class_ids.map((cid, idx) => {
                      const c = state.classes.find((x) => x.id === cid);
                      if (!c) return null;
                      return (
                        <span
                          key={cid}
                          className="kg-node"
                          data-domain={c.domain}
                          style={{ height: 22, fontSize: 11.5 }}
                        >
                          <span className="swatch"></span>
                          {idx === 0 && <span className="primary-rank mono">1</span>}
                          {c.title}
                        </span>
                      );
                    })}
                  </div>
                </td>
                <td className="mono muted" style={{ fontSize: 12 }}>
                  {i.source}
                </td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div
                      style={{
                        width: 60,
                        height: 4,
                        background: "var(--canvas-bg-2)",
                        borderRadius: 2,
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          width: `${i.confidence * 100}%`,
                          height: "100%",
                          background:
                            i.confidence > 0.95 ? "var(--accent-emerald)" : "var(--accent-amber)",
                        }}
                      ></div>
                    </div>
                    <span className="mono" style={{ fontSize: 11.5 }}>
                      {i.confidence.toFixed(2)}
                    </span>
                  </div>
                </td>
                <td>
                  <span className="version-pill">v{i.version}</span>
                </td>
                <td className="row-actions">
                  <RowMenu
                    items={[
                      { label: "Edit", icon: "edit", onClick: () => setEditing(i) },
                      "-",
                      { label: "Delete", icon: "x", danger: true, onClick: () => setConfirm(i) },
                    ]}
                  />
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  style={{ padding: "24px", textAlign: "center", color: "var(--canvas-fg-3)" }}
                >
                  No individuals match.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <IndividualDialog
        open={creating}
        onClose={() => setCreating(false)}
        initial={null}
        defaultClassId={classFilter !== "all" ? classFilter : null}
      />
      <IndividualDialog open={!!editing} onClose={() => setEditing(null)} initial={editing} />
      <ConfirmModal
        open={!!confirm}
        onClose={() => setConfirm(null)}
        title={"Delete " + (confirm?.title || "") + "?"}
        body={
          <>
            Individuals used in relationships return <code>409</code>. Delete those edges first.
          </>
        }
        onConfirm={() => {
          try {
            actions.deleteIndividual(confirm.id);
            setConfirm(null);
          } catch {}
        }}
      />
    </div>
  );
}

function PipelinesPage() {
  const D = window.CS_DATA;
  return (
    <div className="canvas-inner">
      <PageHeader
        title="Pipelines"
        subtitle="Configure Graph RAG pipelines that populate schema and data from external sources."
        badge={
          <div className="row gap-12">
            <span className="chip cyan">
              <span className="dot"></span>
              {D.pipelines.filter((p) => p.status === "running").length} running
            </span>
            <span className="chip rose">
              <span className="dot"></span>
              {D.pipelines.filter((p) => p.status === "failed").length} failed
            </span>
            <span className="chip emerald">
              <span className="dot"></span>
              {D.pipelines.filter((p) => p.status === "success").length} healthy
            </span>
          </div>
        }
        actions={
          <>
            <button className="btn btn-ghost">
              <Icon name="workflow" /> Flavors
            </button>
            <button className="btn btn-primary">
              <Icon name="plus" /> New pipeline
            </button>
          </>
        }
      />
      <div className="tabs">
        <div className="tab active">
          All <span className="count">{D.pipelines.length}</span>
        </div>
        <div className="tab">
          Schema-building <span className="count">2</span>
        </div>
        <div className="tab">
          Data-loading <span className="count">2</span>
        </div>
        <div className="tab">Run history</div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        {D.pipelines.map((p) => (
          <PipelineCard key={p.id} pipeline={p} />
        ))}
      </div>
    </div>
  );
}

function ReferencePage() {
  const sources = [
    {
      id: "src_pubmed",
      name: "PubMed",
      kind: "API",
      status: "connected",
      records: "36M",
      updated: "12m ago",
    },
    {
      id: "src_ncbi",
      name: "NCBI Gene",
      kind: "API",
      status: "connected",
      records: "1.4M",
      updated: "1h ago",
    },
    {
      id: "src_uniprot",
      name: "UniProt",
      kind: "API",
      status: "connected",
      records: "561K",
      updated: "2h ago",
    },
    {
      id: "src_reactome",
      name: "Reactome",
      kind: "API",
      status: "connected",
      records: "24K",
      updated: "6h ago",
    },
    {
      id: "src_ipcc",
      name: "IPCC AR6 corpus",
      kind: "PDFs",
      status: "indexed",
      records: "420 docs",
      updated: "2d ago",
    },
    {
      id: "src_eia",
      name: "EIA energy API",
      kind: "API",
      status: "auth-failed",
      records: "—",
      updated: "3h ago",
    },
    {
      id: "src_arxiv",
      name: "arXiv cs.SE",
      kind: "OAI-PMH",
      status: "connected",
      records: "124K",
      updated: "4h ago",
    },
  ];
  return (
    <div className="canvas-inner">
      <PageHeader
        title="External Reference Sources"
        subtitle="Authoritative sources used by pipelines for grounding and entity resolution."
        actions={
          <>
            <button className="btn btn-ghost">
              <Icon name="link" /> Test connections
            </button>
            <button className="btn btn-primary">
              <Icon name="plus" /> Add source
            </button>
          </>
        }
      />
      <div className="panel">
        <table className="t">
          <thead>
            <tr>
              <th>Name</th>
              <th>Kind</th>
              <th>Status</th>
              <th>Records</th>
              <th>Updated</th>
              <th>Used by</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.id}>
                <td>
                  <span style={{ fontWeight: 500 }}>{s.name}</span>
                </td>
                <td>
                  <span className="chip">{s.kind}</span>
                </td>
                <td>
                  {s.status === "auth-failed" ? (
                    <span className="chip rose">
                      <span className="dot"></span>auth failed
                    </span>
                  ) : (
                    <span className="chip emerald">
                      <span className="dot"></span>
                      {s.status}
                    </span>
                  )}
                </td>
                <td className="mono">{s.records}</td>
                <td className="mono muted" style={{ fontSize: 11.5 }}>
                  {s.updated}
                </td>
                <td className="mono muted" style={{ fontSize: 11.5 }}>
                  2 pipelines
                </td>
                <td className="row-actions">
                  <Icon name="arrow" size={12} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function _DeprecatedSettingsPage_unused() {
  const tiles = [
    {
      ic: "brain",
      n: "LLM Models",
      d: "Manage available models, configure providers, and view capabilities.",
      meta: ["0 models", "0 providers"],
      badge: <span className="chip cyan">priority</span>,
      cls: "priority",
    },
    {
      ic: "database",
      n: "Data Sources",
      d: "Configure reference APIs and database settings.",
      meta: ["Reference APIs", "Database settings"],
    },
    {
      ic: "zap",
      n: "Processing",
      d: "NLP configuration and pipeline defaults.",
      meta: ["NLP", "Pipeline defaults"],
    },
    {
      ic: "cpu",
      n: "System",
      d: "Server settings, logging, and security.",
      meta: ["Server", "Logging", "Security"],
    },
    {
      ic: "globe",
      n: "Network & Proxy",
      d: "Proxy server and caching configuration.",
      meta: ["Proxy", "Cache"],
    },
    {
      ic: "shield",
      n: "Advanced",
      d: "Raw configuration editor and advanced tools.",
      meta: ["Raw config", "Import/Export", "Reset"],
      badge: <span className="chip rose">expert</span>,
      cls: "expert",
    },
  ];
  return (
    <div className="canvas-inner">
      <PageHeader
        title="Configuration"
        subtitle="Workspace-level settings, providers, and system controls."
        badge={
          <div className="row gap-12">
            <span className="status-line">
              <span className="pulse"></span>
              <span>system healthy</span>
            </span>
          </div>
        }
        actions={
          <button className="btn btn-ghost">
            <Icon name="ext" /> Export config
          </button>
        }
      />

      <div
        className="stat-grid"
        style={{ marginBottom: 22, gridTemplateColumns: "repeat(3, 1fr)" }}
      >
        <StatTile
          label="LLM Models"
          value="0"
          color="cyan"
          meta={<span className="muted">across 0 providers</span>}
        />
        <StatTile
          label="System"
          value="Healthy"
          color="emerald"
          meta={
            <span className="muted mono" style={{ fontSize: 11 }}>
              uptime 14d 6h
            </span>
          }
        />
        <StatTile
          label="Quick actions"
          value="—"
          color="amber"
          meta={<span className="muted">manage settings efficiently</span>}
        />
      </div>

      <div className="config-grid">
        {tiles.map((t) => (
          <div key={t.n} className={"config-tile " + (t.cls || "")}>
            <div className="head">
              <div className="icon">
                <Icon name={t.ic} size={18} />
              </div>
              <div style={{ flex: 1 }}>
                <div className="row gap-12">
                  <span className="title">{t.n}</span>
                  {t.badge}
                </div>
                <div className="desc">{t.d}</div>
              </div>
              <Icon name="ext" size={14} className="muted" />
            </div>
            <div className="meta">
              {t.meta.map((m, i) => (
                <span key={i}>· {m}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LandingPage({ onEnter }) {
  return (
    <div className="landing-shell">
      <div className="landing-nav">
        <div className="row gap-12">
          <div className="brand-mark"></div>
          <div className="brand-name">Context Studio</div>
          <span className="env-pill" style={{ marginLeft: 10 }}>
            <span className="dot"></span>v0.1.0
          </span>
        </div>
        <div className="links">
          <a>Docs</a>
          <a>Pipelines</a>
          <a>Changelog</a>
          <button
            className="btn btn-ghost btn-sm"
            style={{ borderColor: "var(--shell-border-2)", color: "var(--shell-fg-1)" }}
          >
            Sign in
          </button>
          <button
            className="btn btn-sm"
            style={{ background: "var(--accent-cyan)", color: "#0B0F14", fontWeight: 600 }}
            onClick={onEnter}
          >
            Open studio →
          </button>
        </div>
      </div>

      <div className="hero">
        <div>
          <div className="eyebrow">
            <span className="dot"></span>Graph RAG · v0.1.0
          </div>
          <h1>
            Curate the <em>context</em>
            <br />
            your AI actually&nbsp;needs.
          </h1>
          <p className="lede">
            Context Studio is a knowledge graph workbench for retrieval-augmented generation. Define
            a schema, populate it from authoritative sources with configurable Graph RAG pipelines,
            and ground every answer in structured evidence.
          </p>
          <div className="ctas">
            <button className="btn-hero" onClick={onEnter}>
              Open studio <Icon name="arrow" />
            </button>
            <button className="btn-hero-alt">
              <Icon name="doc" /> Read the docs
            </button>
          </div>
          <div
            style={{
              marginTop: 24,
              display: "flex",
              gap: 18,
              fontFamily: "var(--mono)",
              fontSize: 11,
              color: "var(--shell-fg-3)",
            }}
          >
            <span>· 22 classes</span>
            <span>· 267 individuals</span>
            <span>· 11 pipelines</span>
            <span>· 7 reference sources</span>
          </div>
        </div>

        <div className="hero-vis">
          <div className="hero-vis-toolbar">
            <div className="lights">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <span style={{ marginLeft: 8 }}>knowledge_graph_structure.tree</span>
            <span style={{ marginLeft: "auto" }}>● live</span>
          </div>
          <div className="hero-tree">
            <div className="h-node" data-d="life">
              <span className="sw"></span>Life Sciences
            </div>
            <div className="h-desc">Biological and biomedical knowledge organisation</div>
            <div className="h-node" data-d="climate">
              <span className="sw"></span>Climate &amp; Environment
            </div>
            <div className="h-desc">Earth systems, emissions, sustainability</div>
            <div className="h-node" data-d="sw">
              <span className="sw"></span>Software Engineering
            </div>
            <div className="h-desc">Patterns, architectures, practices</div>
            <div className="h-node indent-1" data-d="life">
              <span className="sw"></span>Cell
            </div>
            <div className="h-desc">Basic unit of life</div>
            <div className="h-node indent-1" data-d="life">
              <span className="sw"></span>Gene
            </div>
            <div className="h-desc">DNA sequence encoding a product</div>
            <div className="h-node indent-2" data-d="life">
              <span className="sw"></span>Variant
            </div>
            <div className="h-desc">Genetic variation in a population</div>
            <div className="h-node indent-1" data-d="life">
              <span className="sw"></span>Protein
            </div>
            <div className="h-desc">Functional gene product</div>
            <div className="h-node indent-1" data-d="climate">
              <span className="sw"></span>CO₂
            </div>
            <div className="h-desc">Carbon dioxide</div>
            <div className="h-node indent-1" data-d="climate">
              <span className="sw"></span>Global Warming
            </div>
            <div className="h-desc">Long-term temperature increase</div>
            <div className="h-node indent-2" data-d="climate">
              <span className="sw"></span>Sea Level Rise
            </div>
            <div className="h-desc">Ocean expansion and ice melt</div>
            <div className="h-node indent-1" data-d="sw">
              <span className="sw"></span>Hexagonal Architecture
            </div>
            <div className="h-desc">Ports and adapters pattern</div>
            <div className="h-node indent-1" data-d="sw">
              <span className="sw"></span>Microservices
            </div>
            <div className="h-desc">Service decomposition pattern</div>
          </div>
        </div>
      </div>

      <div className="feature-band">
        <div className="feature-band-inner">
          <h2>One workbench for schema, data, and pipelines.</h2>
          <p className="sub">
            Most retrieval setups blur taxonomy and instances. Context Studio keeps them distinct —
            and connects them through pipelines you can configure, run, and version.
          </p>
          <div className="feature-grid">
            {[
              [
                "schema",
                "Schema",
                "Taxonomies, classes, properties, and relationships — the structural backbone of your knowledge.",
              ],
              [
                "data",
                "Data",
                "Individuals populated from sources, with confidence and provenance attached to every triple.",
              ],
              [
                "pipeline",
                "Pipelines",
                "Composable Graph RAG pipelines populate both the schema and the data, on schedule or on demand.",
              ],
              [
                "reference",
                "External grounding",
                "Plug in PubMed, IPCC, arXiv, internal corpora — every node links back to its source.",
              ],
            ].map(([ic, n, d]) => (
              <div key={n} className="feature">
                <div className="ic">
                  <Icon name={ic} size={16} />
                </div>
                <h3>{n}</h3>
                <p>{d}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="landing-foot">
        <span>Context Studio · workbench for Graph RAG</span>
        <span>v0.1.0 · build 2026.05.02</span>
      </div>
    </div>
  );
}

window.PipelinesPage = PipelinesPage;
window.ReferencePage = ReferencePage;
window.LandingPage = LandingPage;
