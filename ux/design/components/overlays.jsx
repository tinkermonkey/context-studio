// =========================================================================
// Overlays — Command palette, Workspace switcher, Modal, Toast stack
// =========================================================================

// ---------------------------------------------------------------------
// Sparkline — used in stat tiles
// ---------------------------------------------------------------------
function Sparkline({ data, color = "#FBBF24", w = 88, h = 28 }) {
  const max = Math.max(...data), min = Math.min(...data);
  const range = Math.max(1, max - min);
  const stepX = w / (data.length - 1);
  const pts = data.map((v, i) => [i * stepX, h - ((v - min) / range) * (h - 4) - 2]);
  const path = "M " + pts.map((p) => p.join(" ")).join(" L ");
  const area = path + ` L ${w} ${h} L 0 ${h} Z`;
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} width={w} height={h} preserveAspectRatio="none">
      <path className="area" d={area} fill={color} />
      <path d={path} stroke={color} />
    </svg>
  );
}
window.Sparkline = Sparkline;

// ---------------------------------------------------------------------
// Command Palette
// ---------------------------------------------------------------------
function CommandPalette({ onClose, onNav }) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const items = useMemo(() => {
    const D = window.CS_DATA;
    const navItems = [];
    NAV_TREE.forEach((n) => {
      if (n.children) n.children.forEach((c) =>
        navItems.push({ kind: "Go", label: c.label, hint: n.label, route: c.id, icon: n.icon })
      );
      else navItems.push({ kind: "Go", label: n.label, hint: "", route: n.id, icon: n.icon });
    });
    const actions = [
      { kind: "Action", label: "New pipeline run…",        hint: "Pipelines",      icon: "pipeline" },
      { kind: "Action", label: "New class",                 hint: "Schema",         icon: "schema" },
      { kind: "Action", label: "New taxonomy",              hint: "Schema",         icon: "schema" },
      { kind: "Action", label: "Import individuals from CSV…", hint: "Data",        icon: "data" },
      { kind: "Action", label: "Reindex workspace",         hint: "System",         icon: "refresh" },
      { kind: "Action", label: "Toggle dark canvas",        hint: "View",           icon: "settings" },
      { kind: "Action", label: "Run pipeline · pubmed_genes", hint: "Pipelines",    icon: "play" },
      { kind: "Action", label: "Open in graph view",        hint: "Schema",         icon: "graph" },
    ];
    const recent = [
      { kind: "Recent", label: "BRCA1 — individual",  hint: "opened 4m ago",  route: "data/individuals", icon: "data" },
      { kind: "Recent", label: "pubmed_genes — pipeline", hint: "opened 12m ago", route: "pipelines/all", icon: "pipeline" },
      { kind: "Recent", label: "Genomics — concept scheme", hint: "opened 27m ago", route: "schema/schemes", icon: "schema" },
    ];
    const entityHits = q
      ? [
          ...D.classes.map((c) => ({ kind: "Class",      label: c.title, hint: c.id, route: "schema/classes",     icon: "schema",    domain: c.domain })),
          ...D.individuals.map((i) => ({ kind: "Individual", label: i.title, hint: i.id, route: "data/individuals", icon: "data" })),
          ...D.pipelines.map((p) => ({ kind: "Pipeline", label: p.name, hint: p.id, route: "pipelines/all",      icon: "pipeline" })),
        ]
      : [];

    const all = q
      ? [...entityHits, ...navItems, ...actions]
      : [...recent, ...navItems, ...actions];
    if (!q) return all;
    const Q = q.toLowerCase();
    return all.filter((x) =>
      x.label.toLowerCase().includes(Q) ||
      (x.hint && x.hint.toLowerCase().includes(Q)) ||
      (x.kind && x.kind.toLowerCase().includes(Q))
    );
  }, [q]);

  useEffect(() => { setActive(0); }, [q]);

  const onKey = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(items.length - 1, i + 1)); }
    if (e.key === "ArrowUp")   { e.preventDefault(); setActive((i) => Math.max(0, i - 1)); }
    if (e.key === "Enter")     { e.preventDefault(); pick(items[active]); }
    if (e.key === "Escape")    { onClose(); }
  };

  const pick = (item) => {
    if (!item) return;
    if (item.route) onNav(item.route);
    else onClose();
  };

  // Group by kind for first-impression structure
  const grouped = useMemo(() => {
    const order = ["Recent", "Class", "Individual", "Pipeline", "Go", "Action"];
    const groups = {};
    items.forEach((it) => { (groups[it.kind] ||= []).push(it); });
    return order.filter((k) => groups[k]).map((k) => [k, groups[k]]);
  }, [items]);

  let runningIndex = 0;

  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div className="palette" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Command palette" onKeyDown={onKey}>
        <div className="palette-input-row">
          <Icon name="search" size={14} />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search nodes, run a command, jump to…"
          />
          <span className="palette-esc">esc</span>
        </div>
        <div className="palette-results">
          {items.length === 0 && (
            <div style={{padding: "30px 16px", textAlign: "center", color: "var(--shell-fg-3)"}}>
              <div style={{fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase"}}>NO MATCHES</div>
              <div style={{marginTop: 4, fontSize: 12}}>Try a class, an individual, or a command verb.</div>
            </div>
          )}
          {grouped.flatMap(([kind, list]) => [
            <div key={kind + ":head"} className="palette-section">{kind === "Go" ? "Jump to" : kind === "Recent" ? "Recent" : kind}</div>,
            ...list.map((it) => {
              const idx = runningIndex++;
              return (
                <button
                  key={kind + ":" + idx}
                  className={"palette-item" + (idx === active ? " active" : "")}
                  onClick={() => pick(it)}
                  onMouseEnter={() => setActive(idx)}
                >
                  <span className={"palette-kind " + (kind === "Action" ? "action" : kind === "Recent" ? "recent" : kind === "Go" ? "go" : "")}>{kind}</span>
                  <Icon name={it.icon} size={13} />
                  <span className="palette-label">{it.label}</span>
                  {it.hint && <span className="palette-hint">{it.hint}</span>}
                  <Icon name="arrow" size={11} className="palette-arrow" />
                </button>
              );
            }),
          ])}
        </div>
        <div className="palette-foot">
          <span><span className="kbd-mini">↵</span> open</span>
          <span><span className="kbd-mini">↑↓</span> navigate</span>
          <span><span className="kbd-mini">tab</span> autocomplete</span>
          <span style={{flex: 1}}></span>
          <span><span className="kbd-mini">⌘K</span> close</span>
        </div>
      </div>
    </div>
  );
}
window.CommandPalette = CommandPalette;

// ---------------------------------------------------------------------
// Workspace switcher
// ---------------------------------------------------------------------
function WorkspaceSwitcher({ onClose }) {
  const recent = [
    { name: "molgraph-research",      path: "~/Projects/molgraph-research",      last: "now",         current: true,  classes: 20, individuals: 267, domain: "life" },
    { name: "climate-policy-graph",   path: "~/Projects/climate-policy-graph",   last: "2 days ago",  classes: 14, individuals: 1208, domain: "climate" },
    { name: "platform-eng-kb",        path: "~/Work/platform-eng-kb",            last: "last week",   classes: 31, individuals: 542, domain: "software" },
    { name: "sandbox",                path: "~/Projects/sandbox",                last: "3 weeks ago", classes: 4,  individuals: 18, domain: "default" },
  ];
  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div className="ws-dialog" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Switch workspace">
        <div className="ws-dialog-head">
          <div>
            <div className="ws-dialog-title">Open workspace</div>
            <div className="ws-dialog-sub">A workspace is a local folder containing your schema, data, pipelines, and config.</div>
          </div>
          <button className="palette-esc" onClick={onClose}>esc</button>
        </div>
        <div className="ws-dialog-actions">
          <button className="ws-action">
            <div className="ic"><Icon name="folder" size={16} /></div>
            <div className="t">Open folder…</div>
            <div className="d">Point Context Studio at an existing workspace on disk.</div>
          </button>
          <button className="ws-action">
            <div className="ic"><Icon name="add" size={16} /></div>
            <div className="t">New workspace…</div>
            <div className="d">Initialize a fresh <span className="mono">.context-studio/</span> directory.</div>
          </button>
          <button className="ws-action">
            <div className="ic"><Icon name="branch" size={16} /></div>
            <div className="t">Clone from git…</div>
            <div className="d">Pull a workspace from a remote, then open it.</div>
          </button>
        </div>
        <div className="ws-dialog-section">Recent</div>
        <div className="ws-list">
          {recent.map((w) => (
            <button key={w.name} className={"ws-recent-row" + (w.current ? " open" : "")} onClick={onClose}>
              <div className="mark"><Icon name="folder" size={14} /></div>
              <div className="main">
                <div className="name">
                  {w.name}
                  {w.current && <span className="badge">open</span>}
                </div>
                <div className="path">{w.path}</div>
              </div>
              <div className="stats">
                <span>{w.classes} cls</span>
                <span>{w.individuals.toLocaleString()} ind</span>
              </div>
              <div className="last">{w.last}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
window.WorkspaceSwitcher = WorkspaceSwitcher;

// ---------------------------------------------------------------------
// Modal — generic dialog wrapper
// ---------------------------------------------------------------------
function Modal({ open, onClose, title, subtitle, children, footer }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog">
        {(title || subtitle) && (
          <div className="modal-head">
            {title && <div className="title">{title}</div>}
            {subtitle && <div className="sub">{subtitle}</div>}
          </div>
        )}
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}
window.Modal = Modal;

// ---------------------------------------------------------------------
// Toast stack
// ---------------------------------------------------------------------
function ToastStack({ toasts }) {
  return (
    <div className="toast-stack">
      {toasts.map((t) => (
        <div key={t.id} className={"toast " + (t.kind || "")}>
          <Icon name={t.kind === "success" ? "check" : t.kind === "fail" ? "alert" : "sparkle"} size={14} />
          <div style={{flex:1}}>
            <div>{t.title}</div>
            {t.subtitle && <div className="mono">{t.subtitle}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}
window.ToastStack = ToastStack;
