// =========================================================================
// Context Studio v2 — App entry
// Composes the REAL Heimdall ShellLayout (Titlebar + Sidebar + Topbar +
// Statusbar) and routes the canvas to real-component pages.
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
          { id: "schema/classes", label: "Classes", count: 22 },
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
  "pipelines/flavors": ["Pipelines", "Flavors"],
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
  const [newClassOpen, setNewClassOpen] = useState(false);
  const [toast, setToast] = useState(null);

  // form state for new-class modal
  const [ncIdent, setNcIdent] = useState("cls_neuron_motor");
  const [ncTitle, setNcTitle] = useState("Motor neuron");
  const [ncScheme, setNcScheme] = useState("sch_cell_bio");
  const [ncParent, setNcParent] = useState("");
  const [ncDesc, setNcDesc] = useState(
    "Motor neurons carry signals from the central nervous system to muscle fibers.",
  );

  // ⌘K + Esc keyboard shortcuts
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

  // Persist route in hash
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

  // --- page dispatch -----------------------------------------------------
  let Page;
  if (route === "dashboard") Page = <CSDashboard onNav={navigate} />;
  else if (route === "schema/classes")
    Page = (
      <CSSchemaClasses
        route={route}
        onNav={navigate}
        onOpenNewClass={() => setNewClassOpen(true)}
      />
    );
  else if (route === "schema/taxonomies")
    Page = <CSSchemaTaxonomies route={route} onNav={navigate} />;
  else if (route === "schema/schemes") Page = <CSSchemaSchemes route={route} onNav={navigate} />;
  else if (route === "schema/properties")
    Page = <CSSchemaProperties route={route} onNav={navigate} />;
  else if (route === "schema/relationships")
    Page = <CSSchemaRelationships route={route} onNav={navigate} />;
  else if (route === "data/individuals") Page = <CSIndividuals onNav={navigate} />;
  else if (route === "pipelines/all") Page = <CSPipelines onNav={navigate} />;
  else Page = <CSStub route={route} />;

  // --- Statusbar items ---------------------------------------------------
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

  // --- Topbar breadcrumbs -------------------------------------------------
  const crumbs = ROUTE_CRUMBS[route] || [route];
  const breadcrumbs = [
    { label: window.CS_DATA.workspace.name, onClick: () => navigate("dashboard") },
    ...crumbs.map((label, i) => ({
      label,
      onClick: i < crumbs.length - 1 ? () => {} : undefined,
    })),
  ];

  // --- Command palette commands ------------------------------------------
  const paletteCommands = useMemo(
    () => [
      {
        id: "go-dashboard",
        label: "Go to Dashboard",
        description: "Workspace overview",
        icon: "dashboard",
        onSelect: () => navigate("dashboard"),
      },
      {
        id: "go-classes",
        label: "Go to Classes",
        description: "/schema/classes",
        icon: "schema",
        onSelect: () => navigate("schema/classes"),
      },
      {
        id: "go-taxonomies",
        label: "Go to Taxonomies",
        description: "/schema/taxonomies",
        icon: "schema",
        onSelect: () => navigate("schema/taxonomies"),
      },
      {
        id: "go-properties",
        label: "Go to Properties",
        description: "/schema/properties",
        icon: "component",
        onSelect: () => navigate("schema/properties"),
      },
      {
        id: "go-relationships",
        label: "Go to Relationships",
        description: "/schema/relationships",
        icon: "link",
        onSelect: () => navigate("schema/relationships"),
      },
      {
        id: "go-individuals",
        label: "Go to Individuals",
        description: "/data/individuals",
        icon: "data",
        onSelect: () => navigate("data/individuals"),
      },
      {
        id: "go-pipelines",
        label: "Go to Pipelines",
        description: "/pipelines/all",
        icon: "pipeline",
        onSelect: () => navigate("pipelines/all"),
      },
      {
        id: "go-graph",
        label: "Go to Graph view",
        description: "Inferred KG layout",
        icon: "graph",
        onSelect: () => navigate("graph"),
      },
      {
        id: "new-class",
        label: "New class…",
        description: "Open the new-class modal",
        icon: "plus",
        onSelect: () => setNewClassOpen(true),
      },
      {
        id: "new-pipeline-run",
        label: "Run pipeline…",
        description: "Trigger a pipeline run",
        icon: "pipeline",
        onSelect: () =>
          setToast({
            variant: "info",
            title: "Pipeline scheduled",
            subtitle: "pubmed_genes · next slot",
          }),
      },
    ],
    [route],
  );

  // --- Render ------------------------------------------------------------
  return (
    <>
      {/* No <Titlebar>. The macOS-style window chrome is intentionally
          OMITTED: this prototype runs in a browser, not a wrapped Electron
          shell, so a fake traffic-light titlebar is decoration we don't need.
          To add one back, pass `titlebar={{ left, center, right }}` to
          <ShellLayout> — but please don't unless we're shipping a desktop wrapper. */}
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

      <Modal
        isOpen={newClassOpen}
        onClose={() => setNewClassOpen(false)}
        title="New class"
        subtitle="Classes belong to a concept scheme and inherit property definitions from their parent."
        hintFooter="POST /classes"
        footer={
          <>
            <Button variant="ghost" onClick={() => setNewClassOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                setNewClassOpen(false);
                setToast({
                  variant: "success",
                  title: "Class created",
                  subtitle: `${ncIdent} · ${ncScheme}`,
                });
              }}
            >
              Create class
            </Button>
          </>
        }
      >
        <Field label="Identifier" hint="snake_case · required" required>
          <TextInput mono value={ncIdent} onChange={(e) => setNcIdent(e.target.value)} autoFocus />
        </Field>
        <Field label="Display title">
          <TextInput value={ncTitle} onChange={(e) => setNcTitle(e.target.value)} />
        </Field>
        <Field label="Concept scheme" required>
          <Select value={ncScheme} onChange={(e) => setNcScheme(e.target.value)}>
            {window.CS_DATA.concept_schemes.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title} · {s.id}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Parent class" hint="optional">
          <Select value={ncParent} onChange={(e) => setNcParent(e.target.value)}>
            <option value="">— none —</option>
            {window.CS_DATA.classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title} · {c.id}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Description">
          <TextArea value={ncDesc} onChange={(e) => setNcDesc(e.target.value)} rows={3} />
        </Field>
      </Modal>

      {toast && (
        <div style={{ position: "fixed", bottom: 44, right: 24, zIndex: 60 }}>
          <Toast
            isOpen={true}
            onClose={() => setToast(null)}
            variant={toast.variant || "info"}
            title={toast.title}
            subtitle={toast.subtitle}
            duration={3200}
          />
        </div>
      )}
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<CSApp />);
