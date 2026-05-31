// =========================================================================
// Context Studio · Shell — titlebar, sidebar, topbar, statusbar
// Dark shell that wraps a dark canvas. Amber accent on active states.
// =========================================================================
const { useState, useEffect, useMemo, useCallback, useRef, Fragment } = React;

const NAV_TREE = [
  { id: "dashboard", label: "Dashboard", icon: "dashboard" },
  {
    id: "schema",
    label: "Schema",
    icon: "schema",
    children: [
      { id: "schema/taxonomies", label: "Taxonomies", count: 3 },
      { id: "schema/schemes", label: "Concept schemes", count: 8 },
      { id: "schema/classes", label: "Classes", count: 20 },
      { id: "schema/properties", label: "Properties", count: 8 },
      { id: "schema/relationships", label: "Relationships", count: 9 },
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
      { id: "pipelines/all", label: "All pipelines", count: 6 },
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
  { id: "graph", label: "Graph view", icon: "graph" },
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
  graph: ["Graph view"],
  settings: ["Configuration"],
};

const WORKSPACE = window.CS_DATA.workspace;

// =====================================================================
// Titlebar — macOS lights + workspace path + ⌘K
// =====================================================================
function Titlebar({ onPalette, onSwitchWs }) {
  return (
    <div className="titlebar" data-screen-label="Titlebar">
      <div className="lights">
        <span className="l-close" title="Close"></span>
        <span className="l-min" title="Minimize"></span>
        <span className="l-max" title="Zoom"></span>
      </div>
      <div className="titlebar-app">
        <span>Context Studio</span>
        <span className="titlebar-app-sep">—</span>
        <button className="titlebar-ws" onClick={onSwitchWs} title="Switch workspace">
          <Icon name="folder" size={12} />
          <span>{WORKSPACE.path}</span>
          <Icon name="chevDown" size={10} />
        </button>
      </div>
      <div className="titlebar-spacer"></div>
      <button className="titlebar-btn" onClick={onPalette} title="Command palette (⌘K)">
        <Icon name="search" size={12} />
        <span className="kbd-mini">⌘K</span>
      </button>
    </div>
  );
}

// =====================================================================
// Sidebar — nav tree, collapsible
// =====================================================================
function Sidebar({ route, onNav, collapsed, onToggle }) {
  const isActive = (id) => route === id || route.startsWith(id + "/");
  const isLeafActive = (id) => route === id;
  const isExpanded = (id) => isActive(id);

  return (
    <aside className={"shell-rail" + (collapsed ? " collapsed" : "")} data-screen-label="Sidebar">
      <div className="brand-row">
        <div className="brand-mark" aria-hidden="true">
          <i></i>
        </div>
        {!collapsed && (
          <div className="brand-name">
            Context Studio<span>{WORKSPACE.version} · local</span>
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
              <Icon name={isExpanded(item.id) ? "chevDown" : "chevRight"} size={12} />
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
          {!collapsed && <Icon name="chevDown" size={11} className="muted" />}
        </div>
      </div>
    </aside>
  );
}

// =====================================================================
// Topbar — workspace chip + crumbs + palette + actions
// =====================================================================
function Topbar({ route, onPalette, onSwitchWs, notifCount = 2 }) {
  const crumbs = ROUTE_LABELS[route] || [route];
  return (
    <header className="topbar" data-screen-label="Topbar">
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
        <span className="label">Search workspace, run command, jump to…</span>
        <span className="kbd">⌘K</span>
      </button>
      <button className="topbar-ico" title="Activity" style={{ position: "relative" }}>
        <Icon name="bell" size={16} />
        {notifCount > 0 && <span className="badge">{notifCount}</span>}
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

// =====================================================================
// Statusbar — live daemon pulse + telemetry
// =====================================================================
function Statusbar() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((v) => v + 1), 2400);
    return () => clearInterval(t);
  }, []);
  const cpu = 12 + (tick % 5) * 3;
  const mem = 412 + (tick % 7) * 11;
  const progress = Math.min(98, 38 + (tick % 8) * 2);

  return (
    <div className="statusbar" data-screen-label="Statusbar">
      <div className="statusbar-group">
        <span className="sb-item">
          <span className="pulse sm"></span>
          <span>graph daemon</span>
          <span className="sb-mono">:7474</span>
        </span>
        <span className="sb-divider"></span>
        <span className="sb-item">
          <Icon name="schema" size={11} />
          <span className="sb-mono">20 cls · 267 ind · 9 rel</span>
        </span>
        <span className="sb-divider"></span>
        <span className="sb-item">
          <span className="dot-amber"></span>
          <span>1 running</span>
          <span className="sb-mono sb-pipe-name">pubmed_genes · {progress}%</span>
        </span>
        <span className="sb-divider"></span>
        <span className="sb-item">
          <Icon name="branch" size={11} />
          <span className="sb-mono">main · 3 ahead</span>
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
          <span className="sb-mono">synced {WORKSPACE.last_sync}</span>
        </span>
      </div>
    </div>
  );
}

Object.assign(window, {
  Titlebar,
  Sidebar,
  Topbar,
  Statusbar,
  NAV_TREE,
  ROUTE_LABELS,
  WORKSPACE,
});
