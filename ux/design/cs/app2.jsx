// =========================================================================
// Context Studio v2 — App entry (CRUD phase)
// Same real Heimdall ShellLayout as app.jsx, with:
//   • nav: Pipelines › "Flavors" rebranded to "Pipeline types" (which now
//     contains Configurations)
//   • inline-editable CRUD pages (loaded from cs/crud/*)
//   • a toast queue driven by the CRUD store
//   • create entry points wired through the command palette
// =========================================================================

const NAV_SECTIONS = [
  {
    title: "WORKSPACE",
    items: [
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
          { id: "data/individuals", label: "Individuals" },
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
          { id: "pipelines/types", label: "Pipeline types" },
        ],
      },
      {
        id: "reference",
        label: "External Reference",
        icon: "link",
        children: [
          { id: "reference/sources", label: "Sources", count: 7 },
          { id: "reference/grounding", label: "Grounding workflows" },
        ],
      },
      { id: "graph", label: "Graph view", icon: "graph" },
      { id: "settings", label: "Configuration", icon: "settings" },
    ],
  },
];

const ROUTE_CRUMBS = {
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
  "pipelines/types": ["Pipelines", "Pipeline types"],
  "reference/sources": ["External Reference", "Sources"],
  "reference/grounding": ["External Reference", "Grounding workflows"],
  graph: ["Graph view"],
  settings: ["Configuration"],
};

function CSApp() {
  const initialRoute = (() => {
    const h = (location.hash || "").match(/r=([^&]+)/);
    return h ? decodeURIComponent(h[1]) : "dashboard";
  })();
  const [route, setRoute] = useState(initialRoute);
  const [collapsed, setCollapsed] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const toasts = useCSToasts();

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    location.hash = "r=" + encodeURIComponent(route);
  }, [route]);
  useEffect(() => {
    const onHash = () => {
      const m = (location.hash || "").match(/r=([^&]+)/);
      if (m) setRoute(decodeURIComponent(m[1]));
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = (r) => {
    setRoute(r);
    setPaletteOpen(false);
  };
  // create from the palette: stash a pending request, navigate; the page picks it up.
  const requestCreate = (r, type) => {
    window.__CS_PENDING = { type, ctx: {} };
    navigate(r);
  };

  // --- page dispatch -----------------------------------------------------
  let Page;
  if (route === "dashboard") Page = <CSDashboard onNav={navigate} />;
  else if (route === "schema/classes") Page = <CSSchemaClasses route={route} onNav={navigate} />;
  else if (route === "schema/taxonomies")
    Page = <CSSchemaTaxonomies route={route} onNav={navigate} />;
  else if (route === "schema/schemes") Page = <CSSchemaSchemes route={route} onNav={navigate} />;
  else if (route === "schema/properties")
    Page = <CSSchemaProperties route={route} onNav={navigate} />;
  else if (route === "schema/relationships")
    Page = <CSSchemaRelationships route={route} onNav={navigate} />;
  else if (route === "data/individuals") Page = <CSIndividuals onNav={navigate} />;
  else if (route === "data/datasets") Page = <CSDatasets onNav={navigate} />;
  else if (route === "pipelines/types") Page = <CSPipelineTypes route={route} onNav={navigate} />;
  else if (route === "pipelines/all") Page = <CSPipelines onNav={navigate} />;
  else Page = <CSStub route={route} />;

  // --- Statusbar ---------------------------------------------------------
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((v) => v + 1), 2200);
    return () => clearInterval(t);
  }, []);
  const cpu = 12 + (tick % 5) * 3;
  const mem = 412 + (tick % 7) * 11;
  const statusbarLeft = [
    { kind: "pulse", tone: "emerald", label: "graph daemon :7474", mono: true },
    { kind: "divider" },
    { kind: "icon", icon: "schema", label: "22 classes · 267 individuals indexed" },
    { kind: "divider" },
    { kind: "pulse", tone: "amber", label: "1 pipeline running · pubmed_genes 38%", mono: true },
  ];
  const statusbarRight = [
    { kind: "icon", icon: "zap", label: `cpu ${cpu}%`, mono: true },
    { kind: "divider" },
    { kind: "icon", icon: "hardDrive", label: `mem ${mem} MB`, mono: true },
    { kind: "divider" },
    { kind: "icon", icon: "check", label: "synced 2m ago", mono: true },
  ];

  const crumbs = ROUTE_CRUMBS[route] || [route];
  const breadcrumbs = [
    { label: window.CS_DATA.workspace.name, onClick: () => navigate("dashboard") },
    ...crumbs.map((label, i) => ({ label, onClick: i < crumbs.length - 1 ? () => {} : undefined })),
  ];

  const paletteCommands = useMemo(
    () => [
      {
        id: "go-dashboard",
        group: "Navigate",
        label: "Go to Dashboard",
        description: "Workspace overview",
        icon: "dashboard",
        onSelect: () => navigate("dashboard"),
      },
      {
        id: "go-taxonomies",
        group: "Navigate",
        label: "Go to Taxonomies",
        description: "/schema/taxonomies",
        icon: "schema",
        onSelect: () => navigate("schema/taxonomies"),
      },
      {
        id: "go-schemes",
        group: "Navigate",
        label: "Go to Concept schemes",
        description: "/schema/schemes",
        icon: "schema",
        onSelect: () => navigate("schema/schemes"),
      },
      {
        id: "go-classes",
        group: "Navigate",
        label: "Go to Classes",
        description: "/schema/classes",
        icon: "graph",
        onSelect: () => navigate("schema/classes"),
      },
      {
        id: "go-properties",
        group: "Navigate",
        label: "Go to Properties",
        description: "/schema/properties",
        icon: "component",
        onSelect: () => navigate("schema/properties"),
      },
      {
        id: "go-relationships",
        group: "Navigate",
        label: "Go to Relationships",
        description: "/schema/relationships",
        icon: "link",
        onSelect: () => navigate("schema/relationships"),
      },
      {
        id: "go-individuals",
        group: "Navigate",
        label: "Go to Individuals",
        description: "/data/individuals",
        icon: "data",
        onSelect: () => navigate("data/individuals"),
      },
      {
        id: "go-datasets",
        group: "Navigate",
        label: "Go to Datasets",
        description: "/data/datasets",
        icon: "data",
        onSelect: () => navigate("data/datasets"),
      },
      {
        id: "go-types",
        group: "Navigate",
        label: "Go to Pipeline types",
        description: "/pipelines/types",
        icon: "pipeline",
        onSelect: () => navigate("pipelines/types"),
      },
      {
        id: "new-taxonomy",
        group: "Create",
        label: "New taxonomy…",
        description: "Schema · taxonomy",
        icon: "plus",
        onSelect: () => requestCreate("schema/taxonomies", "taxonomy"),
      },
      {
        id: "new-scheme",
        group: "Create",
        label: "New concept scheme…",
        description: "Schema · concept_scheme",
        icon: "plus",
        onSelect: () => requestCreate("schema/schemes", "scheme"),
      },
      {
        id: "new-class",
        group: "Create",
        label: "New class…",
        description: "Schema · class",
        icon: "plus",
        onSelect: () => requestCreate("schema/classes", "class"),
      },
      {
        id: "new-property",
        group: "Create",
        label: "New property…",
        description: "Schema · property_definition",
        icon: "plus",
        onSelect: () => requestCreate("schema/properties", "property"),
      },
      {
        id: "new-relationship",
        group: "Create",
        label: "New relationship…",
        description: "Schema · relationship",
        icon: "plus",
        onSelect: () => requestCreate("schema/relationships", "relationship"),
      },
      {
        id: "new-individual",
        group: "Create",
        label: "New individual…",
        description: "Data · individual",
        icon: "plus",
        onSelect: () => requestCreate("data/individuals", "individual"),
      },
      {
        id: "new-dataset",
        group: "Create",
        label: "New dataset…",
        description: "Data · dataset",
        icon: "plus",
        onSelect: () => requestCreate("data/datasets", "dataset"),
      },
      {
        id: "new-config",
        group: "Create",
        label: "New configuration…",
        description: "Pipelines · configuration",
        icon: "plus",
        onSelect: () => requestCreate("pipelines/types", "configuration"),
      },
    ],
    [route],
  );

  return (
    <>
      <ShellLayout
        appTitle={{ title: "Context Studio", version: "v0.3.0 · local" }}
        sidebar={{
          sections: NAV_SECTIONS,
          activeItemId: route,
          collapsed,
          onCollapse: setCollapsed,
          onSelectItem: navigate,
        }}
        topbar={{
          breadcrumbs,
          children: (
            <>
              <button
                onClick={() => setPaletteOpen(true)}
                title="Search or run command"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "6px 10px",
                  minWidth: 260,
                  borderRadius: "var(--radius-md)",
                  background: "rgb(var(--canvas-bg-2))",
                  border: "1px solid rgb(var(--canvas-border))",
                  color: "rgb(var(--canvas-fg-3))",
                  fontSize: 12.5,
                  cursor: "pointer",
                }}
              >
                <Icon name="search" size={13} />
                <span style={{ flex: 1, textAlign: "left" }}>Search or run command…</span>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    padding: "1px 5px",
                    background: "rgb(var(--canvas-bg))",
                    border: "1px solid rgb(var(--canvas-border))",
                    borderRadius: 3,
                  }}
                >
                  ⌘K
                </span>
              </button>
              <Button variant="ghost" size="sm" icon>
                <Icon name="bell" size={14} />
              </Button>
              <Button variant="ghost" size="sm" icon>
                <Icon name="file" size={14} />
              </Button>
              <Chip form="env">{window.CS_DATA.workspace.branch || "main"}</Chip>
            </>
          ),
        }}
        statusbar={{ left: statusbarLeft, right: statusbarRight }}
      >
        {Page}
      </ShellLayout>

      <CommandPalette
        isOpen={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        commands={paletteCommands}
        placeholder="Search workspace, run command…"
      />

      {toasts.length > 0 && (
        <div
          style={{
            position: "fixed",
            bottom: 44,
            right: 24,
            zIndex: 60,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          {toasts.map((t) => (
            <Toast
              key={t.id}
              isOpen
              onClose={() => CSStore.dismissToast(t.id)}
              variant={t.variant || "info"}
              title={t.title}
              subtitle={t.subtitle}
              duration={3600}
            />
          ))}
        </div>
      )}
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<CSApp />);
