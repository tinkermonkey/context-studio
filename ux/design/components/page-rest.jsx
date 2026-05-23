// =========================================================================
// Pipelines page — full cards with flow strips
// =========================================================================
function PipelinesPage({ onNav, route }) {
  if (route === "pipelines/runs")    return <PipelineRunsPage onNav={onNav} />;
  if (route === "pipelines/flavors") return <StubPage route={route} title="Pipeline flavors" subtitle="Pipeline templates — the kinds of source → extract → resolve → write chains the studio supports." />;
  return <PipelinesAllPage onNav={onNav} />;
}
window.PipelinesPage = PipelinesPage;

function PipelinesAllPage({ onNav }) {
  const D = window.CS_DATA;
  const [filter, setFilter] = useState("all");
  const filtered = filter === "all" ? D.pipelines : D.pipelines.filter((p) => p.status === filter);
  const counts = D.pipelines.reduce((a, p) => { a[p.status] = (a[p.status] || 0) + 1; return a; }, {});

  return (
    <div className="canvas-inner" data-screen-label="09 Pipelines">
      <div className="page-head">
        <div>
          <div className="page-head-meta">
            <span className="chip amber"><span className="dot"></span>pipelines</span>
            <span className="id-tag">{D.pipelines.length} pipelines</span>
            <span className="muted mono" style={{fontSize: 11}}>
              {counts.running || 0} running · {counts.idle || 0} idle · {counts.success || 0} ok · {counts.failed || 0} failed
            </span>
          </div>
          <h1>Pipelines <span className="id-tag">/pipelines/all</span></h1>
          <div className="subtitle">
            A pipeline is a source → extract → resolve → write chain. Each run materializes individuals (or schema)
            from a reference source. Runs are append-only — partial writes are kept on failure.
          </div>
        </div>
        <div className="page-actions">
          <button className="btn"><Icon name="refresh" size={13} /> Refresh</button>
          <button className="btn btn-primary"><Icon name="plus" size={13} /> New pipeline</button>
        </div>
      </div>

      <div className="filter-bar">
        <div className="seg">
          {[["all","All"],["running","Running"],["success","Success"],["idle","Idle"],["failed","Failed"]].map(([v, l]) => (
            <button key={v} className={"seg-btn" + (filter === v ? " active" : "")} onClick={() => setFilter(v)}>
              {l} {v !== "all" && <span className="mono muted" style={{marginLeft: 4}}>{counts[v] || 0}</span>}
            </button>
          ))}
        </div>
        <div className="search-input-wrap">
          <Icon name="search" size={13}/>
          <input className="input with-icon" placeholder="Filter by name, target, or step…" />
        </div>
        <span className="muted mono" style={{fontSize: 11, marginLeft: "auto"}}>showing {filtered.length} of {D.pipelines.length}</span>
      </div>

      <div className="stack">
        {filtered.map((p) => <PipelineCard key={p.id} pipeline={p} />)}
      </div>
    </div>
  );
}
window.PipelinesAllPage = PipelinesAllPage;

function PipelineRunsPage({ onNav }) {
  const D = window.CS_DATA;
  // mock run history derived from pipelines
  const runs = [
    { id: "run_4b921", pipeline: "pl_pubmed_genes", name: "pubmed_genes", status: "running", started: "12m ago", duration: "—",        records: "—",   trigger: "scheduled" },
    { id: "run_4b920", pipeline: "pl_uniprot",      name: "uniprot_proteins", status: "success", started: "1h ago", duration: "2m 22s", records: "+8",   trigger: "scheduled" },
    { id: "run_4b919", pipeline: "pl_eia_solar",    name: "eia_renewables", status: "failed",  started: "3h ago",  duration: "0:48",   records: "—",   trigger: "manual" },
    { id: "run_4b918", pipeline: "pl_ipcc_climate", name: "ipcc_ar6", status: "success", started: "1d ago",  duration: "5m 12s", records: "+28",  trigger: "manual" },
    { id: "run_4b917", pipeline: "pl_wikipedia",    name: "wikipedia_links", status: "success", started: "1d ago", duration: "3m 40s", records: "~84",  trigger: "scheduled" },
    { id: "run_4b916", pipeline: "pl_arxiv_se",     name: "arxiv_cs_se", status: "success", started: "2d ago",  duration: "1m 36s", records: "+4",   trigger: "scheduled" },
    { id: "run_4b915", pipeline: "pl_pubmed_genes", name: "pubmed_genes", status: "success", started: "1w ago",  duration: "3m 04s", records: "+412", trigger: "scheduled" },
  ];
  const statusChip = (s) => ({
    running: <span className="chip cyan"><span className="dot" style={{animation: "pulse-out 1.6s infinite"}}></span>running</span>,
    success: <span className="chip emerald"><span className="dot"></span>success</span>,
    failed:  <span className="chip rose"><span className="dot"></span>failed</span>,
    idle:    <span className="chip gray"><span className="dot"></span>idle</span>,
  })[s];
  return (
    <div className="canvas-inner" data-screen-label="10 Pipelines · Runs">
      <div className="page-head">
        <div>
          <div className="page-head-meta">
            <span className="chip amber"><span className="dot"></span>pipelines</span>
            <span className="id-tag">run_history</span>
          </div>
          <h1>Run history <span className="id-tag">/pipelines/runs</span></h1>
          <div className="subtitle">All runs across all pipelines. Append-only — older runs are archived to <span className="mono">.context-studio/runs/</span>.</div>
        </div>
        <div className="page-actions">
          <button className="btn"><Icon name="filter" size={13} /> Filter</button>
        </div>
      </div>

      <div className="panel">
        <table className="tbl">
          <thead><tr>
            <th>Run id</th>
            <th>Pipeline</th>
            <th style={{width: 130}}>Status</th>
            <th style={{width: 120}}>Started</th>
            <th style={{width: 110, textAlign: "right"}}>Duration</th>
            <th style={{width: 110, textAlign: "right"}}>Records</th>
            <th style={{width: 110}}>Trigger</th>
            <th style={{width: 60}}></th>
          </tr></thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id}>
                <td className="mono"><span className="row-link">{r.id}</span></td>
                <td className="mono">{r.name}</td>
                <td>{statusChip(r.status)}</td>
                <td className="mono muted" style={{fontSize: 11.5}}>{r.started}</td>
                <td className="num">{r.duration}</td>
                <td className="num">{r.records}</td>
                <td><span className="chip mono">{r.trigger}</span></td>
                <td style={{textAlign:"right"}}>
                  <button className="btn btn-ghost btn-icon"><Icon name="more" size={12}/></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// =========================================================================
// External Reference page — source list + grounding workflows
// =========================================================================
function ReferencePage({ route, onNav }) {
  if (route === "reference/grounding") return <StubPage route={route} title="Grounding workflows" subtitle="Multi-step pipelines that combine a reference source with extraction and resolution to ground a class or individual in real-world data." />;
  return <ReferenceSourcesPage onNav={onNav} />;
}
window.ReferencePage = ReferencePage;

function ReferenceSourcesPage({ onNav }) {
  const D = window.CS_DATA;
  const statusChip = (s) => ({
    ok:    <span className="chip emerald"><span className="dot"></span>ok</span>,
    fail:  <span className="chip rose"><span className="dot"></span>fail</span>,
    idle:  <span className="chip gray"><span className="dot"></span>idle</span>,
  })[s];
  const kindIcon = (k) => k === "api" ? "globe" : k === "corpus" ? "doc" : "database";
  return (
    <div className="canvas-inner" data-screen-label="11 External Reference · Sources">
      <div className="page-head">
        <div>
          <div className="page-head-meta">
            <span className="chip cyan"><span className="dot"></span>reference</span>
            <span className="id-tag">{D.reference_sources.length} sources</span>
          </div>
          <h1>Reference sources <span className="id-tag">/reference/sources</span></h1>
          <div className="subtitle">External APIs, datasets, and document corpora that pipelines pull from. Each source can power one or more pipelines.</div>
        </div>
        <div className="page-actions">
          <button className="btn"><Icon name="refresh" size={13} /> Health check</button>
          <button className="btn btn-primary"><Icon name="plus" size={13} /> Add source</button>
        </div>
      </div>

      <div className="split-3-1">
        <div className="panel">
          <table className="tbl">
            <thead><tr>
              <th style={{width: 36}}></th>
              <th>Identifier</th>
              <th>Name</th>
              <th>URL</th>
              <th style={{width: 90}}>Kind</th>
              <th style={{width: 90, textAlign: "right"}}>Pipelines</th>
              <th style={{width: 100}}>Status</th>
              <th style={{width: 110}}>Last sync</th>
              <th style={{width: 60}}></th>
            </tr></thead>
            <tbody>
              {D.reference_sources.map((s) => (
                <tr key={s.id}>
                  <td><Icon name={kindIcon(s.kind)} size={14} className="muted"/></td>
                  <td className="mono">{s.id}</td>
                  <td><span className="row-link" style={{fontWeight: 600}}>{s.name}</span></td>
                  <td className="mono muted" style={{fontSize: 11.5}}>{s.url}</td>
                  <td><span className="chip mono">{s.kind}</span></td>
                  <td className="num">{s.pipelines}</td>
                  <td>{statusChip(s.status)}</td>
                  <td className="mono muted" style={{fontSize: 11.5}}>{s.last}</td>
                  <td style={{textAlign:"right"}}>
                    <button className="btn btn-ghost btn-icon"><Icon name="more" size={12}/></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Grounding workflows summary */}
        <div className="stack">
          <div className="panel">
            <div className="panel-head"><div className="panel-title"><Icon name="link" size={14}/>Grounding</div></div>
            <div className="panel-body" style={{display: "flex", flexDirection: "column", gap: 10, fontSize: 12.5}}>
              <div>External references resolve canonical identifiers for classes and individuals.</div>
              <div className="stat-grid" style={{gridTemplateColumns: "1fr 1fr", gap: 10}}>
                <div className="stat" data-color="cyan" style={{padding: "10px 12px", minHeight: 0}}>
                  <div className="label">REFS</div>
                  <div className="num" style={{fontSize: 20}}>184</div>
                </div>
                <div className="stat" data-color="violet" style={{padding: "10px 12px", minHeight: 0}}>
                  <div className="label">UNRESOLVED</div>
                  <div className="num" style={{fontSize: 20}}>9</div>
                </div>
              </div>
            </div>
          </div>
          <div className="panel">
            <div className="panel-head"><div className="panel-title"><Icon name="globe" size={14}/>Health</div></div>
            <div className="panel-body" style={{display: "flex", flexDirection: "column", gap: 10, fontSize: 12.5}}>
              <div className="row between">
                <span className="muted mono" style={{fontSize: 11}}>up</span>
                <span style={{fontFamily:"var(--font-mono)"}}>5 / 7</span>
              </div>
              <div className="row between">
                <span className="muted mono" style={{fontSize: 11}}>rate-limited</span>
                <span style={{fontFamily:"var(--font-mono)"}}>1</span>
              </div>
              <div className="row between">
                <span className="muted mono" style={{fontSize: 11}}>failing</span>
                <span style={{fontFamily:"var(--font-mono)", color:"#FDA4AF"}}>1</span>
              </div>
              <div className="row between">
                <span className="muted mono" style={{fontSize: 11}}>last 24h calls</span>
                <span style={{fontFamily:"var(--font-mono)"}}>14,322</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// =========================================================================
// CheckboxDropdown — used in the graph filter bar
// =========================================================================
function CheckboxDropdown({ label, summary, children, width }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);
  return (
    <div className="dd" ref={ref}>
      <button className={"fd-trigger" + (open ? " open" : "")} onClick={() => setOpen((v) => !v)}>
        <span className="fd-eyebrow">{label}</span>
        <span className="fd-value">{summary}</span>
        <Icon name={open ? "chev-up" : "chevDown"} size={11} className="fd-chev" />
      </button>
      {open && <div className="fd-panel" style={width ? {minWidth: width} : null}>{children}</div>}
    </div>
  );
}

// =========================================================================
// Graph view — schematic SVG of the knowledge graph
// =========================================================================
function GraphViewPage({ onNav }) {
  const D = window.CS_DATA;
  // Build a layout: 3 columns by domain, classes only
  const cols = { life: [], climate: [], software: [] };
  D.classes.forEach((c) => cols[c.domain]?.push(c));

  const HCENTER = [320, 720, 1120];
  const TOP = 110;
  const ROWH = 70;

  const [domains, setDomains]   = useState({ life: true, climate: true, software: true });
  const [showOpts, setShowOpts] = useState({ classes: true, individuals: false, edges: true, edge_labels: false });
  const [layout, setLayout]     = useState("columns");

  // Place nodes (only enabled domains)
  const nodes = {};
  ["life", "climate", "software"].forEach((dom, ci) => {
    if (!domains[dom]) return;
    cols[dom].forEach((c, i) => {
      nodes[c.id] = { x: HCENTER[ci], y: TOP + i * ROWH, cls: c };
    });
  });

  const domainColor = { life: "#10B981", climate: "#FBBF24", software: "#818CF8", default: "#94A3B8" };
  const [selectedNode, setSelectedNode] = useState("cls_gene");

  const edges = showOpts.edges ? D.relationships
    .filter((r) => nodes[r.source_id] && nodes[r.target_id])
    .map((r) => {
      const s = nodes[r.source_id], t = nodes[r.target_id];
      const prop = D.property_definitions.find((p) => p.id === r.property_definition_id);
      return { ...r, x1: s.x, y1: s.y, x2: t.x, y2: t.y, label: prop?.identifier };
    }) : [];

  const selected = D.classes.find((c) => c.id === selectedNode);

  const domainSummary = (() => {
    const on = Object.entries(domains).filter(([_, v]) => v).map(([k]) => k);
    if (on.length === 3) return "all 3";
    if (on.length === 0) return "none";
    return on.join(" · ");
  })();
  const showSummary = (() => {
    const on = Object.entries(showOpts).filter(([_, v]) => v).length;
    return on + " of 4";
  })();
  const layoutLabels = { columns: "columns by domain", force: "force-directed", tree: "tree (hierarchical)" };

  return (
    <div className="canvas-inner" data-screen-label="12 Graph view" style={{paddingBottom: 16}}>
      <div className="page-head">
        <div>
          <div className="page-head-meta">
            <span className="chip violet"><span className="dot"></span>graph</span>
            <span className="muted mono" style={{fontSize:11}}>{D.classes.length} nodes · {D.relationships.length} edges · 3 domains</span>
          </div>
          <h1>Graph view <span className="id-tag">/graph</span></h1>
          <div className="subtitle">Force-directed layout of classes (large nodes) and individuals (small nodes). Edges are typed relationships. Drag to reposition, scroll to zoom.</div>
        </div>
        <div className="page-actions">
          <button className="btn"><Icon name="refresh" size={13}/> Re-layout</button>
          <button className="btn btn-primary"><Icon name="ext" size={13}/> Export PNG</button>
        </div>
      </div>

      {/* ---- Top filter bar ---- */}
      <div className="graph-filter-bar">
        <CheckboxDropdown label="Domain" summary={domainSummary}>
          <div className="fd-section">Domains</div>
          {[["life","Life"],["climate","Climate"],["software","Software"]].map(([k, l]) => (
            <div key={k} className="fd-row" onClick={() => setDomains((d) => ({ ...d, [k]: !d[k] }))}>
              <span className={"fd-checkbox" + (domains[k] ? " on" : "")}>
                {domains[k] && <Icon name="check" size={10} />}
              </span>
              <span className="kg-node-pill sm" data-domain={k}><span className="swatch"></span>{l}</span>
              <span className="fd-meta">{cols[k].length}</span>
            </div>
          ))}
        </CheckboxDropdown>

        <CheckboxDropdown label="Show" summary={showSummary}>
          <div className="fd-section">Nodes</div>
          {[["classes","Classes"],["individuals","Individuals"]].map(([k, l]) => (
            <div key={k} className="fd-row" onClick={() => setShowOpts((o) => ({ ...o, [k]: !o[k] }))}>
              <span className={"fd-checkbox" + (showOpts[k] ? " on" : "")}>
                {showOpts[k] && <Icon name="check" size={10} />}
              </span>
              {l}
            </div>
          ))}
          <div className="fd-section">Edges</div>
          {[["edges","Edges"],["edge_labels","Edge labels"]].map(([k, l]) => (
            <div key={k} className="fd-row" onClick={() => setShowOpts((o) => ({ ...o, [k]: !o[k] }))}>
              <span className={"fd-checkbox" + (showOpts[k] ? " on" : "")}>
                {showOpts[k] && <Icon name="check" size={10} />}
              </span>
              {l}
            </div>
          ))}
        </CheckboxDropdown>

        <CheckboxDropdown label="Layout" summary={layoutLabels[layout]}>
          {Object.entries(layoutLabels).map(([k, l]) => (
            <div key={k} className="fd-row" onClick={() => setLayout(k)}>
              <span className={"fd-radio" + (layout === k ? " on" : "")}></span>
              {l}
            </div>
          ))}
        </CheckboxDropdown>

        <span style={{flex: 1}}></span>
        <span className="muted mono" style={{fontSize: 11}}>
          {Object.keys(nodes).length} nodes · {edges.length} edges visible
        </span>
      </div>

      <div className="graph-shell">
        {/* Canvas */}
        <div className="graph-canvas">
          <div className="grid"></div>

          <div className="graph-toolbar">
            <button title="Pan" className="active"><Icon name="expand" size={13}/></button>
            <button title="Zoom in"><Icon name="plus" size={13}/></button>
            <button title="Zoom out"><Icon name="x" size={13}/></button>
            <button title="Fit"><Icon name="dashboard" size={13}/></button>
          </div>

          <svg viewBox="0 0 1440 740" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
            <defs>
              <marker id="arrowend" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#475569" />
              </marker>
            </defs>

            {/* Edges */}
            {edges.map((e) => {
              const mx = (e.x1 + e.x2) / 2;
              const my = (e.y1 + e.y2) / 2;
              return (
                <g key={e.id}>
                  <line x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2}
                    stroke="#475569" strokeWidth="1.2" strokeDasharray={e.source === "manual" ? "" : "3 3"}
                    markerEnd="url(#arrowend)" opacity="0.7"/>
                  {showOpts.edge_labels && (
                    <g>
                      <rect x={mx - 38} y={my - 9} width="76" height="16" rx="3"
                        fill="#0B1426" stroke="#2A3A5C" strokeWidth="0.75" />
                      <text x={mx} y={my + 3} fill="#94A3B8" fontFamily="JetBrains Mono" fontSize="9.5" textAnchor="middle">
                        {e.label}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}

            {/* Domain column headers */}
            {["life","climate","software"].filter((d) => domains[d]).map((dom) => {
              const i = ["life","climate","software"].indexOf(dom);
              return (
                <g key={dom}>
                  <text x={HCENTER[i]} y={48} fill="#94A3B8" fontFamily="JetBrains Mono" fontSize="11" textAnchor="middle" letterSpacing="2.2">
                    {dom.toUpperCase()}
                  </text>
                  <line x1={HCENTER[i] - 80} y1={62} x2={HCENTER[i] + 80} y2={62}
                    stroke={domainColor[dom]} strokeWidth="2" opacity="0.55"/>
                  <text x={HCENTER[i]} y={80} fill="#6F7E94" fontFamily="JetBrains Mono" fontSize="10" textAnchor="middle">
                    {cols[dom].length} classes
                  </text>
                </g>
              );
            })}

            {/* Nodes */}
            {Object.values(nodes).map(({ x, y, cls }) => {
              const sel = cls.id === selectedNode;
              const color = domainColor[cls.domain] || domainColor.default;
              return (
                <g key={cls.id} onClick={() => setSelectedNode(cls.id)} style={{cursor: "pointer"}}>
                  <rect x={x - 110} y={y - 18} width={220} height={36} rx="6"
                    fill={sel ? "rgba(251,191,36,0.10)" : "#131F39"}
                    stroke={sel ? "#FBBF24" : "#2A3A5C"} strokeWidth={sel ? "1.5" : "1"} />
                  <rect x={x - 110} y={y - 18} width="3" height={36} fill={color} />
                  <text x={x - 100} y={y + 4} fill={sel ? "#FCD34D" : "#E6EDF6"} fontFamily="JetBrains Mono" fontSize="12" fontWeight="500">
                    {cls.title.length > 22 ? cls.title.slice(0, 20) + "…" : cls.title}
                  </text>
                  <text x={x + 100} y={y + 4} fill="#6F7E94" fontFamily="JetBrains Mono" fontSize="10.5" textAnchor="end">
                    {cls.individuals}
                  </text>
                </g>
              );
            })}
          </svg>

          <div className="graph-legend">
            <div className="lg-row"><span className="sw" style={{background:"#10B981"}}></span>life</div>
            <div className="lg-row"><span className="sw" style={{background:"#FBBF24"}}></span>climate</div>
            <div className="lg-row"><span className="sw" style={{background:"#818CF8"}}></span>software</div>
            <div className="lg-row" style={{marginTop: 4, paddingTop: 4, borderTop: "1px solid var(--canvas-border)"}}>
              <svg width="22" height="6"><line x1="0" y1="3" x2="22" y2="3" stroke="#475569" strokeWidth="1.5"/></svg>
              manual
            </div>
            <div className="lg-row">
              <svg width="22" height="6"><line x1="0" y1="3" x2="22" y2="3" stroke="#475569" strokeWidth="1.5" strokeDasharray="3 3"/></svg>
              inferred
            </div>
          </div>

          <div className="graph-mini">
            <svg viewBox="0 0 168 96" width="168" height="96">
              <rect width="168" height="96" fill="rgba(11,20,38,0.4)" />
              {Object.values(nodes).map(({x, y, cls}) => (
                <circle key={cls.id} cx={(x/1440) * 168} cy={(y/740) * 96} r="2"
                  fill={domainColor[cls.domain] || domainColor.default} />
              ))}
              <rect x="40" y="20" width="80" height="50" stroke="#FBBF24" fill="rgba(251,191,36,0.05)" strokeWidth="1" />
            </svg>
          </div>
        </div>

        {/* Right rail — selected node detail */}
        <div className="panel" style={{minHeight: 0, overflow: "auto"}}>
          <div className="panel-head">
            <div className="panel-title">
              <span className="kg-node-pill sm" data-domain={selected?.domain}><span className="swatch"></span></span>
              Selection
            </div>
          </div>
          {selected && (
            <div>
              <div className="kv">
                <div className="k">Title</div>
                <div className="v" style={{fontWeight: 600}}>{selected.title}</div>
                <div className="k">Identifier</div>
                <div className="v mono">{selected.id}</div>
                <div className="k">Domain</div>
                <div className="v"><span className="kg-node-pill sm" data-domain={selected.domain}><span className="swatch"></span>{selected.domain}</span></div>
                <div className="k">Individuals</div>
                <div className="v mono">{selected.individuals}</div>
                <div className="k">Version</div>
                <div className="v"><span className="version-pill">v{selected.version}</span></div>
              </div>
              <div className="panel-body">
                <div style={{fontSize: 12.5, color: "var(--canvas-fg-2)", lineHeight: 1.55, marginBottom: 10}}>{selected.description}</div>
                <button className="btn btn-ghost btn-sm" onClick={() => onNav("schema/classes")}>
                  <Icon name="ext" size={12}/> Open in Schema
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
window.GraphViewPage = GraphViewPage;

// =========================================================================
// Configuration page — tile grid with sub-sections + form panel
// =========================================================================
function SettingsPage() {
  const [active, setActive] = useState("general");
  const tabs = [
    { id: "general",      label: "General",      count: 6 },
    { id: "pipelines",    label: "Pipelines",    count: 4 },
    { id: "storage",      label: "Storage",      count: 3 },
    { id: "members",      label: "Members",      count: 3 },
    { id: "integrations", label: "Integrations", count: 5 },
  ];
  return (
    <div className="canvas-inner" data-screen-label="13 Configuration">
      <div className="page-head">
        <div>
          <div className="page-head-meta">
            <span className="chip gray"><span className="dot"></span>settings</span>
            <span className="id-tag">/workspace/{window.CS_DATA.workspace.name}/.context-studio</span>
          </div>
          <h1>Configuration <span className="id-tag">/settings</span></h1>
          <div className="subtitle">Workspace-level configuration. Changes are written to <span className="mono">.context-studio/config.yaml</span> and synced on next push.</div>
        </div>
        <div className="page-actions">
          <button className="btn"><Icon name="refresh" size={13} /> Reload</button>
        </div>
      </div>

      <div className="tabs">
        {tabs.map((t) => (
          <button key={t.id} className={"tab" + (active === t.id ? " active" : "")} onClick={() => setActive(t.id)}>
            {t.label} <span className="count">{t.count}</span>
          </button>
        ))}
      </div>

      {active === "general" && <GeneralSettings />}
      {active === "pipelines" && <PipelinesSettings />}
      {active === "storage" && <StorageSettings />}
      {active === "members" && <MembersSettings />}
      {active === "integrations" && <IntegrationsSettings />}
    </div>
  );
}
window.SettingsPage = SettingsPage;

function GeneralSettings() {
  const D = window.CS_DATA;
  return (
    <div className="split-3-1" style={{alignItems: "start"}}>
      <div className="panel">
        <div className="panel-head"><div className="panel-title">Workspace</div></div>
        <div className="panel-body" style={{display: "grid", gap: 16}}>
          <div className="field">
            <div className="lab">Name<span className="hint-r">snake_case</span></div>
            <input className="input mono" defaultValue={D.workspace.name} />
            <div className="hint">The canonical workspace identifier. Used in URLs, exports, and the daemon API.</div>
          </div>
          <div className="field">
            <div className="lab">Local path<span className="hint-r">absolute or ~/</span></div>
            <input className="input mono" defaultValue={D.workspace.path} />
            <div className="hint">Source of truth for schema, data, and pipeline definitions.</div>
          </div>
          <div className="field">
            <div className="lab">Default branch</div>
            <input className="input mono" defaultValue={D.workspace.branch} />
          </div>
          <div className="field">
            <div className="lab">Graph daemon</div>
            <div className="row gap-12">
              <input className="input mono" defaultValue="http://localhost:7474" style={{flex: 1}} />
              <button className="btn btn-sm"><Icon name="refresh" size={11}/> Test</button>
            </div>
            <div className="hint">Where the local graph process listens. Restart required if changed.</div>
          </div>
        </div>
        <div className="modal-foot" style={{borderTop:"1px solid var(--canvas-border)"}}>
          <span className="modal-foot-hint">PUT /workspace/{D.workspace.name}/config</span>
          <button className="btn btn-ghost">Discard</button>
          <button className="btn btn-primary">Save changes</button>
        </div>
      </div>

      <div className="stack">
        <div className="config-tile">
          <div className="ic"><Icon name="shield" size={18}/></div>
          <div style={{flex: 1, minWidth: 0}}>
            <div className="t">Backups</div>
            <div className="d">Automatic snapshots are stored alongside the workspace.</div>
            <div className="kv-mini"><span><b>last</b> 4h ago</span><span><b>retain</b> 7d</span></div>
          </div>
        </div>
        <div className="config-tile">
          <div className="ic"><Icon name="cpu" size={18}/></div>
          <div style={{flex: 1, minWidth: 0}}>
            <div className="t">Performance</div>
            <div className="d">Daemon process limits and worker pool.</div>
            <div className="kv-mini"><span><b>workers</b> 4</span><span><b>mem cap</b> 2 GB</span></div>
          </div>
        </div>
        <div className="config-tile">
          <div className="ic"><Icon name="zap" size={18}/></div>
          <div style={{flex: 1, minWidth: 0}}>
            <div className="t">Telemetry</div>
            <div className="d">Anonymous usage helps prioritize features.</div>
            <div className="kv-mini"><span><b>status</b> off</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PipelinesSettings() {
  return (
    <div className="config-grid">
      {[
        ["pipeline","Default flavor","claude-haiku · embeddings · neo4j-write","Used for new pipelines unless overridden."],
        ["sparkle","Model providers","openai · anthropic · local-llama","Order = priority on rate-limit fallback."],
        ["history","Run retention","last 50 per pipeline","Older runs are archived to disk."],
        ["bell","Notifications","desktop · failures only","Email and webhook options below."],
      ].map(([ic, t, v, d]) => (
        <div key={t} className="config-tile">
          <div className="ic"><Icon name={ic} size={18}/></div>
          <div style={{flex: 1, minWidth: 0}}>
            <div className="t">{t}</div>
            <div className="d">{d}</div>
            <div className="kv-mini"><span>{v}</span></div>
          </div>
          <button className="btn btn-ghost btn-icon"><Icon name="chevRight" size={12}/></button>
        </div>
      ))}
    </div>
  );
}

function StorageSettings() {
  return (
    <div className="config-grid">
      {[
        ["database","Graph store","neo4j-embedded · 1.2 GB","Local Neo4j running at :7474."],
        ["layers","Object store","local filesystem","Datasets, run logs, large blobs."],
        ["data","Embeddings cache","sqlite · 224 MB","Reused across pipelines for resolve steps."],
      ].map(([ic, t, v, d]) => (
        <div key={t} className="config-tile">
          <div className="ic"><Icon name={ic} size={18}/></div>
          <div style={{flex: 1, minWidth: 0}}>
            <div className="t">{t}</div>
            <div className="d">{d}</div>
            <div className="kv-mini"><span>{v}</span></div>
          </div>
        </div>
      ))}
    </div>
  );
}

function MembersSettings() {
  const members = [
    { who: "maya@studio",   role: "owner",   last: "now"        },
    { who: "ben@studio",    role: "curator", last: "3h ago"     },
    { who: "agent@studio",  role: "service", last: "12m ago"    },
  ];
  return (
    <div className="panel">
      <table className="tbl">
        <thead><tr><th>Member</th><th>Role</th><th>Last active</th><th style={{width: 60}}></th></tr></thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.who}>
              <td className="mono">{m.who}</td>
              <td><span className="chip mono">{m.role}</span></td>
              <td className="mono muted">{m.last}</td>
              <td style={{textAlign:"right"}}><button className="btn btn-ghost btn-icon"><Icon name="more" size={12}/></button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IntegrationsSettings() {
  return (
    <div className="config-grid">
      {[
        ["bot","claude-haiku","extract / resolve","connected · key on file"],
        ["sparkle","gpt-4o-mini","NER","connected"],
        ["database","neo4j","graph daemon","local · :7474"],
        ["branch","github","sync workspace","linked to molgraph-research"],
        ["globe","wikidata","grounding","public · no auth"],
      ].map(([ic, t, d, v]) => (
        <div key={t} className="config-tile">
          <div className="ic"><Icon name={ic} size={18}/></div>
          <div style={{flex: 1, minWidth: 0}}>
            <div className="t">{t}</div>
            <div className="d">{d}</div>
            <div className="kv-mini"><span>{v}</span></div>
          </div>
          <button className="btn btn-ghost btn-sm">Manage</button>
        </div>
      ))}
    </div>
  );
}

// =========================================================================
// Stub page — for routes without dedicated content yet
// =========================================================================
function StubPage({ route, title, subtitle }) {
  const labels = ROUTE_LABELS[route] || [route];
  return (
    <div className="canvas-inner" data-screen-label={"99 " + (title || labels.join(" / "))}>
      <div className="page-head">
        <div>
          <h1>{title || labels.join(" / ")}</h1>
          <div className="subtitle">{subtitle || "This surface is wired in the prototype but doesn't have a richer mock yet — open the production app."}</div>
        </div>
      </div>
      <div className="panel">
        <div className="empty" style={{padding: 60}}>
          <div className="ic"><Icon name="layers" size={20}/></div>
          <div className="t">No content yet</div>
          <div className="d">This page exists in the navigation. The detail view ships in the production studio.</div>
        </div>
      </div>
    </div>
  );
}
window.StubPage = StubPage;
