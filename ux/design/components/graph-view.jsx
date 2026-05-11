// Schema Graph View — a node-link visualization of typed relationships
// between classes and individuals. Deterministic clustered layout.

const GRAPH_LAYOUT = {
  // Life sciences cluster (left half)
  cls_cell: { x: 230, y: 250, cluster: "life" },
  cls_nucleus: { x: 90, y: 110, cluster: "life" },
  cls_mito: { x: 380, y: 95, cluster: "life" },
  cls_membrane: { x: 85, y: 380, cluster: "life" },
  cls_stem: { x: 240, y: 410, cluster: "life" },
  cls_neuron: { x: 380, y: 380, cluster: "life" },
  cls_gene: { x: 560, y: 170, cluster: "life" },
  cls_variant: { x: 700, y: 100, cluster: "life" },
  cls_protein: { x: 560, y: 320, cluster: "life" },
  cls_pathway: { x: 720, y: 460, cluster: "life" },
  ind_brca1: { x: 380, y: 575, cluster: "life" },
  ind_tp53: { x: 540, y: 605, cluster: "life" },
  ind_egfr: { x: 250, y: 580, cluster: "life" },
  ind_p53: { x: 580, y: 470, cluster: "life" },
  ind_apop: { x: 760, y: 600, cluster: "life" },
  // Climate cluster (right half)
  cls_co2: { x: 1100, y: 215, cluster: "climate" },
  cls_methane: { x: 1240, y: 105, cluster: "climate" },
  cls_warming: { x: 920, y: 365, cluster: "climate" },
  cls_sealevel: { x: 1130, y: 405, cluster: "climate" },
  cls_deforest: { x: 920, y: 165, cluster: "climate" },
  cls_renew: { x: 1255, y: 535, cluster: "climate" },
  ind_co2_atm: { x: 1115, y: 600, cluster: "climate" },
  ind_amazon: { x: 920, y: 555, cluster: "climate" },
  ind_solar_us: { x: 1255, y: 660, cluster: "climate" },
  // Software cluster (bottom strip — currently no relationships, hidden by default)
  cls_hex: { x: 200, y: 760, cluster: "software" },
  cls_ddd: { x: 380, y: 760, cluster: "software" },
  cls_micro: { x: 560, y: 760, cluster: "software" },
  cls_unit: { x: 740, y: 760, cluster: "software" },
  ind_hex_alistair: { x: 200, y: 850, cluster: "software" },
  ind_evans_ddd: { x: 380, y: 850, cluster: "software" },
};

const CLUSTER_META = {
  life: { title: "Life Sciences", domain: "life", bbox: { x: 10, y: 40, w: 800, h: 640 } },
  climate: {
    title: "Climate & Environment",
    domain: "climate",
    bbox: { x: 850, y: 40, w: 460, h: 640 },
  },
};

// Node dimensions (must match rendered HTML — used for edge endpoint math)
const NODE_W = 138;
const NODE_W_LONG = 168;
const NODE_H = 30;

function nodeWidth(title) {
  if (!title) return NODE_W;
  // Rough char-based width for routing — matches actual rendered widths well enough
  const len = title.length;
  if (len <= 8) return 110;
  if (len <= 14) return NODE_W;
  return NODE_W_LONG;
}

// Compute connection point on the rectangle perimeter facing target
function rectEdgePoint(cx, cy, w, h, tx, ty) {
  const dx = tx - cx;
  const dy = ty - cy;
  if (dx === 0 && dy === 0) return { x: cx, y: cy };
  const adx = Math.abs(dx);
  const ady = Math.abs(dy);
  const hw = w / 2;
  const hh = h / 2;
  // Determine which edge it leaves through
  if (adx * hh > ady * hw) {
    // Leaves through left/right edge
    const sign = dx > 0 ? 1 : -1;
    return { x: cx + sign * hw, y: cy + (dy * hw) / adx };
  } else {
    const sign = dy > 0 ? 1 : -1;
    return { x: cx + (dx * hh) / ady, y: cy + sign * hh };
  }
}

function bezierPath(p1, p2, curvature = 0.28) {
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const dist = Math.hypot(dx, dy);
  // Normal vector for offset (perpendicular)
  const nx = -dy / (dist || 1);
  const ny = dx / (dist || 1);
  const offset = Math.min(80, dist * curvature);
  const mx = (p1.x + p2.x) / 2 + nx * offset;
  const my = (p1.y + p2.y) / 2 + ny * offset;
  return {
    d: `M ${p1.x} ${p1.y} Q ${mx} ${my} ${p2.x} ${p2.y}`,
    mid: { x: (p1.x + 2 * mx + p2.x) / 4, y: (p1.y + 2 * my + p2.y) / 4 },
    angle: Math.atan2(p2.y - my, p2.x - mx),
  };
}

function GraphView({ onCloseGraph }) {
  const { state } = useStore();
  const [selectedId, setSelectedId] = useState("cls_cell");
  const [hoverEdgeId, setHoverEdgeId] = useState(null);
  const [hiddenPreds, setHiddenPreds] = useState({});
  const [hiddenClusters, setHiddenClusters] = useState({ software: true });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [showLabels, setShowLabels] = useState(true);
  const [showIndividuals, setShowIndividuals] = useState(true);
  const dragRef = useRef(null);
  const canvasRef = useRef(null);
  const didInitFit = useRef(false);

  const STAGE_W = 1340;
  const STAGE_H = 700;

  const fitToCanvas = useCallback(() => {
    const el = canvasRef.current;
    if (!el) return;
    const w = el.clientWidth;
    const h = el.clientHeight;
    if (!w || !h) return;
    const z = Math.min(w / STAGE_W, h / STAGE_H, 1);
    setZoom(z);
    setPan({ x: (w - STAGE_W * z) / 2, y: (h - STAGE_H * z) / 2 });
  }, []);

  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      if (!didInitFit.current) {
        fitToCanvas();
        didInitFit.current = true;
      }
    });
    ro.observe(el);
    fitToCanvas();
    return () => ro.disconnect();
  }, [fitToCanvas]);

  // Look up node (class or individual)
  const lookupNode = useCallback(
    (id) => {
      const c = state.classes.find((x) => x.id === id);
      if (c) return { ...c, kind: "class" };
      const i = state.individuals.find((x) => x.id === id);
      if (i) {
        const cc = state.classes.find((x) => x.id === i.class_ids[0]);
        return { ...i, kind: "individual", domain: cc?.domain || "default" };
      }
      return null;
    },
    [state],
  );

  // Visible edges (after filters)
  const edges = state.relationships.filter((r) => {
    if (hiddenPreds[r.property_definition_id]) return false;
    const s = lookupNode(r.source_id);
    const t = lookupNode(r.target_id);
    if (!s || !t) return false;
    if (!showIndividuals && (s.kind === "individual" || t.kind === "individual")) return false;
    if (hiddenClusters[GRAPH_LAYOUT[r.source_id]?.cluster]) return false;
    if (hiddenClusters[GRAPH_LAYOUT[r.target_id]?.cluster]) return false;
    return true;
  });

  // Build node list: anything in GRAPH_LAYOUT, filtered by toggles
  const nodes = Object.keys(GRAPH_LAYOUT)
    .map(lookupNode)
    .filter(Boolean)
    .filter((n) => {
      if (!showIndividuals && n.kind === "individual") return false;
      if (hiddenClusters[GRAPH_LAYOUT[n.id]?.cluster]) return false;
      return true;
    });

  // Mark which nodes are connected at all (dim isolates)
  const connected = new Set();
  edges.forEach((e) => {
    connected.add(e.source_id);
    connected.add(e.target_id);
  });

  // Predicate counts (for the filter pills)
  const predCounts = state.property_definitions.reduce((acc, p) => {
    acc[p.id] = state.relationships.filter((r) => r.property_definition_id === p.id).length;
    return acc;
  }, {});
  const usedPreds = state.property_definitions.filter((p) => predCounts[p.id] > 0);

  const selected = selectedId ? lookupNode(selectedId) : null;
  const selectedRels = selected
    ? state.relationships.filter((r) => r.source_id === selected.id || r.target_id === selected.id)
    : [];

  // Pan/zoom handlers
  const onWheel = (e) => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setZoom((z) => Math.min(2.5, Math.max(0.4, z + delta)));
  };
  const onMouseDown = (e) => {
    if (
      e.target.closest(
        ".graph-node, .graph-toolbar, .graph-legend, .graph-inspector, .graph-edge-hit",
      )
    )
      return;
    dragRef.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
  };
  const onMouseMove = (e) => {
    if (!dragRef.current) return;
    setPan({
      x: dragRef.current.panX + (e.clientX - dragRef.current.x),
      y: dragRef.current.panY + (e.clientY - dragRef.current.y),
    });
  };
  const onMouseUp = () => {
    dragRef.current = null;
  };

  const fit = () => {
    fitToCanvas();
  };

  // For arrow heads — pre-compute on the path
  const renderEdges = edges.map((e) => {
    const s = lookupNode(e.source_id);
    const t = lookupNode(e.target_id);
    const sp = GRAPH_LAYOUT[e.source_id];
    const tp = GRAPH_LAYOUT[e.target_id];
    const sw = nodeWidth(s.title);
    const tw = nodeWidth(t.title);
    const a = rectEdgePoint(sp.x, sp.y, sw, NODE_H, tp.x, tp.y);
    const b = rectEdgePoint(tp.x, tp.y, tw, NODE_H, sp.x, sp.y);
    const path = bezierPath(a, b, 0.22);
    const prop = state.property_definitions.find((p) => p.id === e.property_definition_id);
    const irrelevant = prop?.is_relevant === false;
    const isHighlighted =
      hoverEdgeId === e.id ||
      (selected && (e.source_id === selected.id || e.target_id === selected.id));
    return { e, prop, path, isHighlighted, irrelevant, end: b };
  });

  return (
    <div className="graph-shell">
      {/* SVG canvas */}
      <div
        className="graph-canvas"
        ref={canvasRef}
        onWheel={onWheel}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
      >
        <div className="graph-grid"></div>

        <div
          className="graph-stage"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
        >
          {/* Cluster halos */}
          <svg className="graph-svg" viewBox="0 0 1340 700" preserveAspectRatio="xMidYMid meet">
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--graph-edge-strong)" />
              </marker>
              <marker
                id="arrow-rose"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--accent-rose)" />
              </marker>
              <marker
                id="arrow-cyan"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="8"
                markerHeight="8"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--accent-cyan)" />
              </marker>
            </defs>

            {/* Cluster zones */}
            {Object.entries(CLUSTER_META).map(([key, meta]) =>
              hiddenClusters[key] ? null : (
                <g key={key} className={"graph-cluster cluster-" + meta.domain}>
                  <rect
                    x={meta.bbox.x}
                    y={meta.bbox.y}
                    width={meta.bbox.w}
                    height={meta.bbox.h}
                    rx="14"
                  />
                  <text x={meta.bbox.x + 16} y={meta.bbox.y + 24} className="graph-cluster-label">
                    {meta.title.toUpperCase()}
                  </text>
                </g>
              ),
            )}

            {/* Edges */}
            {renderEdges.map(({ e, prop, path, isHighlighted, irrelevant }) => (
              <g
                key={e.id}
                className={
                  "graph-edge" +
                  (isHighlighted ? " is-hot" : "") +
                  (irrelevant ? " is-irrelevant" : "")
                }
              >
                {/* invisible thicker hit area */}
                <path
                  className="graph-edge-hit"
                  d={path.d}
                  onMouseEnter={() => setHoverEdgeId(e.id)}
                  onMouseLeave={() => setHoverEdgeId(null)}
                />
                <path
                  className="graph-edge-line"
                  d={path.d}
                  markerEnd={
                    isHighlighted
                      ? "url(#arrow-cyan)"
                      : irrelevant
                        ? "url(#arrow-rose)"
                        : "url(#arrow)"
                  }
                />
              </g>
            ))}

            {/* Edge labels (above paths so they sit on top) */}
            {showLabels &&
              renderEdges.map(({ e, prop, path, isHighlighted }) => {
                const label = prop?.identifier || "?";
                const w = label.length * 6.6 + 14;
                return (
                  <g
                    key={"lbl_" + e.id}
                    className={"graph-edge-label" + (isHighlighted ? " is-hot" : "")}
                    transform={`translate(${path.mid.x - w / 2}, ${path.mid.y - 9})`}
                  >
                    <rect width={w} height="18" rx="3" />
                    <text x={w / 2} y="12">
                      {label}
                    </text>
                  </g>
                );
              })}
          </svg>

          {/* Nodes (HTML for crisp text + matching .kg-node aesthetic) */}
          {nodes.map((n) => {
            const pos = GRAPH_LAYOUT[n.id];
            const w = nodeWidth(n.title);
            const isSel = selectedId === n.id;
            const isOrphan = !connected.has(n.id);
            return (
              <button
                key={n.id}
                className={
                  "graph-node kg-node" + (isSel ? " selected" : "") + (isOrphan ? " is-orphan" : "")
                }
                data-domain={n.domain}
                data-kind={n.kind}
                style={{ left: pos.x - w / 2, top: pos.y - NODE_H / 2, width: w, height: NODE_H }}
                onClick={() => setSelectedId(n.id)}
                title={n.id}
              >
                <span className="swatch"></span>
                <span className="graph-node-title">{n.title}</span>
                <span className="graph-node-kind">{n.kind === "class" ? "C" : "I"}</span>
              </button>
            );
          })}
        </div>

        {/* Floating legend */}
        <div className="graph-legend">
          <div className="gl-section">
            <div className="gl-label">Domains</div>
            <div className="gl-row">
              <span className="dot dom-life"></span>Life sciences
              <span className="gl-count">{nodes.filter((n) => n.domain === "life").length}</span>
            </div>
            <div className="gl-row">
              <span className="dot dom-climate"></span>Climate
              <span className="gl-count">{nodes.filter((n) => n.domain === "climate").length}</span>
            </div>
            <div className="gl-row" data-disabled={hiddenClusters.software}>
              <span className="dot dom-software"></span>Software
              <span className="gl-count">
                {state.classes.filter((c) => c.domain === "software").length}
              </span>
            </div>
          </div>
          <div className="gl-section">
            <div className="gl-label">Glyphs</div>
            <div className="gl-row">
              <span className="gl-pill">C</span>Class
            </div>
            <div className="gl-row">
              <span className="gl-pill ind">I</span>Individual
            </div>
          </div>
          <div className="gl-section">
            <div className="gl-label">Edges</div>
            <div className="gl-row">
              <span className="gl-line"></span>Relevant
            </div>
            <div className="gl-row">
              <span className="gl-line dashed"></span>Irrelevant predicate
            </div>
          </div>
        </div>

        {/* Floating predicate filter chips (top right) */}
        <div className="graph-toolbar predicates">
          <div className="gt-label">PREDICATES</div>
          <div className="gt-chips">
            {usedPreds.map((p) => {
              const off = !!hiddenPreds[p.id];
              const irrelevant = p.is_relevant === false;
              return (
                <button
                  key={p.id}
                  className={"gt-chip" + (off ? " off" : "") + (irrelevant ? " irrelevant" : "")}
                  onClick={() => setHiddenPreds({ ...hiddenPreds, [p.id]: !off })}
                >
                  <span className="gt-chip-id">{p.identifier}</span>
                  <span className="gt-chip-n">{predCounts[p.id]}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Bottom controls — view toggles + zoom */}
        <div className="graph-toolbar bottom">
          <div className="gt-group">
            <button
              className={"gt-btn" + (showIndividuals ? " on" : "")}
              onClick={() => setShowIndividuals((v) => !v)}
            >
              <Icon name="data" size={13} /> Individuals
            </button>
            <button
              className={"gt-btn" + (showLabels ? " on" : "")}
              onClick={() => setShowLabels((v) => !v)}
            >
              <Icon name="tag" size={13} /> Edge labels
            </button>
            <button
              className={"gt-btn" + (!hiddenClusters.software ? " on" : "")}
              onClick={() =>
                setHiddenClusters({ ...hiddenClusters, software: !hiddenClusters.software })
              }
            >
              <span className="dot dom-software" style={{ marginRight: 6 }}></span>Software cluster
            </button>
          </div>
          <div className="gt-spacer"></div>
          <div className="gt-group zoom">
            <button
              className="gt-btn icon"
              onClick={() => setZoom((z) => Math.max(0.4, z - 0.15))}
              aria-label="Zoom out"
            >
              −
            </button>
            <button className="gt-btn icon ratio" onClick={fit}>
              {Math.round(zoom * 100)}%
            </button>
            <button
              className="gt-btn icon"
              onClick={() => setZoom((z) => Math.min(2.5, z + 0.15))}
              aria-label="Zoom in"
            >
              +
            </button>
            <button className="gt-btn" onClick={fit}>
              <Icon name="expand" size={13} /> Fit
            </button>
          </div>
        </div>
      </div>

      {/* Inspector */}
      <aside className="graph-inspector">
        {selected ? (
          <NodeInspector
            node={selected}
            rels={selectedRels}
            lookupNode={lookupNode}
            onSelect={setSelectedId}
            state={state}
          />
        ) : (
          <div className="empty">Select a node to inspect.</div>
        )}
      </aside>
    </div>
  );
}

function NodeInspector({ node, rels, lookupNode, onSelect, state }) {
  const out = rels.filter((r) => r.source_id === node.id);
  const incoming = rels.filter((r) => r.target_id === node.id);
  const tax = state.taxonomies.find((t) => t.id === node.taxonomy_id);
  const scheme = state.concept_schemes.find((s) => s.id === node.concept_scheme_id);

  const renderRelLine = (r, dir) => {
    const otherId = dir === "out" ? r.target_id : r.source_id;
    const other = lookupNode(otherId);
    const prop = state.property_definitions.find((p) => p.id === r.property_definition_id);
    return (
      <li key={r.id} className="gi-rel">
        <span className={"gi-rel-dir " + dir}>{dir === "out" ? "→" : "←"}</span>
        <span className="mono cyan-text gi-rel-pred">{prop?.identifier}</span>
        <button
          className="kg-node gi-rel-target"
          data-domain={other?.domain}
          onClick={() => onSelect(otherId)}
        >
          <span className="swatch"></span>
          <span>{other?.title}</span>
        </button>
      </li>
    );
  };

  return (
    <>
      <div className="gi-head">
        <div className="gi-head-eyebrow">
          <span className="chip gray">{node.kind}</span>
          {node.domain && (
            <span
              className={
                "chip " +
                (node.domain === "life"
                  ? "emerald"
                  : node.domain === "climate"
                    ? "amber"
                    : "violet")
              }
            >
              {node.domain}
            </span>
          )}
        </div>
        <div className="gi-title">{node.title}</div>
        <div className="gi-id mono">
          {node.id} · v{node.version}
        </div>
      </div>
      <div className="gi-body">
        {node.description && <p className="gi-desc">{node.description}</p>}

        <dl className="kv">
          {tax && (
            <>
              <dt>taxonomy</dt>
              <dd>{tax.title}</dd>
            </>
          )}
          {scheme && (
            <>
              <dt>scheme</dt>
              <dd>{scheme.title}</dd>
            </>
          )}
          {node.kind === "individual" && node.source && (
            <>
              <dt>source</dt>
              <dd className="mono">{node.source}</dd>
            </>
          )}
          {node.kind === "individual" && typeof node.confidence === "number" && (
            <>
              <dt>confidence</dt>
              <dd className="mono">{node.confidence.toFixed(2)}</dd>
            </>
          )}
          <dt>edges</dt>
          <dd className="mono">
            {rels.length} ({out.length} out, {incoming.length} in)
          </dd>
        </dl>

        {out.length > 0 && (
          <>
            <div className="gi-section-label">Outgoing · {out.length}</div>
            <ul className="gi-rels">{out.map((r) => renderRelLine(r, "out"))}</ul>
          </>
        )}
        {incoming.length > 0 && (
          <>
            <div className="gi-section-label">Incoming · {incoming.length}</div>
            <ul className="gi-rels">{incoming.map((r) => renderRelLine(r, "in"))}</ul>
          </>
        )}
        {rels.length === 0 && (
          <div className="empty-mini" style={{ marginTop: 12 }}>
            No relationships yet.
          </div>
        )}
      </div>
    </>
  );
}

window.GraphView = GraphView;
