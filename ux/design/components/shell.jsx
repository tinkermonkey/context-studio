// App shell — desktop chrome, sidebar, topbar, statusbar, command palette
const { useState, useEffect, useMemo, useCallback, useRef, Fragment } = React;

const NAV_TREE = [
  { id: "dashboard", label: "Dashboard", icon: "dashboard" },
  {
    id: "schema",
    label: "Schema",
    icon: "schema",
    children: [
      { id: "schema/taxonomies", label: "Taxonomies" },
      { id: "schema/schemes", label: "Concept schemes" },
      { id: "schema/classes", label: "Classes" },
      { id: "schema/properties", label: "Properties" },
      { id: "schema/relationships", label: "Relationships" },
    ],
  },
  {
    id: "data",
    label: "Data",
    icon: "data",
    children: [
      { id: "data/individuals", label: "Individuals", count: 267 },
      { id: "data/datasets", label: "Datasets", count: 12 },
    ],
  },
  {
    id: "pipelines",
    label: "Pipelines",
    icon: "pipeline",
    children: [
      { id: "pipelines/all", label: "All pipelines", count: 11 },
      { id: "pipelines/runs", label: "Run history" },
      { id: "pipelines/flavors", label: "Flavors" },
    ],
  },
  {
    id: "reference",
    label: "External Reference",
    icon: "reference",
    children: [
      { id: "reference/sources", label: "Sources", count: 7 },
      { id: "reference/grounding", label: "Grounding workflows" },
    ],
  },
  { id: "settings", label: "Configuration", icon: "settings" },
];

const ROUTE_LABELS = {
  dashboard: ["Dashboard"],
  "schema/taxonomies": ["Schema", "Taxonomies"],
  "schema/schemes": ["Schema", "Concept schemes"],
  "schema/classes": ["Schema", "Classes"],
  "schema/properties": ["Schema", "Properties"],
  "schema/relationships": ["Schema", "Relationships"],
  "data/individuals": ["Data", "Individuals"],
  "data/datasets": ["Data", "Datasets"],
  "pipelines/all": ["Pipelines", "All pipelines"],
  "pipelines/runs": ["Pipelines", "Run history"],
  "pipelines/flavors": ["Pipelines", "Flavors"],
  "reference/sources": ["External Reference", "Sources"],
  "reference/grounding": ["External Reference", "Grounding workflows"],
  settings: ["Configuration"],
};

const WORKSPACE = {
  name: "molgraph-research",
  path: "~/Projects/molgraph-research",
  branch: "main",
};

// ============= Desktop titlebar =============
function Titlebar({ onPalette, onSwitchWs }) {
  return (
    <div className="titlebar">
      <div className="lights">
        <span className="l-close" title="Close"></span>
        <span className="l-min" title="Minimize"></span>
        <span className="l-max" title="Zoom"></span>
      </div>
      <div className="titlebar-app">
        <span className="titlebar-app-name">Context Studio</span>
        <span className="titlebar-app-sep">—</span>
        <button className="titlebar-ws" onClick={onSwitchWs} title="Switch workspace">
          <Icon name="folder" size={12} />
          <span>{WORKSPACE.path}</span>
          <Icon name="chevDown" size={10} />
        </button>
      </div>
      <div className="titlebar-spacer"></div>
      <div className="titlebar-actions">
        <button className="titlebar-btn" onClick={onPalette} title="Command palette (⌘K)">
          <Icon name="search" size={12} />
          <span className="kbd-mini">⌘K</span>
        </button>
      </div>
    </div>
  );
}

// ============= Sidebar =============
function Sidebar({ route, onNav, collapsed, onToggle }) {
  const isActive = (id) => route === id || route.startsWith(id + "/");
  const isLeafActive = (id) => route === id;
  const isExpanded = (id) => isActive(id);

  return (
    <aside className="shell-rail">
      <div className="brand-row">
        <div className="brand-mark" aria-hidden="true"></div>
        {!collapsed && (
          <div className="brand-name">
            Context Studio<span>v0.1.0 · local</span>
          </div>
        )}
        <button className="rail-collapse" onClick={onToggle} aria-label="Toggle sidebar">
          <Icon name={collapsed ? "chevRight" : "chevLeft"} size={11} />
        </button>
      </div>

      <div className="nav-section">
        {NAV_TREE.flatMap((item) => [
          <div
            key={item.id}
            className={
              "nav-item " +
              (item.children
                ? isActive(item.id)
                  ? "active-parent"
                  : ""
                : isLeafActive(item.id)
                  ? "active"
                  : "")
            }
            onClick={() => onNav(item.children ? item.children[0].id : item.id)}
            title={collapsed ? item.label : undefined}
          >
            <Icon name={item.icon} size={16} />
            <span className="nav-label">{item.label}</span>
            {item.children && !collapsed && (
              <Icon
                name={isExpanded(item.id) ? "chevDown" : "chevRight"}
                size={12}
                className="ml-auto"
              />
            )}
          </div>,
          item.children && isExpanded(item.id) && !collapsed ? (
            <div key={item.id + ":sub"} className="nav-sub">
              {item.children.map((c) => (
                <div
                  key={c.id}
                  className={"nav-item " + (route === c.id ? "active" : "")}
                  onClick={() => onNav(c.id)}
                >
                  <span className="nav-label">{c.label}</span>
                  {c.count != null && <span className="nav-count">{c.count}</span>}
                </div>
              ))}
            </div>
          ) : null,
        ])}
      </div>

      <div className="rail-footer">
        <div className="rail-user">
          <div className="avatar">MC</div>
          <div className="rail-user-info">
            <div className="n">Maya Chen</div>
            <div className="e">local · {WORKSPACE.branch}</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

// ============= Topbar (workspace path + search + actions) =============
function Topbar({ route, onPalette, onSwitchWs }) {
  const crumbs = ROUTE_LABELS[route] || [route];
  return (
    <header className="topbar">
      <button className="ws-chip" onClick={onSwitchWs} title="Switch workspace">
        <span className="ws-chip-dot"></span>
        <span className="ws-chip-name">{WORKSPACE.name}</span>
        <Icon name="chevDown" size={11} />
      </button>
      <span className="crumbs-sep">/</span>
      <div className="crumbs">
        {crumbs.flatMap((c, i) => [
          <span key={i + ":lbl"} className={i === crumbs.length - 1 ? "last" : ""}>
            {c}
          </span>,
          i < crumbs.length - 1 ? (
            <span key={i + ":sep"} className="sep">
              /
            </span>
          ) : null,
        ])}
      </div>

      <button className="topbar-palette" onClick={onPalette} title="Command palette">
        <Icon name="search" size={14} />
        <span>Search or run command…</span>
        <span className="kbd">⌘K</span>
      </button>
      <button className="topbar-ico" title="Activity">
        <Icon name="bell" size={16} />
      </button>
      <button className="topbar-ico" title="Documentation">
        <Icon name="doc" size={16} />
      </button>
      <span className="env-pill">
        <span className="dot"></span>
        {WORKSPACE.branch}
      </span>
    </header>
  );
}

// ============= Statusbar (system indicators) =============
function Statusbar({ route }) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((v) => v + 1), 2200);
    return () => clearInterval(t);
  }, []);
  // Mildly fluctuating numbers so it feels alive
  const cpu = 12 + (tick % 5) * 3;
  const mem = 412 + (tick % 7) * 11;
  return (
    <div className="statusbar">
      <div className="statusbar-group">
        <span className="sb-item">
          <span className="pulse"></span>
          <span>graph daemon</span>
          <span className="sb-mono">:7474</span>
        </span>
        <span className="sb-divider"></span>
        <span className="sb-item">
          <Icon name="schema" size={11} />
          <span>22 classes · 267 individuals indexed</span>
        </span>
        <span className="sb-divider"></span>
        <span className="sb-item">
          <span className="dot-amber"></span>
          <span>1 pipeline running</span>
          <span className="sb-mono">pubmed_genes 38%</span>
        </span>
      </div>
      <div className="statusbar-group">
        <span className="sb-item">
          <span className="sb-mono">cpu {cpu}%</span>
        </span>
        <span className="sb-divider"></span>
        <span className="sb-item">
          <span className="sb-mono">mem {mem} MB</span>
        </span>
        <span className="sb-divider"></span>
        <span className="sb-item">
          <span className="sb-mono">UTF-8 · LF</span>
        </span>
        <span className="sb-divider"></span>
        <span className="sb-item">
          <Icon name="check" size={11} />
          <span className="sb-mono">synced 2m ago</span>
        </span>
      </div>
    </div>
  );
}

// ============= Command palette =============
function CommandPalette({ onClose, onNav }) {
  const [q, setQ] = useState("");
  const inputRef = useRef(null);
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const items = useMemo(() => {
    const navItems = [];
    NAV_TREE.forEach((n) => {
      if (n.children)
        n.children.forEach((c) =>
          navItems.push({ kind: "Go", label: c.label, hint: n.label, route: c.id, icon: n.icon }),
        );
      else navItems.push({ kind: "Go", label: n.label, hint: "", route: n.id, icon: n.icon });
    });
    const actions = [
      { kind: "Action", label: "New pipeline run…", hint: "Pipelines", icon: "pipeline" },
      { kind: "Action", label: "New class", hint: "Schema", icon: "schema" },
      { kind: "Action", label: "Import individuals from CSV…", hint: "Data", icon: "data" },
      { kind: "Action", label: "Open in graph view", hint: "Schema", icon: "schema" },
      { kind: "Action", label: "Reindex workspace", hint: "System", icon: "settings" },
      { kind: "Action", label: "Toggle theme", hint: "View", icon: "settings" },
    ];
    const recent = [
      {
        kind: "Recent",
        label: "Variant — class detail",
        hint: "opened 4m ago",
        route: "schema/classes",
        icon: "schema",
      },
      {
        kind: "Recent",
        label: "pubmed_genes — pipeline",
        hint: "opened 12m ago",
        route: "pipelines/all",
        icon: "pipeline",
      },
    ];
    const all = [...recent, ...navItems, ...actions];
    if (!q) return all;
    const Q = q.toLowerCase();
    return all.filter(
      (x) => x.label.toLowerCase().includes(Q) || (x.hint && x.hint.toLowerCase().includes(Q)),
    );
  }, [q]);

  const onPick = (item) => {
    if (item.route) onNav(item.route);
    else onClose();
  };

  return (
    <div className="palette-backdrop" onClick={onClose}>
      <div
        className="palette"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Command palette"
      >
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
          {items.length === 0 && <div className="palette-empty">No matches</div>}
          {items.map((it, i) => (
            <button
              key={i}
              className={"palette-item" + (i === 0 ? " first" : "")}
              onClick={() => onPick(it)}
            >
              <span className="palette-kind">{it.kind}</span>
              <Icon name={it.icon} size={13} />
              <span className="palette-label">{it.label}</span>
              {it.hint && <span className="palette-hint">{it.hint}</span>}
              <Icon name="arrow" size={11} className="palette-arrow" />
            </button>
          ))}
        </div>
        <div className="palette-foot">
          <span>
            <span className="kbd-mini">↵</span> open
          </span>
          <span>
            <span className="kbd-mini">↑↓</span> navigate
          </span>
          <span>
            <span className="kbd-mini">⌘K</span> close
          </span>
        </div>
      </div>
    </div>
  );
}

// ============= Workspace switcher dialog =============
function WorkspaceSwitcher({ onClose }) {
  const recent = [
    {
      name: "molgraph-research",
      path: "~/Projects/molgraph-research",
      last: "now",
      current: true,
      classes: 22,
      individuals: 267,
    },
    {
      name: "climate-policy-graph",
      path: "~/Projects/climate-policy-graph",
      last: "2 days ago",
      classes: 14,
      individuals: 1208,
    },
    {
      name: "platform-eng-kb",
      path: "~/Work/platform-eng-kb",
      last: "last week",
      classes: 31,
      individuals: 542,
    },
    {
      name: "sandbox",
      path: "~/Projects/sandbox",
      last: "3 weeks ago",
      classes: 4,
      individuals: 18,
    },
  ];
  return (
    <div className="palette-backdrop" onClick={onClose}>
      <div
        className="ws-dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Switch workspace"
      >
        <div className="ws-dialog-head">
          <div>
            <div className="ws-dialog-title">Open workspace</div>
            <div className="ws-dialog-sub">
              A workspace is a local folder containing your schema, data, and pipeline definitions.
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>
            esc
          </button>
        </div>
        <div className="ws-dialog-actions">
          <button className="btn btn-ghost">
            <Icon name="folder" /> Open folder…
          </button>
          <button className="btn btn-ghost">
            <Icon name="add" /> New workspace…
          </button>
          <button className="btn btn-ghost">
            <Icon name="data" /> Clone from git…
          </button>
        </div>
        <div className="ws-dialog-section">Recent</div>
        <div className="ws-list">
          {recent.map((w) => (
            <button
              key={w.name}
              className={"ws-row" + (w.current ? " current" : "")}
              onClick={onClose}
            >
              <div className="ws-row-mark">
                <Icon name="folder" size={14} />
              </div>
              <div className="ws-row-main">
                <div className="ws-row-name">
                  {w.name}
                  {w.current && <span className="ws-row-badge">open</span>}
                </div>
                <div className="ws-row-path">{w.path}</div>
              </div>
              <div className="ws-row-stats">
                <span className="sb-mono">{w.classes} cls</span>
                <span className="sb-mono">{w.individuals} ind</span>
              </div>
              <div className="ws-row-last">{w.last}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

window.Titlebar = Titlebar;
window.Sidebar = Sidebar;
window.Topbar = Topbar;
window.Statusbar = Statusbar;
window.CommandPalette = CommandPalette;
window.WorkspaceSwitcher = WorkspaceSwitcher;
window.NAV_TREE = NAV_TREE;
window.ROUTE_LABELS = ROUTE_LABELS;
